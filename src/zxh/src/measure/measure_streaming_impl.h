#pragma once

#include "measure_internal.h"

#include <algorithm>
#include <array>
#include <limits>
#include <utility>

namespace ZXHSim
{
namespace detail
{

inline raddr_t resolve_in_segment(raddr_t seg, const float_t *cdf_seg,
                                  size_t valid_count, float_t tau)
{
    if (valid_count == 0)
        abort("resolve_in_segment on empty segment");

    const float_t *it = std::upper_bound(cdf_seg, cdf_seg + valid_count, tau);
    const size_t offset = (it == cdf_seg + valid_count)
                              ? (valid_count - 1)
                              : static_cast<size_t>(it - cdf_seg);
    return seg + static_cast<raddr_t>(offset);
}

inline void consume_stream_in_segment(raddr_t seg, const float_t *cdf_seg,
                                      size_t valid_count, float_t cdf_tail,
                                      threshold_stream_t &tau_stream, size_t &pcnt,
                                      raddr_t *results, size_t result_count)
{
    if (valid_count == 0)
        return;

    while (!tau_stream.empty() && tau_stream.head() < cdf_tail)
    {
        if (pcnt >= result_count)
            abort("measure local result overflow");
        results[pcnt++] = resolve_in_segment(seg, cdf_seg, valid_count,
                                             tau_stream.head());
        tau_stream.pop();
    }
}

class segment_prefix_state_t
{
  public:
    explicit segment_prefix_state_t(float_t base) : base_(base)
    {
        active_.fill(false);
        sums_.fill(0.0);
    }

    float_t prefix() const
    {
        float_t acc = base_;
        for (size_t level = kMaxLevels; level-- > 0;)
        {
            if (active_[level])
                acc += sums_[level];
        }
        return acc;
    }

    void push(float_t seg_sum)
    {
        size_t level = 0;
        float_t carry = seg_sum;
        while (true)
        {
            if (level >= kMaxLevels)
                abort("segment_prefix_state_t overflow");
            if (!active_[level])
            {
                active_[level] = true;
                sums_[level] = carry;
                return;
            }

            carry = sums_[level] + carry;
            active_[level] = false;
            sums_[level] = 0.0;
            level++;
        }
    }

  private:
    static constexpr size_t kMaxLevels =
        std::numeric_limits<raddr_t>::digits;

    float_t base_ = 0.0;
    std::array<float_t, kMaxLevels> sums_{};
    std::array<bool, kMaxLevels> active_{};
};

inline void sample_local_streaming(const sv_t &sv, float_t local_prob,
                                   size_t result_count, uint64_t stream_seed,
                                   raddr_t *results)
{
    if (result_count == 0)
        return;
    if (local_prob <= 0.0)
        abort("sample_local_streaming requires positive local_prob");

    threshold_stream_t tau_stream(result_count, 0.0, local_prob, stream_seed);

    const raddr_t step = raddr_e_i(sv.I);
    const size_t segment_len = static_cast<size_t>(step);
    segment_cdf_t slot0(segment_len);
    segment_cdf_t slot1(segment_len);
    segment_cdf_t *cur = &slot0;
    segment_cdf_t *nxt = &slot1;

    raddr_t seg = sv.block_start;
    size_t pcnt = 0;
    segment_prefix_state_t prefix_state(0.0);
    float_t cur_prefix = prefix_state.prefix();

    cur->pre_cdf(sv, seg, cur_prefix);
    while (seg < sv.block_end && !tau_stream.empty())
    {
        float_t next_cdf_head = cur_prefix;
        const float_t *cdf_seg = cur->wait_cdf(next_cdf_head);
        prefix_state.push(cur->segment_sum());

        const raddr_t next_seg = seg + step;
        if (next_seg < sv.block_end)
            nxt->pre_cdf(sv, next_seg, prefix_state.prefix());

        const size_t valid_count =
            std::min(segment_len, static_cast<size_t>(sv.block_end - seg));
        consume_stream_in_segment(seg, cdf_seg, valid_count, next_cdf_head,
                                  tau_stream, pcnt, results, result_count);

        cur->release();
        seg = next_seg;
        cur_prefix = prefix_state.prefix();
        std::swap(cur, nxt);
    }

    slot0.release();
    slot1.release();

    if (!tau_stream.empty() || pcnt != result_count)
        abort("measure failed to resolve all local samples");
}

} // namespace detail
} // namespace ZXHSim
