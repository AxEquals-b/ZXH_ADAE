#include "zxhsim/kernels.h"
#include "zxhsim/runtime.h"
#include "zxhsim/utils.h"
#include <iostream>

#include <cuComplex.h>
#include <cooperative_groups.h>
#include <cuda_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <cstdlib>
#include <string>
#include <type_traits>
#include <vector>

namespace ZXHSim
{

static_assert(std::is_same_v<float_t, float> || std::is_same_v<float_t, double>, "float_t must be float or double");
template <typename T>
struct cu_ops_t;

template <>
struct cu_ops_t<float>
{
    using complex_t = cuFloatComplex;
    __host__ __device__ static inline complex_t make(float re, float im)
    {
        return make_cuFloatComplex(re, im);
    }
    __host__ __device__ static inline float real(complex_t v)
    {
        return cuCrealf(v);
    }
    __host__ __device__ static inline float imag(complex_t v)
    {
        return cuCimagf(v);
    }
};

template <>
struct cu_ops_t<double>
{
    using complex_t = cuDoubleComplex;
    __host__ __device__ static inline complex_t make(double re, double im)
    {
        return make_cuDoubleComplex(re, im);
    }
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

__host__ __device__ inline device_complex_t zx_make_complex(float_t re, float_t im)
{
    return cu_ops_t<float_t>::make(re, im);
}

__host__ __device__ inline float_t zx_real(device_complex_t v)
{
    return cu_ops_t<float_t>::real(v);
}

__host__ __device__ inline float_t zx_imag(device_complex_t v)
{
    return cu_ops_t<float_t>::imag(v);
}

#define cuDoubleComplex device_complex_t
#define make_cuDoubleComplex zx_make_complex
#define cuCreal zx_real
#define cuCimag zx_imag

namespace
{
constexpr int kCudaThreads = 256;
constexpr int kDiagLaneBits = 8;
constexpr int kDiagSliceTile = 4;
constexpr raddr_t kDiagLaneMask = 0xffULL;
constexpr size_t kDiagIrWordCap = 6144;
constexpr size_t kU3BatchMaxDesc = 63;
__constant__ uint64_t g_diag_ir_words[kDiagIrWordCap];
__constant__ u3_batch_desc_t g_u3_batch_desc[kU3BatchMaxDesc];

enum class selector_class_t
{
    low,
    high,
    cross,
};

struct diag1_desc_t
{
    uint64_t sel;
    float_t theta;
};

struct diag2_desc_t
{
    uint64_t sel0;
    uint64_t sel1;
    float_t theta;
};

struct diag_chunk_counts_t
{
    uint32_t cnt_p_l = 0;
    uint32_t cnt_p_h = 0;
    uint32_t cnt_p_x = 0;
    uint32_t cnt_cp_ll = 0;
    uint32_t cnt_cp_hh = 0;
    uint32_t cnt_cp_hl = 0;
};

struct diag_chunk_cursor_t
{
    size_t p_l = 0;
    size_t p_h = 0;
    size_t p_x = 0;
    size_t cp_ll = 0;
    size_t cp_hh = 0;
    size_t cp_hl = 0;
};

std::vector<diag1_desc_t> g_diag_p_l;
std::vector<diag1_desc_t> g_diag_p_h;
std::vector<diag1_desc_t> g_diag_p_x;
std::vector<diag2_desc_t> g_diag_cp_ll;
std::vector<diag2_desc_t> g_diag_cp_hh;
std::vector<diag2_desc_t> g_diag_cp_hl;
std::vector<uint64_t> g_diag_ir_host;
size_t g_diag_ir_word_cap_runtime = kDiagIrWordCap;
bool g_diag_ir_word_cap_initialized = false;

int calc_blocks(size_t n)
{
    return static_cast<int>((n + static_cast<size_t>(kCudaThreads) - 1) / static_cast<size_t>(kCudaThreads));
}

int calc_diag_blocks(size_t n)
{
    const size_t slice_count = (n + static_cast<size_t>(kCudaThreads) - 1) >> kDiagLaneBits;
    return static_cast<int>((slice_count + static_cast<size_t>(kDiagSliceTile) - 1) /
                            static_cast<size_t>(kDiagSliceTile));
}

void check_cuda(cudaError_t err, const char *what)
{
    if (err == cudaSuccess)
        return;
    abort(std::string(what) + ": " + cudaGetErrorString(err));
}

void check_launch(const char *where)
{
    cudaError_t err = cudaGetLastError();
    if (err != cudaSuccess)
        abort(std::string(where) + " launch failed: " + cudaGetErrorString(err));
}

size_t diag_ir_word_cap_runtime()
{
    if (g_diag_ir_word_cap_initialized)
        return g_diag_ir_word_cap_runtime;

    const char *env = std::getenv("ZXHSIM_DIAG_IR_WORD_CAP");
    if (env != nullptr && env[0] != '\0')
    {
        char *end = nullptr;
        const unsigned long long parsed = std::strtoull(env, &end, 10);
        if (end == env || *end != '\0')
            abort(std::string("invalid ZXHSIM_DIAG_IR_WORD_CAP: ") + env);
        if (parsed == 0 || parsed > static_cast<unsigned long long>(kDiagIrWordCap))
            abort("ZXHSIM_DIAG_IR_WORD_CAP must be in [1, 6144]");
        g_diag_ir_word_cap_runtime = static_cast<size_t>(parsed);
    }

    g_diag_ir_word_cap_initialized = true;
    return g_diag_ir_word_cap_runtime;
}

cuDoubleComplex to_cu(val_t v)
{
    return make_cuDoubleComplex(v.real(), v.imag());
}

__device__ inline bool selector_eval(uint64_t alpha, bool beta, uint64_t x)
{
    const bool parity = (__popcll(static_cast<unsigned long long>(x & alpha)) & 1ULL) != 0;
    return parity != beta;
}

__device__ inline bool selector_eval_packed(uint64_t packed, uint64_t x)
{
    // selector_t packs beta in bit63 and alpha in bits[0..62].
    // With local_bits <= 63, x never touches bit63, so parity(x & packed)
    // equals parity(x & alpha). XOR with packed>>63 applies beta.
    const unsigned long long parity = __popcll(static_cast<unsigned long long>(x & packed)) & 1ULL;
    return (parity ^ static_cast<unsigned long long>(packed >> 63)) != 0ULL;
}

__device__ inline cuDoubleComplex c_add(cuDoubleComplex a, cuDoubleComplex b)
{
    return make_cuDoubleComplex(cuCreal(a) + cuCreal(b), cuCimag(a) + cuCimag(b));
}

__device__ inline cuDoubleComplex c_mul(cuDoubleComplex a, cuDoubleComplex b)
{
    return make_cuDoubleComplex(cuCreal(a) * cuCreal(b) - cuCimag(a) * cuCimag(b),
                                cuCreal(a) * cuCimag(b) + cuCimag(a) * cuCreal(b));
}

selector_class_t classify_selector(selector_t sel)
{
    const raddr_t alpha = sel.alpha();
    const raddr_t alpha_low = alpha & kDiagLaneMask;
    const raddr_t alpha_high = alpha >> 8;
    if (alpha_high == 0)
        return selector_class_t::low;
    if (alpha_low == 0)
        return selector_class_t::high;
    return selector_class_t::cross;
}

uint64_t pack_selector(selector_t sel)
{
    return sel.alpha() | (sel.beta() ? (1ULL << 63) : 0ULL);
}

uint64_t pack_theta_bits(float_t theta)
{
    if constexpr (std::is_same_v<float_t, float>)
    {
        uint32_t bits = 0;
        std::memcpy(&bits, &theta, sizeof(bits));
        return static_cast<uint64_t>(bits);
    }
    else
    {
        uint64_t bits = 0;
        std::memcpy(&bits, &theta, sizeof(bits));
        return bits;
    }
}

__device__ inline float_t unpack_theta_bits(uint64_t bits)
{
    if constexpr (std::is_same_v<float_t, float>)
        return __uint_as_float(static_cast<uint32_t>(bits));
    else
        return __longlong_as_double(static_cast<unsigned long long>(bits));
}

__host__ __device__ inline float_t zx_cos(float_t x)
{
    if constexpr (std::is_same_v<float_t, float>)
        return cosf(x);
    else
        return cos(x);
}

__host__ __device__ inline float_t zx_sin(float_t x)
{
    if constexpr (std::is_same_v<float_t, float>)
        return sinf(x);
    else
        return sin(x);
}

bool any_diag_pending()
{
    return !g_diag_p_l.empty() || !g_diag_p_h.empty() || !g_diag_p_x.empty() || !g_diag_cp_ll.empty() ||
           !g_diag_cp_hh.empty() || !g_diag_cp_hl.empty();
}

selector_t unpack_selector(uint64_t packed)
{
    return selector_t(packed & ((uint64_t(1) << 63) - 1), ((packed >> 63) & 1ULL) != 0);
}

bool supports_cooperative_launch()
{
    int supported = 0;
    check_cuda(cudaDeviceGetAttribute(&supported, cudaDevAttrCooperativeLaunch, 0),
               "cudaDeviceGetAttribute(cooperativeLaunch) failed");
    return supported != 0;
}

template <typename DescT>
bool append_diag_bucket(std::vector<uint64_t> &ir_words, const std::vector<DescT> &bucket, size_t &cursor,
                        uint32_t &count, size_t words_per_desc, size_t word_cap)
{
    bool changed = false;
    while (cursor < bucket.size() && ir_words.size() + words_per_desc <= word_cap)
    {
        if constexpr (std::is_same_v<DescT, diag1_desc_t>)
        {
            ir_words.push_back(bucket[cursor].sel);
            ir_words.push_back(pack_theta_bits(bucket[cursor].theta));
        }
        else
        {
            ir_words.push_back(bucket[cursor].sel0);
            ir_words.push_back(bucket[cursor].sel1);
            ir_words.push_back(pack_theta_bits(bucket[cursor].theta));
        }
        cursor++;
        count++;
        changed = true;
    }
    return changed;
}

bool build_diag_chunk(diag_chunk_cursor_t &cursor, diag_chunk_counts_t &counts)
{
    g_diag_ir_host.clear();
    counts = {};
    const size_t word_cap = diag_ir_word_cap_runtime();

    append_diag_bucket(g_diag_ir_host, g_diag_p_l, cursor.p_l, counts.cnt_p_l, 2, word_cap);
    append_diag_bucket(g_diag_ir_host, g_diag_p_h, cursor.p_h, counts.cnt_p_h, 2, word_cap);
    append_diag_bucket(g_diag_ir_host, g_diag_p_x, cursor.p_x, counts.cnt_p_x, 2, word_cap);
    append_diag_bucket(g_diag_ir_host, g_diag_cp_ll, cursor.cp_ll, counts.cnt_cp_ll, 3, word_cap);
    append_diag_bucket(g_diag_ir_host, g_diag_cp_hh, cursor.cp_hh, counts.cnt_cp_hh, 3, word_cap);
    append_diag_bucket(g_diag_ir_host, g_diag_cp_hl, cursor.cp_hl, counts.cnt_cp_hl, 3, word_cap);

    return !g_diag_ir_host.empty();
}

bool diag_chunks_done(const diag_chunk_cursor_t &cursor)
{
    return cursor.p_l == g_diag_p_l.size() && cursor.p_h == g_diag_p_h.size() && cursor.p_x == g_diag_p_x.size() &&
           cursor.cp_ll == g_diag_cp_ll.size() && cursor.cp_hh == g_diag_cp_hh.size() &&
           cursor.cp_hl == g_diag_cp_hl.size();
}

__global__ void u3_block_kernel_cuda(cuDoubleComplex *ptr1, size_t n, size_t delta, uint64_t alpha, bool beta,
                                     cuDoubleComplex u00, cuDoubleComplex u01, cuDoubleComplex u10, cuDoubleComplex u11)
{
    const size_t i = blockIdx.x * static_cast<size_t>(blockDim.x) + threadIdx.x;
    if (i >= n)
        return;
    if (selector_eval(alpha, beta, i))
        return;

    const size_t j = i ^ delta;

    const cuDoubleComplex even = ptr1[i];
    const cuDoubleComplex odd = ptr1[j];
    ptr1[i] = c_add(c_mul(u00, even), c_mul(u01, odd));
    ptr1[j] = c_add(c_mul(u10, even), c_mul(u11, odd));
}

__global__ void u3_intra_kernel_cuda(cuDoubleComplex *ptr1, cuDoubleComplex *ptr2, size_t n, size_t delta,
                                     uint64_t alpha, bool beta, cuDoubleComplex u00, cuDoubleComplex u01,
                                     cuDoubleComplex u10, cuDoubleComplex u11)
{
    const size_t i = blockIdx.x * static_cast<size_t>(blockDim.x) + threadIdx.x;
    if (i >= n)
        return;
    const size_t j = i ^ delta;

    const bool first_is_even = !selector_eval(alpha, beta, i);
    const cuDoubleComplex even = first_is_even ? ptr1[i] : ptr2[j];
    const cuDoubleComplex odd = first_is_even ? ptr2[j] : ptr1[i];
    const cuDoubleComplex even_new = c_add(c_mul(u00, even), c_mul(u01, odd));
    const cuDoubleComplex odd_new = c_add(c_mul(u10, even), c_mul(u11, odd));

    if (first_is_even)
    {
        ptr1[i] = even_new;
        ptr2[j] = odd_new;
    }
    else
    {
        ptr2[j] = even_new;
        ptr1[i] = odd_new;
    }
}

__global__ void u3_block_batch_kernel_cuda(cuDoubleComplex *ptr1, size_t n, size_t gate_count)
{
    namespace cg = cooperative_groups;
    cg::grid_group grid = cg::this_grid();
    const size_t tid = blockIdx.x * static_cast<size_t>(blockDim.x) + threadIdx.x;
    const size_t stride = static_cast<size_t>(blockDim.x) * static_cast<size_t>(gridDim.x);

    for (size_t g = 0; g < gate_count; g++)
    {
        const u3_batch_desc_t desc = g_u3_batch_desc[g];
        const size_t delta = static_cast<size_t>(desc.delta_so);
        const cuDoubleComplex u00 = make_cuDoubleComplex(desc.u00_re, desc.u00_im);
        const cuDoubleComplex u01 = make_cuDoubleComplex(desc.u01_re, desc.u01_im);
        const cuDoubleComplex u10 = make_cuDoubleComplex(desc.u10_re, desc.u10_im);
        const cuDoubleComplex u11 = make_cuDoubleComplex(desc.u11_re, desc.u11_im);

        for (size_t off = tid; off < n; off += stride)
        {
            if (selector_eval_packed(desc.packed_sel, off))
                continue;

            const size_t j = off ^ delta;
            if (j >= n)
                continue;

            const cuDoubleComplex even = ptr1[off];
            const cuDoubleComplex odd = ptr1[j];
            ptr1[off] = c_add(c_mul(u00, even), c_mul(u01, odd));
            ptr1[j] = c_add(c_mul(u10, even), c_mul(u11, odd));
        }

        grid.sync();
    }
}

__global__ void u3_inter_kernel_cuda(cuDoubleComplex *ptr1, const cuDoubleComplex *ptr2, size_t n, size_t delta,
                                     uint64_t alpha, bool beta, cuDoubleComplex u00, cuDoubleComplex u01,
                                     cuDoubleComplex u10, cuDoubleComplex u11)
{
    const size_t i = blockIdx.x * static_cast<size_t>(blockDim.x) + threadIdx.x;
    if (i >= n)
        return;
    const size_t j = i ^ delta;

    const cuDoubleComplex local = ptr1[i];
    const cuDoubleComplex remote = ptr2[j];
    if (!selector_eval(alpha, beta, i))
        ptr1[i] = c_add(c_mul(u00, local), c_mul(u01, remote));
    else
        ptr1[i] = c_add(c_mul(u10, remote), c_mul(u11, local));
}

__global__ void x_block_kernel_cuda(cuDoubleComplex *ptr, size_t n, size_t delta, uint64_t alpha, bool beta)
{
    const size_t off = blockIdx.x * static_cast<size_t>(blockDim.x) + threadIdx.x;
    if (off >= n)
        return;
    if (selector_eval(alpha, beta, off))
        return;

    const size_t peer = off ^ delta;
    if (peer >= n)
        return;

    const cuDoubleComplex tmp = ptr[off];
    ptr[off] = ptr[peer];
    ptr[peer] = tmp;
}

__global__ void cx_block_kernel_cuda(cuDoubleComplex *ptr, size_t n, size_t delta, uint64_t alpha_cq, bool beta_cq,
                                     uint64_t alpha_q, bool beta_q)
{
    const size_t off = blockIdx.x * static_cast<size_t>(blockDim.x) + threadIdx.x;
    if (off >= n)
        return;
    if (selector_eval(alpha_q, beta_q, off))
        return;
    if (!selector_eval(alpha_cq, beta_cq, off))
        return;

    const size_t peer = off ^ delta;
    if (peer >= n)
        return;

    const cuDoubleComplex tmp = ptr[off];
    ptr[off] = ptr[peer];
    ptr[peer] = tmp;
}

__global__ void p_block_kernel_cuda(cuDoubleComplex *ptr, size_t n, uint64_t alpha, bool beta, float_t phase_re,
                                    float_t phase_im)
{
    const size_t off = blockIdx.x * static_cast<size_t>(blockDim.x) + threadIdx.x;
    if (off >= n)
        return;
    if (!selector_eval(alpha, beta, off))
        return;

    const cuDoubleComplex ph = make_cuDoubleComplex(phase_re, phase_im);
    ptr[off] = c_mul(ptr[off], ph);
}

__global__ void cp_kernel_cuda(cuDoubleComplex *ptr, size_t n, uint64_t alpha_cq, bool beta_cq, uint64_t alpha_q,
                               bool beta_q, float_t phase_re, float_t phase_im)
{
    const size_t off = blockIdx.x * static_cast<size_t>(blockDim.x) + threadIdx.x;
    if (off >= n)
        return;
    if (!selector_eval(alpha_cq, beta_cq, off) || !selector_eval(alpha_q, beta_q, off))
        return;

    const cuDoubleComplex ph = make_cuDoubleComplex(phase_re, phase_im);
    ptr[off] = c_mul(ptr[off], ph);
}

__global__ void diag_block_kernel_cuda(cuDoubleComplex *ptr, size_t n, diag_chunk_counts_t counts)
{
    const size_t base_p_l = 0;
    const size_t base_p_h = base_p_l + static_cast<size_t>(counts.cnt_p_l) * 2;
    const size_t base_p_x = base_p_h + static_cast<size_t>(counts.cnt_p_h) * 2;
    const size_t base_cp_ll = base_p_x + static_cast<size_t>(counts.cnt_p_x) * 2;
    const size_t base_cp_hh = base_cp_ll + static_cast<size_t>(counts.cnt_cp_ll) * 3;
    const size_t base_cp_hl = base_cp_hh + static_cast<size_t>(counts.cnt_cp_hh) * 3;

    const uint64_t lane = static_cast<uint64_t>(threadIdx.x) & kDiagLaneMask;
    const size_t first_slice = static_cast<size_t>(blockIdx.x) * static_cast<size_t>(kDiagSliceTile);
    const size_t slice_count = (n + static_cast<size_t>(kCudaThreads) - 1) >> kDiagLaneBits;

    __shared__ float_t sh_theta_high[kDiagSliceTile];
    if (threadIdx.x < kDiagSliceTile)
    {
        const size_t tile = static_cast<size_t>(threadIdx.x);
        const size_t slice_idx = first_slice + tile;
        float_t theta_high = 0.0;
        if (slice_idx < slice_count)
        {
            const uint64_t slice = static_cast<uint64_t>(slice_idx) << kDiagLaneBits;
            size_t base = base_p_h;
            for (uint32_t i = 0; i < counts.cnt_p_h; i++, base += 2)
            {
                if (selector_eval_packed(g_diag_ir_words[base], slice))
                    theta_high += unpack_theta_bits(g_diag_ir_words[base + 1]);
            }
            base = base_cp_hh;
            for (uint32_t i = 0; i < counts.cnt_cp_hh; i++, base += 3)
            {
                if (selector_eval_packed(g_diag_ir_words[base], slice) &&
                    selector_eval_packed(g_diag_ir_words[base + 1], slice))
                    theta_high += unpack_theta_bits(g_diag_ir_words[base + 2]);
            }
        }
        sh_theta_high[tile] = theta_high;
    }
    __syncthreads();

    float_t theta_lane = 0.0;
    size_t base = base_p_l;
    for (uint32_t i = 0; i < counts.cnt_p_l; i++, base += 2)
    {
        if (selector_eval_packed(g_diag_ir_words[base], lane))
            theta_lane += unpack_theta_bits(g_diag_ir_words[base + 1]);
    }
    base = base_cp_ll;
    for (uint32_t i = 0; i < counts.cnt_cp_ll; i++, base += 3)
    {
        if (selector_eval_packed(g_diag_ir_words[base], lane) && selector_eval_packed(g_diag_ir_words[base + 1], lane))
            theta_lane += unpack_theta_bits(g_diag_ir_words[base + 2]);
    }

    float_t theta_tile[kDiagSliceTile];
    uint64_t off_tile[kDiagSliceTile];
    uint64_t slice_tile[kDiagSliceTile];
    bool active_tile[kDiagSliceTile];

#pragma unroll
    for (int tile = 0; tile < kDiagSliceTile; tile++)
    {
        const size_t slice_idx = first_slice + static_cast<size_t>(tile);
        const uint64_t slice = static_cast<uint64_t>(slice_idx) << kDiagLaneBits;
        const uint64_t off = slice | lane;
        const bool active = static_cast<size_t>(off) < n;
        off_tile[tile] = off;
        slice_tile[tile] = slice;
        active_tile[tile] = active;
        theta_tile[tile] = active ? (theta_lane + sh_theta_high[tile]) : 0.0;
    }

    base = base_p_x;
    for (uint32_t i = 0; i < counts.cnt_p_x; i++, base += 2)
    {
        const uint64_t sel = g_diag_ir_words[base];
        const float_t theta = unpack_theta_bits(g_diag_ir_words[base + 1]);
#pragma unroll
        for (int tile = 0; tile < kDiagSliceTile; tile++)
        {
            if (active_tile[tile] && selector_eval_packed(sel, off_tile[tile]))
                theta_tile[tile] += theta;
        }
    }

    base = base_cp_hl;
    for (uint32_t i = 0; i < counts.cnt_cp_hl; i++, base += 3)
    {
        if (!selector_eval_packed(g_diag_ir_words[base], lane))
            continue;
        const uint64_t sel_high = g_diag_ir_words[base + 1];
        const float_t theta = unpack_theta_bits(g_diag_ir_words[base + 2]);
#pragma unroll
        for (int tile = 0; tile < kDiagSliceTile; tile++)
        {
            if (active_tile[tile] && selector_eval_packed(sel_high, slice_tile[tile]))
                theta_tile[tile] += theta;
        }
    }

#pragma unroll
    for (int tile = 0; tile < kDiagSliceTile; tile++)
    {
        const float_t theta_sum = theta_tile[tile];
        if (!active_tile[tile] || theta_sum == 0.0)
            continue;
        const cuDoubleComplex ph = make_cuDoubleComplex(zx_cos(theta_sum), zx_sin(theta_sum));
        ptr[off_tile[tile]] = c_mul(ptr[off_tile[tile]], ph);
    }
}

} // namespace

void kernel_sync()
{
    cudaError_t err = cudaDeviceSynchronize();
    if (err != cudaSuccess)
        abort(std::string("kernel_sync failed: ") + cudaGetErrorString(err));
}

void u3_block_kernel(val_t *ptr1, size_t local_bits, raddr_t delta_so, selector_t S_block, val_t u00, val_t u01,
                     val_t u10, val_t u11)
{
    const size_t n = size_t(1) << local_bits;
    auto *p1 = reinterpret_cast<cuDoubleComplex *>(ptr1);
    u3_block_kernel_cuda<<<calc_blocks(n), kCudaThreads>>>(p1, n, static_cast<size_t>(delta_so), S_block.alpha(),
                                                           S_block.beta(), to_cu(u00), to_cu(u01), to_cu(u10),
                                                           to_cu(u11));
    check_launch("u3_block_kernel_cuda");
}

void x_block_kernel(val_t *ptr, size_t local_bits, raddr_t delta_so, selector_t S_q_block)
{
    const size_t n = size_t(1) << local_bits;
    auto *p = reinterpret_cast<cuDoubleComplex *>(ptr);
    x_block_kernel_cuda<<<calc_blocks(n), kCudaThreads>>>(p, n, static_cast<size_t>(delta_so), S_q_block.alpha(),
                                                          S_q_block.beta());
    check_launch("x_block_kernel_cuda");
}

void cx_block_kernel(val_t *ptr, size_t local_bits, raddr_t delta_so, selector_t S_cq_block, selector_t S_q_block)
{
    const size_t n = size_t(1) << local_bits;
    auto *p = reinterpret_cast<cuDoubleComplex *>(ptr);
    cx_block_kernel_cuda<<<calc_blocks(n), kCudaThreads>>>(p, n, static_cast<size_t>(delta_so), S_cq_block.alpha(),
                                                           S_cq_block.beta(), S_q_block.alpha(), S_q_block.beta());
    check_launch("cx_block_kernel_cuda");
}

void u3_block_batch_kernel(val_t *ptr1, size_t local_bits, const std::vector<u3_batch_desc_t> &descs)
{
    if (descs.empty())
        return;
    if (descs.size() > kU3BatchMaxDesc)
        abort("u3_block_batch_kernel descriptor count exceeds constant-memory budget");

    const size_t n = size_t(1) << local_bits;
    auto *p1 = reinterpret_cast<cuDoubleComplex *>(ptr1);

    if (descs.size() == 1 || !supports_cooperative_launch())
    {
        for (const u3_batch_desc_t &desc : descs)
        {
            const selector_t sel = unpack_selector(desc.packed_sel);
            u3_block_kernel(ptr1, local_bits, desc.delta_so, sel, val_t(desc.u00_re, desc.u00_im),
                            val_t(desc.u01_re, desc.u01_im), val_t(desc.u10_re, desc.u10_im),
                            val_t(desc.u11_re, desc.u11_im));
        }
        return;
    }

    int sm_count = 0;
    check_cuda(cudaDeviceGetAttribute(&sm_count, cudaDevAttrMultiProcessorCount, 0),
               "cudaDeviceGetAttribute(multiProcessorCount) failed");
    int blocks_per_sm = 0;
    check_cuda(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&blocks_per_sm, u3_block_batch_kernel_cuda, kCudaThreads, 0),
               "cudaOccupancyMaxActiveBlocksPerMultiprocessor(u3_block_batch_kernel_cuda) failed");
    if (blocks_per_sm <= 0)
    {
        for (const u3_batch_desc_t &desc : descs)
        {
            const selector_t sel = unpack_selector(desc.packed_sel);
            u3_block_kernel(ptr1, local_bits, desc.delta_so, sel, val_t(desc.u00_re, desc.u00_im),
                            val_t(desc.u01_re, desc.u01_im), val_t(desc.u10_re, desc.u10_im),
                            val_t(desc.u11_re, desc.u11_im));
        }
        return;
    }
    const int grid = std::max(1, blocks_per_sm * sm_count);

    check_cuda(cudaMemcpyToSymbol(g_u3_batch_desc, descs.data(), descs.size() * sizeof(u3_batch_desc_t), 0,
                                  cudaMemcpyHostToDevice),
               "cudaMemcpyToSymbol(g_u3_batch_desc) failed");

    const size_t gate_count = descs.size();
    size_t kernel_n = n;
    void *kernel_args[] = {&p1, &kernel_n, const_cast<size_t *>(&gate_count)};
    check_cuda(cudaLaunchCooperativeKernel(reinterpret_cast<void *>(u3_block_batch_kernel_cuda), dim3(grid),
                                           dim3(kCudaThreads), kernel_args),
               "cudaLaunchCooperativeKernel(u3_block_batch_kernel_cuda) failed");
    check_launch("u3_block_batch_kernel_cuda");
}

void u3_intra_kernel(val_t *ptr1, val_t *ptr2, size_t I, raddr_t delta_o, selector_t S_k, val_t u00, val_t u01,
                     val_t u10, val_t u11)
{
    const size_t n = size_t(1) << I;
    auto *p1 = reinterpret_cast<cuDoubleComplex *>(ptr1);
    auto *p2 = reinterpret_cast<cuDoubleComplex *>(ptr2);
    u3_intra_kernel_cuda<<<calc_blocks(n), kCudaThreads>>>(p1, p2, n, static_cast<size_t>(delta_o), S_k.alpha(),
                                                           S_k.beta(), to_cu(u00), to_cu(u01), to_cu(u10), to_cu(u11));
    check_launch("u3_intra_kernel_cuda");
}

void u3_inter_kernel(val_t *ptr1, const val_t *ptr2, size_t I, raddr_t delta_o, selector_t S_k, val_t u00, val_t u01,
                     val_t u10, val_t u11)
{
    const size_t n = size_t(1) << I;
    auto *p1 = reinterpret_cast<cuDoubleComplex *>(ptr1);
    auto *p2 = reinterpret_cast<const cuDoubleComplex *>(ptr2);
    u3_inter_kernel_cuda<<<calc_blocks(n), kCudaThreads>>>(p1, p2, n, static_cast<size_t>(delta_o), S_k.alpha(),
                                                           S_k.beta(), to_cu(u00), to_cu(u01), to_cu(u10), to_cu(u11));
    check_launch("u3_inter_kernel_cuda");
}

void p_block_kernel(val_t *ptr, size_t local_bits, selector_t S_block, float_t theta)
{
    const size_t n = size_t(1) << local_bits;
    auto *p = reinterpret_cast<cuDoubleComplex *>(ptr);
    const val_t phase(std::cos(theta), std::sin(theta));
    p_block_kernel_cuda<<<calc_blocks(n), kCudaThreads>>>(p, n, S_block.alpha(), S_block.beta(), phase.real(),
                                                          phase.imag());
    check_launch("p_block_kernel_cuda");
}

void diag_pending_reset()
{
    g_diag_p_l.clear();
    g_diag_p_h.clear();
    g_diag_p_x.clear();
    g_diag_cp_ll.clear();
    g_diag_cp_hh.clear();
    g_diag_cp_hl.clear();
    g_diag_ir_host.clear();
}

void diag_pending_push_p(selector_t S_block, float_t theta)
{
    switch (classify_selector(S_block))
    {
    case selector_class_t::low:
        g_diag_p_l.push_back({pack_selector(S_block), theta});
        break;
    case selector_class_t::high:
        g_diag_p_h.push_back({pack_selector(S_block), theta});
        break;
    case selector_class_t::cross:
        g_diag_p_x.push_back({pack_selector(S_block), theta});
        break;
    }
}

bool diag_pending_try_push_cp(selector_t S_cq_block, selector_t S_q_block, float_t theta)
{
    const selector_class_t cq_class = classify_selector(S_cq_block);
    const selector_class_t q_class = classify_selector(S_q_block);
    const uint64_t cq = pack_selector(S_cq_block);
    const uint64_t q = pack_selector(S_q_block);

    if (cq_class == selector_class_t::low && q_class == selector_class_t::low)
    {
        g_diag_cp_ll.push_back({cq, q, theta});
        return true;
    }
    if (cq_class == selector_class_t::high && q_class == selector_class_t::high)
    {
        g_diag_cp_hh.push_back({cq, q, theta});
        return true;
    }
    if (cq_class == selector_class_t::low && q_class == selector_class_t::high)
    {
        g_diag_cp_hl.push_back({cq, q, theta});
        return true;
    }
    if (cq_class == selector_class_t::high && q_class == selector_class_t::low)
    {
        g_diag_cp_hl.push_back({q, cq, theta});
        return true;
    }
    return false;
}

bool diag_pending_empty()
{
    return !any_diag_pending();
}

void diag_pending_flush(val_t *ptr, size_t local_bits)
{
    if (!any_diag_pending())
        return;

    const size_t n = size_t(1) << local_bits;
    auto *p = reinterpret_cast<cuDoubleComplex *>(ptr);
    diag_chunk_cursor_t cursor;
    while (!diag_chunks_done(cursor))
    {
        diag_chunk_counts_t counts;
        if (!build_diag_chunk(cursor, counts))
            abort("diag_pending_flush failed to build non-empty chunk");
        check_cuda(cudaMemcpyToSymbol(g_diag_ir_words, g_diag_ir_host.data(), g_diag_ir_host.size() * sizeof(uint64_t),
                                      0, cudaMemcpyHostToDevice),
                   "cudaMemcpyToSymbol(g_diag_ir_words) failed");
        diag_block_kernel_cuda<<<calc_diag_blocks(n), kCudaThreads>>>(p, n, counts);
        check_launch("diag_block_kernel_cuda");
    }
    diag_pending_reset();
}

void p_block_batch_kernel(val_t *ptr, size_t local_bits, std::vector<selector_t> S_block, std::vector<float_t> theta)
{
    if (S_block.size() != theta.size())
        abort("p_block_batch_kernel selector/theta size mismatch");
    diag_pending_reset();
    for (size_t i = 0; i < S_block.size(); i++)
        diag_pending_push_p(S_block[i], theta[i]);
    diag_pending_flush(ptr, local_bits);
}

void cp_kernel(val_t *ptr, size_t local_bits, selector_t S_cq_block, selector_t S_q_block, float_t theta)
{
    const size_t n = size_t(1) << local_bits;
    auto *p = reinterpret_cast<cuDoubleComplex *>(ptr);
    const val_t phase(std::cos(theta), std::sin(theta));
    cp_kernel_cuda<<<calc_blocks(n), kCudaThreads>>>(p, n, S_cq_block.alpha(), S_cq_block.beta(), S_q_block.alpha(),
                                                     S_q_block.beta(), phase.real(), phase.imag());
    check_launch("cp_kernel_cuda");
}

} // namespace ZXHSim
