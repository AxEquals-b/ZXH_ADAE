#pragma once

#include "zxhsim/defs.h"
#include "zxhsim/runtime.h"

#include <memory>

namespace ZXHSim
{

class slot_pool_t;
class neighbor_stream_t;

class sv_t
{
  public:
    sv_t();
    ~sv_t();

    sv_t(const sv_t &) = delete;
    sv_t &operator=(const sv_t &) = delete;
    sv_t(sv_t &&) = delete;
    sv_t &operator=(sv_t &&) = delete;

    size_t used_bits() const;

    void reset();
    void resize(size_t M_new);
    void expand();

    val_t *segment_ptr(raddr_t seg);
    const val_t *raw_data() const;

    size_t I = 0;
    size_t J = 0;
    size_t K = 0;
    raddr_t block_start = 0;
    raddr_t block_end = 0;

  private:
    friend class neighbor_stream_t;

    size_t rank() const;
    size_t nprocs() const;

    size_t C_ = 0;
    size_t M_ = 0;
    size_t m_ = 0;
    size_t alloc_elems_ = 0;
    val_t *data_ = nullptr;
    std::unique_ptr<slot_pool_t> slot_pool_;
};

} // namespace ZXHSim
