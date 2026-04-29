#pragma once

#include "zxhsim/defs.h"
#include "zxhsim/sv.h"

#include <cstdint>
#include <memory>

namespace ZXHSim
{

class measure_cache_t
{
  public:
    explicit measure_cache_t(size_t nbits);
    ~measure_cache_t();

    measure_cache_t(const measure_cache_t &) = delete;
    measure_cache_t &operator=(const measure_cache_t &) = delete;
    measure_cache_t(measure_cache_t &&) = delete;
    measure_cache_t &operator=(measure_cache_t &&) = delete;

    size_t nbits() const;
    size_t result_count() const;

    void invalidate_mapping();

    void ensure_capacity(const sv_t &sv, size_t local_count, size_t global_count);
    void sample_local(const sv_t &sv, float_t local_prob, size_t result_count,
                      uint64_t stream_seed);
    void gather_results(size_t local_count, size_t global_count);
    void finalize_results(const bitmat_t &A, const bitvec_t &b, size_t count);
    void copy_results_to_host(res_t *results, size_t count) const;
    void set_result_count(size_t count);

  private:
    friend float_t sum_block_prob(const sv_t &sv, measure_cache_t &cache);

    size_t nbits_ = 0;
    size_t result_count_ = 0;

    struct impl_t;
    std::unique_ptr<impl_t> impl_;
};

// Backend-selected measurement implementation.
// Sample cnt outcomes from sv in real-address space, keep mapped results in backend buffers,
// and expose host transfer via get_results(...).
void measure(const sv_t &sv, const bitmat_t &A, const bitvec_t &b,
             measure_cache_t &cache, size_t cnt, bool use_seed, uint64_t seed);
void get_results(const measure_cache_t &cache, res_t *results, size_t cnt);

} // namespace ZXHSim
