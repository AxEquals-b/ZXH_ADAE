#pragma once

#include "zxhsim/measure.h"
#include "zxhsim/defs.h"

#include <cstdint>
#include <memory>

namespace ZXHSim
{

struct prob_scan_t
{
    float_t local_prob = 0.0;
    float_t prob_prefix = 0.0;
    float_t global_total = 0.0;
};

struct measure_plan_t
{
    float_t global_total = 0.0;
    float_t prob_prefix = 0.0;
    size_t cnt_local = 0;
    uint64_t stream_seed = 0;
};

class threshold_stream_t
{
  public:
    threshold_stream_t(size_t cnt, float_t begin, float_t end, uint64_t seed);
    ~threshold_stream_t();

    bool empty() const;
    float_t head() const;
    void pop();

  private:
    size_t rest_ = 0;
    float_t tau_begin_ = 0.0;
    float_t tau_end_ = 0.0;
    float_t head_ = 0.0;

    struct impl_t;
    std::unique_ptr<impl_t> impl_;

    void advance();
};

class segment_cdf_t
{
  public:
    explicit segment_cdf_t(size_t segment_len);
    ~segment_cdf_t();

    segment_cdf_t(const segment_cdf_t &) = delete;
    segment_cdf_t &operator=(const segment_cdf_t &) = delete;
    segment_cdf_t(segment_cdf_t &&) = delete;
    segment_cdf_t &operator=(segment_cdf_t &&) = delete;

    void pre_cdf(const sv_t &sv, raddr_t seg, float_t cdf_head_in);
    const float_t *wait_cdf(float_t &cdf_head_out);
    float_t segment_sum() const;
    void release();

  private:
    struct impl_t;
    std::unique_ptr<impl_t> impl_;
};

float_t sum_block_prob(const sv_t &sv, measure_cache_t &cache);
prob_scan_t scan_block_prob(const sv_t &sv, measure_cache_t &cache);
measure_plan_t make_measure_plan(size_t cnt, const prob_scan_t &prob_scan,
                                 bool use_seed, uint64_t seed);

} // namespace ZXHSim
