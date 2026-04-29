#pragma once

#include "zxhsim/sv.h"

namespace ZXHSim
{

struct neighbor_t
{
    raddr_t seg = 0;
    val_t *local = nullptr;
    const val_t *remote = nullptr;
};

class neighbor_stream_t
{
  public:
    neighbor_stream_t(sv_t &sv, raddr_t delta_bs);
    ~neighbor_stream_t();

    neighbor_stream_t(const neighbor_stream_t &) = delete;
    neighbor_stream_t &operator=(const neighbor_stream_t &) = delete;
    neighbor_stream_t(neighbor_stream_t &&) = delete;
    neighbor_stream_t &operator=(neighbor_stream_t &&) = delete;

    bool acquire(neighbor_t &neighbor);
    void release();

  private:
    static constexpr size_t kInvalidSlot = static_cast<size_t>(-1);

    void prefetch_next();

    sv_t &sv_;
    raddr_t delta_bs_ = 0;
    raddr_t step_ = 0;
    raddr_t next_seg_ = 0;

    bool prefetched_ = false;
    raddr_t prefetched_seg_ = 0;
    size_t prefetched_slot_ = kInvalidSlot;

    bool acquired_ = false;
    raddr_t acquired_seg_ = 0;
    size_t acquired_slot_ = kInvalidSlot;
    const val_t *acquired_remote_ = nullptr;
};

} // namespace ZXHSim
