#include "measure_internal.h"
#include "measure_result_pack.h"

#include "zxhsim/mem.h"

#include <cub/device/device_scan.cuh>
#include <thrust/iterator/transform_iterator.h>
#include <cuComplex.h>
#include <cuda_runtime.h>

#include <algorithm>
#include <cstdlib>
#include <cstdint>
#include <limits>
#include <random>
#include <string>
#include <type_traits>
#include <vector>

namespace ZXHSim
{
static_assert(std::is_same_v<float_t, float> || std::is_same_v<float_t, double>,
              "float_t must be float or double");
template <typename T> struct cu_ops_t;

template <> struct cu_ops_t<float>
{
    using complex_t = cuFloatComplex;
    __host__ __device__ static inline float real(complex_t v)
    {
        return cuCrealf(v);
    }
    __host__ __device__ static inline float imag(complex_t v)
    {
        return cuCimagf(v);
    }
};

template <> struct cu_ops_t<double>
{
    using complex_t = cuDoubleComplex;
    __host__ __device__ static inline double real(complex_t v)
    {
        return cuCreal(v);
    }
    __host__ __device__ static inline double imag(complex_t v)
    {
        return cuCimag(v);
    }
};

using device_complex_t = typename cu_ops_t<float_t>::complex_t;

__host__ __device__ inline float_t zx_real(device_complex_t v)
{
    return cu_ops_t<float_t>::real(v);
}

__host__ __device__ inline float_t zx_imag(device_complex_t v)
{
    return cu_ops_t<float_t>::imag(v);
}

#define cuDoubleComplex device_complex_t
#define cuCreal zx_real
#define cuCimag zx_imag

namespace
{
constexpr int kCudaThreads = 256;
constexpr size_t kReduceChunkElems = static_cast<size_t>(kCudaThreads) * 2;
constexpr size_t kDefaultMultinomialMeasureI = 12;

size_t multinomial_measure_i()
{
    const char *env = std::getenv("ZXHSIM_MEASURE_I");
    if (env == nullptr)
        return kDefaultMultinomialMeasureI;

    char *end = nullptr;
    const unsigned long parsed = std::strtoul(env, &end, 10);
    if (end == env || parsed == 0 || parsed >= std::numeric_limits<size_t>::digits)
        return kDefaultMultinomialMeasureI;
    return static_cast<size_t>(parsed);
}

size_t sampling_segment_len(const sv_t &sv)
{
    const size_t local_size = static_cast<size_t>(sv.block_end - sv.block_start);
    if (local_size == 0)
        return 1;
    return std::min(size_t(1) << multinomial_measure_i(), local_size);
}

size_t sampling_segment_count(const sv_t &sv, size_t segment_len)
{
    const size_t local_size = static_cast<size_t>(sv.block_end - sv.block_start);
    if (local_size == 0)
        return 0;
    return (local_size + segment_len - 1) / segment_len;
}

uint64_t mix_seed(uint64_t base, uint64_t salt)
{
    uint64_t z = base + 0x9e3779b97f4a7c15ULL + salt;
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
}

uint64_t choose_base_seed(bool use_seed, uint64_t seed)
{
    if (use_seed)
        return seed;
    return std::random_device{}();
}

void check_cuda(cudaError_t err, const char *what)
{
    if (err == cudaSuccess)
        return;
    abort(std::string(what) + ": " + cudaGetErrorString(err));
}

int calc_blocks(size_t n)
{
    return static_cast<int>((n + static_cast<size_t>(kCudaThreads) - 1) /
                            static_cast<size_t>(kCudaThreads));
}

int cub_num_items(size_t count, const char *what)
{
    if (count > static_cast<size_t>(std::numeric_limits<int>::max()))
        abort(std::string(what) + " exceeds CUB item limit");
    return static_cast<int>(count);
}

size_t cdf_storage_elems(size_t float_count)
{
    const size_t bytes = float_count * sizeof(float_t);
    return (bytes + sizeof(val_t) - 1) / sizeof(val_t);
}

size_t valid_segment_len(const sv_t &sv, raddr_t seg, size_t segment_len)
{
    if (seg >= sv.block_end)
        return 0;
    return std::min(segment_len, static_cast<size_t>(sv.block_end - seg));
}

struct amplitude_prob_op_t
{
    __host__ __device__ __forceinline__ float_t operator()(const cuDoubleComplex &v) const
    {
        const float_t re = cuCreal(v);
        const float_t im = cuCimag(v);
        return re * re + im * im;
    }
};

__global__ void sum_prob_partial_kernel(const cuDoubleComplex *data, size_t n,
                                        double *partial)
{
    extern __shared__ double sh[];

    const size_t tid = static_cast<size_t>(threadIdx.x);
    const size_t begin = static_cast<size_t>(blockIdx.x) * kReduceChunkElems;
    const size_t idx0 = begin + tid;
    const size_t idx1 = idx0 + static_cast<size_t>(blockDim.x);

    double local = 0.0;
    if (idx0 < n)
    {
        const cuDoubleComplex v = data[idx0];
        const double re = cuCreal(v);
        const double im = cuCimag(v);
        local += re * re + im * im;
    }
    if (idx1 < n)
    {
        const cuDoubleComplex v = data[idx1];
        const double re = cuCreal(v);
        const double im = cuCimag(v);
        local += re * re + im * im;
    }

    sh[tid] = local;
    __syncthreads();

    for (size_t stride = static_cast<size_t>(blockDim.x) >> 1; stride >= 1; stride >>= 1)
    {
        if (tid < stride)
            sh[tid] += sh[tid + stride];
        __syncthreads();
        if (stride == 1)
            break;
    }

    if (tid == 0)
        partial[blockIdx.x] = sh[0];
}

__global__ void reduce_double_partial_kernel(const double *data, size_t n,
                                             double *partial)
{
    extern __shared__ double sh[];

    const size_t tid = static_cast<size_t>(threadIdx.x);
    const size_t begin = static_cast<size_t>(blockIdx.x) * kReduceChunkElems;
    const size_t idx0 = begin + tid;
    const size_t idx1 = idx0 + static_cast<size_t>(blockDim.x);

    double local = 0.0;
    if (idx0 < n)
        local += data[idx0];
    if (idx1 < n)
        local += data[idx1];

    sh[tid] = local;
    __syncthreads();

    for (size_t stride = static_cast<size_t>(blockDim.x) >> 1; stride >= 1; stride >>= 1)
    {
        if (tid < stride)
            sh[tid] += sh[tid + stride];
        __syncthreads();
        if (stride == 1)
            break;
    }

    if (tid == 0)
        partial[blockIdx.x] = sh[0];
}

__global__ void segment_cdf_finalize_kernel(float_t *cdf, size_t valid_count,
                                            float_t cdf_head_in,
                                            float_t *segment_total_out)
{
    const size_t idx = static_cast<size_t>(blockIdx.x) * static_cast<size_t>(blockDim.x) +
                       static_cast<size_t>(threadIdx.x);
    if (idx >= valid_count)
        return;

    const float_t local_cdf = cdf[idx];
    if (idx + 1 == valid_count)
        *segment_total_out = local_cdf;
    cdf[idx] = local_cdf + cdf_head_in;
}

__global__ void segment_mass_kernel(const cuDoubleComplex *data, size_t local_size,
                                    size_t segment_len, float_t *mass_out)
{
    extern __shared__ double sh[];

    const size_t seg_idx = static_cast<size_t>(blockIdx.x);
    const size_t seg_begin = seg_idx * segment_len;
    const size_t tid = static_cast<size_t>(threadIdx.x);

    double local = 0.0;
    if (seg_begin < local_size)
    {
        const size_t valid_count = min(segment_len, local_size - seg_begin);
        for (size_t idx = tid; idx < valid_count; idx += static_cast<size_t>(blockDim.x))
        {
            const cuDoubleComplex v = data[seg_begin + idx];
            const double re = cuCreal(v);
            const double im = cuCimag(v);
            local += re * re + im * im;
        }
    }

    sh[tid] = local;
    __syncthreads();

    for (size_t stride = static_cast<size_t>(blockDim.x) >> 1; stride >= 1; stride >>= 1)
    {
        if (tid < stride)
            sh[tid] += sh[tid + stride];
        __syncthreads();
        if (stride == 1)
            break;
    }

    if (tid == 0)
        mass_out[seg_idx] = static_cast<float_t>(sh[0]);
}

__global__ void resolve_thresholds_kernel(const float_t *cdf, size_t valid_count,
                                          raddr_t seg_base,
                                          const float_t *thresholds,
                                          size_t threshold_count,
                                          raddr_t *out)
{
    const size_t idx = static_cast<size_t>(blockIdx.x) * static_cast<size_t>(blockDim.x) +
                       static_cast<size_t>(threadIdx.x);
    if (idx >= threshold_count)
        return;

    const float_t tau = thresholds[idx];
    size_t lo = 0;
    size_t hi = valid_count;
    while (lo < hi)
    {
        const size_t mid = lo + (hi - lo) / 2;
        if (cdf[mid] <= tau)
            lo = mid + 1;
        else
            hi = mid;
    }

    const size_t offset = (lo >= valid_count) ? (valid_count - 1) : lo;
    out[idx] = seg_base + static_cast<raddr_t>(offset);
}

__global__ void map_real_to_virtual_words_kernel(const raddr_t *real_results,
                                                 size_t count, const uint64_t *rows,
                                                 const uint64_t *b_words,
                                                 size_t nbits, size_t word_count,
                                                 uint64_t *out_words)
{
    const size_t idx = static_cast<size_t>(blockIdx.x) * static_cast<size_t>(blockDim.x) +
                       static_cast<size_t>(threadIdx.x);
    if (idx >= count)
        return;

    uint64_t *dst = out_words + idx * word_count;
    for (size_t w = 0; w < word_count; w++)
        dst[w] = 0ULL;

    const raddr_t real = real_results[idx];
    for (size_t q = 0; q < nbits; q++)
    {
        const bool affine_bit = ((__popcll(real & rows[q]) & 1U) != 0U);
        const bool bias_bit = ((b_words[q >> 6] >> (q & 63)) & 1ULL) != 0ULL;
        if (affine_bit ^ bias_bit)
            dst[q >> 6] |= (1ULL << (q & 63));
    }
}

template <typename T>
void ensure_device_capacity(T *&ptr, size_t &capacity, size_t need, const char *what)
{
    if (need <= capacity)
        return;
    if (ptr != nullptr)
        check_cuda(cudaFree(ptr), what);
    ptr = nullptr;
    capacity = 0;
    if (need == 0)
        return;
    check_cuda(cudaMalloc(reinterpret_cast<void **>(&ptr), need * sizeof(T)), what);
    capacity = need;
}

template <typename T>
void ensure_host_pinned_capacity(T *&ptr, size_t &capacity, size_t need, const char *what)
{
    if (need <= capacity)
        return;
    if (ptr != nullptr)
        check_cuda(cudaFreeHost(ptr), what);
    ptr = nullptr;
    capacity = 0;
    if (need == 0)
        return;
    check_cuda(cudaMallocHost(reinterpret_cast<void **>(&ptr), need * sizeof(T)), what);
    capacity = need;
}

void build_segment_mass_device(const sv_t &sv, size_t segment_len,
                               size_t segment_count, float_t *device_mass)
{
    const size_t local_size = static_cast<size_t>(sv.block_end - sv.block_start);

    if (segment_len == 0)
        abort("build_segment_mass_device requires positive segment_len");
    if (segment_count == 0)
        abort("build_segment_mass_device requires positive segment_count");

    const auto *data = reinterpret_cast<const cuDoubleComplex *>(sv.raw_data());
    segment_mass_kernel<<<static_cast<unsigned int>(segment_count), kCudaThreads,
                          kCudaThreads * sizeof(double)>>>(data, local_size, segment_len,
                                                           device_mass);
    check_cuda(cudaGetLastError(), "segment_mass_kernel launch failed");
}

__device__ inline uint64_t splitmix64_device(uint64_t x)
{
    uint64_t z = x + 0x9e3779b97f4a7c15ULL;
    z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ULL;
    z = (z ^ (z >> 27)) * 0x94d049bb133111ebULL;
    return z ^ (z >> 31);
}

__device__ inline float_t uniform_open01_device(uint64_t seed)
{
    const uint64_t bits = splitmix64_device(seed);
    if constexpr (std::is_same_v<float_t, float>)
    {
        const uint32_t mant = static_cast<uint32_t>(bits >> 40);
        return (static_cast<float_t>(mant) + 1.0f) /
               (static_cast<float_t>(uint32_t(1) << 24) + 1.0f);
    }
    else
    {
        const uint64_t mant = bits >> 11;
        return (static_cast<float_t>(mant) + 1.0) /
               (static_cast<float_t>(uint64_t(1) << 53) + 1.0);
    }
}

__global__ void generate_segment_counts_kernel(const float_t *mass_cdf,
                                               size_t segment_count,
                                               uint64_t stream_seed,
                                               size_t shot_count,
                                               uint64_t *counts)
{
    const size_t idx = static_cast<size_t>(blockIdx.x) * static_cast<size_t>(blockDim.x) +
                       static_cast<size_t>(threadIdx.x);
    if (idx >= shot_count)
        return;

    const float_t total_mass = mass_cdf[segment_count - 1];
    if (total_mass <= 0.0f)
        return;

    const float_t u = uniform_open01_device(stream_seed ^ (0x510e527fade682d1ULL + idx));
    const float_t tau_global = u * total_mass;

    size_t lo = 0;
    size_t hi = segment_count;
    while (lo < hi)
    {
        const size_t mid = lo + (hi - lo) / 2;
        if (mass_cdf[mid] <= tau_global)
            lo = mid + 1;
        else
            hi = mid;
    }

    const size_t seg_idx = (lo >= segment_count) ? (segment_count - 1) : lo;
    atomicAdd(reinterpret_cast<unsigned long long *>(counts + seg_idx), 1ULL);
}

__global__ void resolve_multinomial_segments_kernel(const cuDoubleComplex *data,
                                                    size_t local_size,
                                                    size_t segment_len,
                                                    const uint64_t *counts,
                                                    const uint64_t *offsets,
                                                    uint64_t stream_seed,
                                                    raddr_t block_start,
                                                    raddr_t *results)
{
    extern __shared__ float_t shared[];
    float_t *cdf = shared;
    float_t *scratch = shared + segment_len;

    const size_t seg_idx = static_cast<size_t>(blockIdx.x);
    const uint64_t shot_count = counts[seg_idx];
    if (shot_count == 0)
        return;

    const size_t seg_begin = seg_idx * segment_len;
    if (seg_begin >= local_size)
        return;

    const size_t valid_count = min(segment_len, local_size - seg_begin);
    const size_t tid = static_cast<size_t>(threadIdx.x);

    for (size_t idx = tid; idx < valid_count; idx += static_cast<size_t>(blockDim.x))
    {
        const cuDoubleComplex v = data[seg_begin + idx];
        const float_t re = cuCreal(v);
        const float_t im = cuCimag(v);
        cdf[idx] = re * re + im * im;
    }
    __syncthreads();

    for (size_t step = 1; step < valid_count; step <<= 1)
    {
        for (size_t idx = tid; idx < valid_count; idx += static_cast<size_t>(blockDim.x))
            scratch[idx] = (idx >= step) ? cdf[idx - step] : 0.0f;
        __syncthreads();
        for (size_t idx = tid; idx < valid_count; idx += static_cast<size_t>(blockDim.x))
            cdf[idx] += scratch[idx];
        __syncthreads();
    }

    const float_t segment_total = cdf[valid_count - 1];
    if (segment_total <= 0.0f)
        return;

    const uint64_t output_begin = offsets[seg_idx];
    for (uint64_t local_shot = static_cast<uint64_t>(tid); local_shot < shot_count;
         local_shot += static_cast<uint64_t>(blockDim.x))
    {
        const uint64_t output_idx = output_begin + local_shot;
        const float_t u = uniform_open01_device(
            stream_seed ^ (0x9b05688c2b3e6c1fULL + output_idx));
        const float_t tau = u * segment_total;

        size_t lo = 0;
        size_t hi = valid_count;
        while (lo < hi)
        {
            const size_t mid = lo + (hi - lo) / 2;
            if (cdf[mid] <= tau)
                lo = mid + 1;
            else
                hi = mid;
        }

        const size_t hit = (lo >= valid_count) ? (valid_count - 1) : lo;
        results[output_idx] = block_start + static_cast<raddr_t>(seg_begin + hit);
    }
}

class local_sample_workspace_t
{
  public:
    ~local_sample_workspace_t()
    {
        if (device_counts_ != nullptr)
            check_cuda(cudaFree(device_counts_),
                       "local_sample_workspace_t cudaFree counts failed");
        if (device_offsets_ != nullptr)
            check_cuda(cudaFree(device_offsets_),
                       "local_sample_workspace_t cudaFree offsets failed");
        if (device_mass_cdf_ != nullptr)
            check_cuda(cudaFree(device_mass_cdf_),
                       "local_sample_workspace_t cudaFree mass_cdf failed");
        if (device_mass_ != nullptr)
            check_cuda(cudaFree(device_mass_),
                       "local_sample_workspace_t cudaFree mass failed");
        if (mass_scan_storage_ != nullptr)
            check_cuda(cudaFree(mass_scan_storage_),
                       "local_sample_workspace_t cudaFree mass scan storage failed");
        if (offset_scan_storage_ != nullptr)
            check_cuda(cudaFree(offset_scan_storage_),
                       "local_sample_workspace_t cudaFree offset scan storage failed");
    }

    void ensure(size_t segment_len, size_t segment_count)
    {
        if (segment_len == 0)
            abort("local_sample_workspace_t requires positive segment_len");

        ensure_device_capacity(device_mass_, device_mass_capacity_, segment_count,
                               "local_sample_workspace_t cudaMalloc device_mass failed");
        ensure_device_capacity(device_mass_cdf_, device_mass_cdf_capacity_, segment_count,
                               "local_sample_workspace_t cudaMalloc device_mass_cdf failed");

        if (segment_count > mass_scan_segment_capacity_)
        {
            size_t bytes = 0;
            check_cuda(cub::DeviceScan::InclusiveSum(nullptr, bytes, device_mass_,
                                                     device_mass_cdf_,
                                                     cub_num_items(segment_count,
                                                                   "local_sample_workspace_t segment_count")),
                       "local_sample_workspace_t mass scan storage query failed");
            if (mass_scan_storage_ != nullptr)
                check_cuda(cudaFree(mass_scan_storage_),
                           "local_sample_workspace_t cudaFree mass scan storage failed");
            mass_scan_storage_ = nullptr;
            mass_scan_storage_bytes_ = 0;
            if (bytes != 0)
                check_cuda(cudaMalloc(&mass_scan_storage_, bytes),
                           "local_sample_workspace_t cudaMalloc mass scan storage failed");
            mass_scan_storage_bytes_ = bytes;
            mass_scan_segment_capacity_ = segment_count;
        }

        ensure_device_capacity(device_counts_, device_counts_capacity_, segment_count,
                               "local_sample_workspace_t cudaMalloc counts failed");
        ensure_device_capacity(device_offsets_, device_offsets_capacity_, segment_count,
                               "local_sample_workspace_t cudaMalloc offsets failed");

        if (segment_count > offset_scan_segment_capacity_)
        {
            size_t bytes = 0;
            check_cuda(cub::DeviceScan::ExclusiveSum(nullptr, bytes, device_counts_,
                                                     device_offsets_,
                                                     cub_num_items(segment_count,
                                                                   "local_sample_workspace_t segment_count")),
                       "local_sample_workspace_t offset scan storage query failed");
            if (offset_scan_storage_ != nullptr)
                check_cuda(cudaFree(offset_scan_storage_),
                           "local_sample_workspace_t cudaFree offset scan storage failed");
            offset_scan_storage_ = nullptr;
            offset_scan_storage_bytes_ = 0;
            if (bytes != 0)
                check_cuda(cudaMalloc(&offset_scan_storage_, bytes),
                           "local_sample_workspace_t cudaMalloc offset scan storage failed");
            offset_scan_storage_bytes_ = bytes;
            offset_scan_segment_capacity_ = segment_count;
        }
    }

    float_t *device_mass() { return device_mass_; }
    float_t *device_mass_cdf() { return device_mass_cdf_; }
    uint64_t *device_counts() { return device_counts_; }
    uint64_t *device_offsets() { return device_offsets_; }
    void *mass_scan_storage() { return mass_scan_storage_; }
    size_t mass_scan_storage_bytes() const { return mass_scan_storage_bytes_; }
    void *offset_scan_storage() { return offset_scan_storage_; }
    size_t offset_scan_storage_bytes() const { return offset_scan_storage_bytes_; }

  private:
    float_t *device_mass_ = nullptr;
    size_t device_mass_capacity_ = 0;
    float_t *device_mass_cdf_ = nullptr;
    size_t device_mass_cdf_capacity_ = 0;
    uint64_t *device_counts_ = nullptr;
    size_t device_counts_capacity_ = 0;
    uint64_t *device_offsets_ = nullptr;
    size_t device_offsets_capacity_ = 0;
    void *mass_scan_storage_ = nullptr;
    size_t mass_scan_storage_bytes_ = 0;
    size_t mass_scan_segment_capacity_ = 0;
    void *offset_scan_storage_ = nullptr;
    size_t offset_scan_storage_bytes_ = 0;
    size_t offset_scan_segment_capacity_ = 0;
};

void prepare_multinomial_shared_memory(size_t shared_bytes)
{
    cudaDeviceProp prop{};
    int device = 0;
    check_cuda(cudaGetDevice(&device), "sample_segments_device cudaGetDevice failed");
    check_cuda(cudaGetDeviceProperties(&prop, device),
               "sample_segments_device cudaGetDeviceProperties failed");
    if (shared_bytes <= static_cast<size_t>(prop.sharedMemPerBlock))
        return;
    if (shared_bytes > static_cast<size_t>(prop.sharedMemPerBlockOptin))
        abort("multinomial measurement segment requires too much shared memory");
    check_cuda(cudaFuncSetAttribute(resolve_multinomial_segments_kernel,
                                    cudaFuncAttributeMaxDynamicSharedMemorySize,
                                    static_cast<int>(shared_bytes)),
               "sample_segments_device shared memory opt-in failed");
}

void sample_segments_device(const sv_t &sv, size_t result_count,
                            uint64_t stream_seed, local_sample_workspace_t &work,
                            raddr_t *device_results)
{
    const size_t segment_len = sampling_segment_len(sv);
    const size_t segment_count = sampling_segment_count(sv, segment_len);
    if (result_count == 0)
        return;
    if (segment_count == 0)
        abort("sample_segments_device requires positive segment_count");

    build_segment_mass_device(sv, segment_len, segment_count, work.device_mass());
    size_t mass_scan_bytes = work.mass_scan_storage_bytes();
    check_cuda(cub::DeviceScan::InclusiveSum(work.mass_scan_storage(),
                                             mass_scan_bytes,
                                             work.device_mass(),
                                             work.device_mass_cdf(),
                                             cub_num_items(segment_count,
                                                           "sample_segments_device segment_count")),
               "sample_segments_device mass scan failed");

    check_cuda(cudaMemset(work.device_counts(), 0, segment_count * sizeof(uint64_t)),
               "sample_segments_device multinomial count memset failed");
    generate_segment_counts_kernel<<<calc_blocks(result_count), kCudaThreads>>>(
        work.device_mass_cdf(), segment_count, stream_seed, result_count,
        work.device_counts());
    check_cuda(cudaGetLastError(),
               "sample_segments_device generate_segment_counts_kernel failed");

    size_t offset_scan_bytes = work.offset_scan_storage_bytes();
    check_cuda(cub::DeviceScan::ExclusiveSum(work.offset_scan_storage(),
                                             offset_scan_bytes,
                                             work.device_counts(),
                                             work.device_offsets(),
                                             cub_num_items(segment_count,
                                                           "sample_segments_device segment_count")),
               "sample_segments_device multinomial offset scan failed");

    const size_t shared_bytes = 2 * segment_len * sizeof(float_t);
    prepare_multinomial_shared_memory(shared_bytes);

    const auto *data = reinterpret_cast<const cuDoubleComplex *>(sv.raw_data());
    resolve_multinomial_segments_kernel<<<static_cast<unsigned int>(segment_count),
                                          kCudaThreads, shared_bytes>>>(
        data, static_cast<size_t>(sv.block_end - sv.block_start), segment_len,
        work.device_counts(), work.device_offsets(), mix_seed(stream_seed, 1),
        sv.block_start, device_results);
    check_cuda(cudaGetLastError(),
               "sample_segments_device resolve_multinomial_segments_kernel failed");
}

} // namespace

struct measure_cache_t::impl_t
{
    size_t real_capacity = 0;
    raddr_t *device_real_results = nullptr;

    size_t device_packed_word_capacity = 0;
    uint64_t *device_packed_results = nullptr;
    size_t host_packed_word_capacity = 0;
    uint64_t *host_packed_results = nullptr;

    size_t row_capacity = 0;
    uint64_t *device_rows = nullptr;
    size_t b_word_capacity = 0;
    uint64_t *device_b_words = nullptr;

    size_t reduce_buf0_capacity = 0;
    double *reduce_buf0 = nullptr;
    size_t reduce_buf1_capacity = 0;
    double *reduce_buf1 = nullptr;

    std::vector<uint64_t> host_rows;
    std::vector<uint64_t> host_b_words;
    local_sample_workspace_t sample_workspace;
    bool mapping_dirty = true;
};

namespace
{

double reduce_prob_sum_device(const cuDoubleComplex *data, size_t n,
                              double *&buf0, size_t &buf0_capacity,
                              double *&buf1, size_t &buf1_capacity)
{
    const size_t partial_count = (n + kReduceChunkElems - 1) / kReduceChunkElems;
    ensure_device_capacity(buf0, buf0_capacity, partial_count,
                           "sum_block_prob partial cudaMalloc failed");

    sum_prob_partial_kernel<<<static_cast<unsigned int>(partial_count), kCudaThreads,
                              kCudaThreads * sizeof(double)>>>(data, n, buf0);
    check_cuda(cudaGetLastError(), "sum_prob_partial_kernel launch failed");

    double *src = buf0;
    if (partial_count > 1)
    {
        ensure_device_capacity(buf1, buf1_capacity, partial_count,
                               "sum_block_prob partial scratch cudaMalloc failed");

        size_t cur_count = partial_count;
        double *dst = buf1;
        while (cur_count > 1)
        {
            const size_t next_count = (cur_count + kReduceChunkElems - 1) / kReduceChunkElems;
            reduce_double_partial_kernel<<<static_cast<unsigned int>(next_count), kCudaThreads,
                                           kCudaThreads * sizeof(double)>>>(src, cur_count, dst);
            check_cuda(cudaGetLastError(),
                       "reduce_double_partial_kernel launch failed");
            cur_count = next_count;
            std::swap(src, dst);
        }
    }

    double total = 0.0;
    check_cuda(cudaMemcpy(&total, src, sizeof(double), cudaMemcpyDeviceToHost),
               "sum_block_prob copy failed");
    return total;
}

} // namespace

struct segment_cdf_t::impl_t
{
    size_t segment_len = 0;
    size_t storage_elems = 0;
    val_t *host_storage = nullptr;
    val_t *device_storage = nullptr;
    float_t *host_cdf = nullptr;
    float_t *device_cdf = nullptr;
    float_t cdf_head_out = 0.0;
    float_t segment_total = 0.0;
    float_t *device_total = nullptr;
    void *device_scan_storage = nullptr;
    size_t scan_storage_bytes = 0;
};

segment_cdf_t::segment_cdf_t(size_t segment_len) : impl_(std::make_unique<impl_t>())
{
    impl_->segment_len = segment_len;
    impl_->storage_elems = cdf_storage_elems(segment_len);
    impl_->host_storage = host_alloc(impl_->storage_elems);
    impl_->device_storage = worker_alloc(impl_->storage_elems);
    impl_->host_cdf = reinterpret_cast<float_t *>(impl_->host_storage);
    impl_->device_cdf = reinterpret_cast<float_t *>(impl_->device_storage);
    check_cuda(cudaMalloc(reinterpret_cast<void **>(&impl_->device_total), sizeof(float_t)),
               "segment_cdf_t cudaMalloc device_total failed");
    auto dummy_probs = thrust::make_transform_iterator(
        static_cast<const cuDoubleComplex *>(nullptr), amplitude_prob_op_t{});
    check_cuda(cub::DeviceScan::InclusiveSum(nullptr, impl_->scan_storage_bytes, dummy_probs,
                                             static_cast<float_t *>(nullptr),
                                             cub_num_items(segment_len, "segment_cdf_t segment_len")),
               "segment_cdf_t CUB temp storage query failed");
    if (impl_->scan_storage_bytes != 0)
    {
        check_cuda(cudaMalloc(&impl_->device_scan_storage, impl_->scan_storage_bytes),
                   "segment_cdf_t cudaMalloc scan storage failed");
    }
}

segment_cdf_t::~segment_cdf_t()
{
    if (impl_ == nullptr)
        return;
    host_free(impl_->host_storage);
    worker_free(impl_->device_storage);
    check_cuda(cudaFree(impl_->device_total), "segment_cdf_t cudaFree device_total failed");
    if (impl_->device_scan_storage != nullptr)
        check_cuda(cudaFree(impl_->device_scan_storage), "segment_cdf_t cudaFree scan storage failed");
    impl_->host_storage = nullptr;
    impl_->device_storage = nullptr;
    impl_->host_cdf = nullptr;
    impl_->device_cdf = nullptr;
    impl_->device_total = nullptr;
    impl_->device_scan_storage = nullptr;
}

void segment_cdf_t::pre_cdf(const sv_t &sv, raddr_t seg, float_t cdf_head_in)
{
    const size_t valid_count = valid_segment_len(sv, seg, impl_->segment_len);
    if (valid_count == 0)
    {
        impl_->cdf_head_out = cdf_head_in;
        impl_->segment_total = 0.0;
        return;
    }

    const size_t offset = static_cast<size_t>(seg - sv.block_start);
    const auto *src = reinterpret_cast<const cuDoubleComplex *>(sv.raw_data() + offset);
    auto probs = thrust::make_transform_iterator(src, amplitude_prob_op_t{});
    check_cuda(cub::DeviceScan::InclusiveSum(impl_->device_scan_storage, impl_->scan_storage_bytes,
                                             probs, impl_->device_cdf,
                                             cub_num_items(valid_count, "segment_cdf_t valid_count")),
               "segment_cdf_t CUB inclusive sum failed");

    segment_cdf_finalize_kernel<<<calc_blocks(valid_count), kCudaThreads>>>(
        impl_->device_cdf, valid_count, cdf_head_in, impl_->device_total);
    check_cuda(cudaGetLastError(), "segment_cdf_finalize_kernel launch failed");
    check_cuda(cudaMemcpy(impl_->host_cdf, impl_->device_cdf,
                          valid_count * sizeof(float_t), cudaMemcpyDeviceToHost),
               "segment_cdf_t copy failed");
    check_cuda(cudaMemcpy(&impl_->segment_total, impl_->device_total, sizeof(float_t),
                          cudaMemcpyDeviceToHost),
               "segment_cdf_t total copy failed");

    impl_->cdf_head_out = impl_->host_cdf[valid_count - 1];
}

const float_t *segment_cdf_t::wait_cdf(float_t &cdf_head_out)
{
    cdf_head_out = impl_->cdf_head_out;
    return impl_->host_cdf;
}

float_t segment_cdf_t::segment_sum() const
{
    return impl_->segment_total;
}

void segment_cdf_t::release()
{
}

measure_cache_t::measure_cache_t(size_t nbits)
    : nbits_(nbits), result_count_(0), impl_(std::make_unique<impl_t>())
{
}

measure_cache_t::~measure_cache_t()
{
    if (impl_ == nullptr)
        return;
    if (impl_->reduce_buf1 != nullptr)
        check_cuda(cudaFree(impl_->reduce_buf1), "measure_cache_t cudaFree reduce_buf1 failed");
    if (impl_->reduce_buf0 != nullptr)
        check_cuda(cudaFree(impl_->reduce_buf0), "measure_cache_t cudaFree reduce_buf0 failed");
    if (impl_->device_b_words != nullptr)
        check_cuda(cudaFree(impl_->device_b_words), "measure_cache_t cudaFree device_b_words failed");
    if (impl_->device_rows != nullptr)
        check_cuda(cudaFree(impl_->device_rows), "measure_cache_t cudaFree device_rows failed");
    if (impl_->host_packed_results != nullptr)
        check_cuda(cudaFreeHost(impl_->host_packed_results),
                   "measure_cache_t cudaFreeHost host_packed_results failed");
    if (impl_->device_packed_results != nullptr)
        check_cuda(cudaFree(impl_->device_packed_results),
                   "measure_cache_t cudaFree device_packed_results failed");
    if (impl_->device_real_results != nullptr)
        check_cuda(cudaFree(impl_->device_real_results),
                   "measure_cache_t cudaFree device_real_results failed");
}

size_t measure_cache_t::nbits() const
{
    return nbits_;
}

size_t measure_cache_t::result_count() const
{
    return result_count_;
}

void measure_cache_t::invalidate_mapping()
{
    result_count_ = 0;
    impl_->mapping_dirty = true;
}

void measure_cache_t::ensure_capacity(const sv_t &sv, size_t local_count, size_t global_count)
{
    const size_t word_count = detail::result_word_count(nbits_);
    ensure_device_capacity(impl_->device_real_results, impl_->real_capacity, global_count,
                           "measure_cache_t cudaMalloc device_real_results failed");
    ensure_device_capacity(impl_->device_packed_results, impl_->device_packed_word_capacity,
                           global_count * word_count,
                           "measure_cache_t cudaMalloc device_packed_results failed");
    ensure_host_pinned_capacity(impl_->host_packed_results, impl_->host_packed_word_capacity,
                                global_count * word_count,
                                "measure_cache_t cudaMallocHost host_packed_results failed");
    ensure_device_capacity(impl_->device_rows, impl_->row_capacity, nbits_,
                           "measure_cache_t cudaMalloc device_rows failed");
    ensure_device_capacity(impl_->device_b_words, impl_->b_word_capacity, word_count,
                           "measure_cache_t cudaMalloc device_b_words failed");

    if (local_count != 0)
    {
        const size_t segment_len = sampling_segment_len(sv);
        const size_t segment_count = sampling_segment_count(sv, segment_len);
        impl_->sample_workspace.ensure(segment_len, segment_count);
    }
}

void measure_cache_t::sample_local(const sv_t &sv, float_t local_prob, size_t local_count,
                                   uint64_t stream_seed)
{
    if (local_count == 0)
        return;

    (void)local_prob;
    sample_segments_device(sv, local_count, stream_seed, impl_->sample_workspace,
                           impl_->device_real_results);
}

void measure_cache_t::gather_results(size_t local_count, size_t global_count)
{
    if (global_count == 0)
        return;
    if (local_count != global_count)
        abort("measure_cache_t::gather_results count mismatch");
}

void measure_cache_t::finalize_results(const bitmat_t &A, const bitvec_t &b, size_t count)
{
    const size_t word_count = detail::result_word_count(nbits_);
    if (count == 0 || word_count == 0)
        return;

    if (impl_->mapping_dirty)
    {
        impl_->host_rows.resize(nbits_);
        for (size_t q = 0; q < nbits_; q++)
            impl_->host_rows[q] = A.get_row(q);

        impl_->host_b_words.assign(word_count, 0ULL);
        for (size_t q = 0; q < nbits_; q++)
        {
            if (b.get_bit(q))
                impl_->host_b_words[q >> 6] |= (1ULL << (q & 63));
        }

        check_cuda(cudaMemcpy(impl_->device_rows, impl_->host_rows.data(),
                              nbits_ * sizeof(uint64_t), cudaMemcpyHostToDevice),
                   "measure_cache_t row copy failed");
        check_cuda(cudaMemcpy(impl_->device_b_words, impl_->host_b_words.data(),
                              word_count * sizeof(uint64_t), cudaMemcpyHostToDevice),
                   "measure_cache_t b copy failed");
        impl_->mapping_dirty = false;
    }

    map_real_to_virtual_words_kernel<<<calc_blocks(count), kCudaThreads>>>(
        impl_->device_real_results, count, impl_->device_rows, impl_->device_b_words, nbits_,
        word_count, impl_->device_packed_results);
    check_cuda(cudaGetLastError(), "measure_cache_t map_real_to_virtual_words_kernel failed");
}

void measure_cache_t::copy_results_to_host(res_t *results, size_t count) const
{
    const size_t word_count = detail::result_word_count(nbits_);
    if (count == 0 || word_count == 0)
        return;
    check_cuda(cudaMemcpy(impl_->host_packed_results, impl_->device_packed_results,
                          count * word_count * sizeof(uint64_t), cudaMemcpyDeviceToHost),
               "measure_cache_t packed result copy failed");
    detail::unpack_virtual_results_host(impl_->host_packed_results, count, nbits_, results);
}

void measure_cache_t::set_result_count(size_t count)
{
    result_count_ = count;
}

float_t sum_block_prob(const sv_t &sv, measure_cache_t &cache)
{
    const size_t local_size = static_cast<size_t>(sv.block_end - sv.block_start);
    if (local_size == 0)
        return 0.0;

    const auto *data = reinterpret_cast<const cuDoubleComplex *>(sv.raw_data());
    return reduce_prob_sum_device(data, local_size, cache.impl_->reduce_buf0,
                                  cache.impl_->reduce_buf0_capacity,
                                  cache.impl_->reduce_buf1,
                                  cache.impl_->reduce_buf1_capacity);
}

prob_scan_t scan_block_prob(const sv_t &sv, measure_cache_t &cache)
{
    prob_scan_t scan;
    (void)sv;
    (void)cache;
    scan.local_prob = 1.0;
    scan.prob_prefix = 0.0;
    scan.global_total = 1.0;
    return scan;
}

measure_plan_t make_measure_plan(size_t cnt, const prob_scan_t &prob_scan,
                                 bool use_seed, uint64_t seed)
{
    measure_plan_t plan;
    plan.global_total = prob_scan.global_total;
    plan.prob_prefix = prob_scan.prob_prefix;
    plan.cnt_local = cnt;
    plan.stream_seed = mix_seed(choose_base_seed(use_seed, seed), 0);
    return plan;
}

} // namespace ZXHSim
