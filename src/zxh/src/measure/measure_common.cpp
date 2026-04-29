#include "zxhsim/measure.h"

#include "measure_internal.h"

#include <cmath>
#include <cstdint>
#include <limits>
#include <random>
#include <vector>

namespace ZXHSim
{

struct threshold_stream_t::impl_t
{
    std::mt19937_64 rng;
    std::uniform_real_distribution<float_t> dist;

    explicit impl_t(uint64_t seed) : rng(seed), dist(0.0, 1.0)
    {
    }
};

threshold_stream_t::threshold_stream_t(size_t cnt, float_t begin, float_t end,
                                       uint64_t seed)
    : rest_(cnt), tau_begin_(begin), tau_end_(end),
      impl_(std::make_unique<impl_t>(seed))
{
    if (end < begin)
        abort("threshold_stream_t interval is invalid");
    if (rest_ != 0 && begin >= end)
        abort("threshold_stream_t non-empty interval is empty");

    if (rest_ != 0)
        advance();
}

threshold_stream_t::~threshold_stream_t() = default;

bool threshold_stream_t::empty() const
{
    return rest_ == 0;
}

float_t threshold_stream_t::head() const
{
    if (empty())
        abort("threshold_stream_t head on empty stream");
    return head_;
}

void threshold_stream_t::pop()
{
    if (empty())
        abort("threshold_stream_t pop on empty stream");

    tau_begin_ = head_;
    rest_--;
    if (rest_ != 0)
        advance();
}

void threshold_stream_t::advance()
{
    float_t u = impl_->dist(impl_->rng);
    u = std::max(u, std::numeric_limits<float_t>::min());

    const float_t span = tau_end_ - tau_begin_;
    const float_t factor = 1.0 - std::pow(u, 1.0 / static_cast<float_t>(rest_));
    head_ = tau_begin_ + span * factor;
}

void measure(const sv_t &sv, const bitmat_t &A, const bitvec_t &b,
             measure_cache_t &cache, size_t cnt, bool use_seed, uint64_t seed)
{
    if (cnt == 0)
    {
        cache.set_result_count(0);
        return;
    }

    const prob_scan_t prob_scan = scan_block_prob(sv, cache);
    const measure_plan_t plan = make_measure_plan(cnt, prob_scan, use_seed, seed);
    if (plan.global_total <= 0.0)
        abort("state has zero total probability");

    cache.ensure_capacity(sv, plan.cnt_local, cnt);
    cache.sample_local(sv, prob_scan.local_prob, plan.cnt_local, plan.stream_seed);
    cache.gather_results(plan.cnt_local, cnt);
    cache.finalize_results(A, b, cnt);
    cache.set_result_count(cnt);
}

void get_results(const measure_cache_t &cache, res_t *results, size_t cnt)
{
    if (cnt == 0)
        return;
    if (results == nullptr)
        abort("get_results results is null");
    if (cnt > cache.result_count())
        abort("get_results count exceeds cached result count");
    cache.copy_results_to_host(results, cnt);
}

} // namespace ZXHSim
