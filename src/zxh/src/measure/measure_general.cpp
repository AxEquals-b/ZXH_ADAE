#include "measure_internal.h"
#include "measure_result_pack.h"
#include "measure_streaming_impl.h"

#include <algorithm>
#include <cstdint>
#include <random>
#include <vector>

namespace ZXHSim
{

namespace
{

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

size_t next_pow2(size_t x)
{
    size_t v = 1;
    while (v < x)
        v <<= 1;
    return v;
}

float_t merge_prob_sum_range(const val_t *data, size_t begin, size_t end)
{
    if (begin >= end)
        return 0.0;
    if (end - begin == 1)
        return std::norm(data[begin]);

    const size_t mid = begin + (end - begin) / 2;
    return merge_prob_sum_range(data, begin, mid) +
           merge_prob_sum_range(data, mid, end);
}

float_t exclusive_scan_merge(const float_t *input, size_t count,
                             std::vector<float_t> &work)
{
    if (count == 0)
        return 0.0;

    const size_t padded = next_pow2(count);
    work.assign(padded, 0.0);
    for (size_t i = 0; i < count; i++)
        work[i] = input[i];

    for (size_t stride = 1; stride < padded; stride <<= 1)
    {
        const size_t step = stride << 1;
        for (size_t i = 0; i < padded; i += step)
            work[i + step - 1] += work[i + stride - 1];
    }

    const float_t total = work[padded - 1];
    work[padded - 1] = 0.0;

    for (size_t stride = padded >> 1; stride >= 1; stride >>= 1)
    {
        const size_t step = stride << 1;
        for (size_t i = 0; i < padded; i += step)
        {
            const float_t left = work[i + stride - 1];
            work[i + stride - 1] = work[i + step - 1];
            work[i + step - 1] += left;
        }
        if (stride == 1)
            break;
    }

    return total;
}

} // namespace

struct measure_cache_t::impl_t
{
    std::vector<raddr_t> local_real_results;
    std::vector<raddr_t> real_results;
    std::vector<uint64_t> packed_results;
};

measure_cache_t::measure_cache_t(size_t nbits)
    : nbits_(nbits), result_count_(0), impl_(std::make_unique<impl_t>())
{
}

measure_cache_t::~measure_cache_t() = default;

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
}

void measure_cache_t::ensure_capacity(const sv_t &, size_t local_count, size_t global_count)
{
    impl_->local_real_results.resize(local_count);
    impl_->real_results.resize(global_count);
    impl_->packed_results.resize(global_count * detail::result_word_count(nbits_));
}

void measure_cache_t::sample_local(const sv_t &sv, float_t local_prob, size_t result_count,
                                   uint64_t stream_seed)
{
    detail::sample_local_streaming(sv, local_prob, result_count, stream_seed,
                                   impl_->local_real_results.data());
}

void measure_cache_t::gather_results(size_t local_count, size_t global_count)
{
    if (global_count == 0)
        return;
    if (local_count != global_count)
        abort("measure_cache_t::gather_results count mismatch");
    std::copy_n(impl_->local_real_results.data(), global_count, impl_->real_results.data());
}

void measure_cache_t::finalize_results(const bitmat_t &A, const bitvec_t &b, size_t count)
{
    detail::pack_virtual_results_host(impl_->real_results.data(), count, A, b, nbits_,
                                      impl_->packed_results);
}

void measure_cache_t::copy_results_to_host(res_t *results, size_t count) const
{
    detail::unpack_virtual_results_host(impl_->packed_results.data(), count, nbits_, results);
}

void measure_cache_t::set_result_count(size_t count)
{
    result_count_ = count;
}

struct segment_cdf_t::impl_t
{
    size_t segment_len = 0;
    std::vector<float_t> cdf_buffer;
    std::vector<float_t> scan_buffer;
    float_t cdf_head_out = 0.0;
    float_t segment_total = 0.0;
};

static size_t valid_segment_len(const sv_t &sv, raddr_t seg, size_t segment_len)
{
    if (seg >= sv.block_end)
        return 0;
    return std::min(segment_len, static_cast<size_t>(sv.block_end - seg));
}

segment_cdf_t::segment_cdf_t(size_t segment_len) : impl_(std::make_unique<impl_t>())
{
    impl_->segment_len = segment_len;
    impl_->cdf_buffer.resize(segment_len);
}

segment_cdf_t::~segment_cdf_t() = default;

void segment_cdf_t::pre_cdf(const sv_t &sv, raddr_t seg, float_t cdf_head_in)
{
    const size_t valid_count = valid_segment_len(sv, seg, impl_->segment_len);
    if (valid_count == 0)
    {
        impl_->cdf_head_out = cdf_head_in;
        return;
    }

    const size_t offset = static_cast<size_t>(seg - sv.block_start);
    const val_t *src = sv.raw_data() + offset;

    for (size_t i = 0; i < valid_count; i++)
        impl_->cdf_buffer[i] = std::norm(src[i]);

    const float_t total =
        exclusive_scan_merge(impl_->cdf_buffer.data(), valid_count, impl_->scan_buffer);
    for (size_t i = 0; i < valid_count; i++)
        impl_->cdf_buffer[i] = cdf_head_in + impl_->scan_buffer[i] + impl_->cdf_buffer[i];
    impl_->cdf_head_out = cdf_head_in + total;
    impl_->segment_total = total;
}

const float_t *segment_cdf_t::wait_cdf(float_t &cdf_head_out)
{
    cdf_head_out = impl_->cdf_head_out;
    return impl_->cdf_buffer.data();
}

float_t segment_cdf_t::segment_sum() const
{
    return impl_->segment_total;
}

void segment_cdf_t::release()
{
}

float_t sum_block_prob(const sv_t &sv, measure_cache_t &)
{
    const size_t local_size = static_cast<size_t>(sv.block_end - sv.block_start);
    const val_t *data = sv.raw_data();
    return merge_prob_sum_range(data, 0, local_size);
}

prob_scan_t scan_block_prob(const sv_t &sv, measure_cache_t &cache)
{
    prob_scan_t scan;
    scan.local_prob = sum_block_prob(sv, cache);
    scan.prob_prefix = 0.0;
    scan.global_total = scan.local_prob;
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
