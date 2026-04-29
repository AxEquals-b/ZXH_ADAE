#pragma once

#include "zxhsim/defs.h"

#include <cstddef>
#include <memory>

namespace ZXHSim::mpi_cuda_comm
{
class request_backend_t
{
  public:
    virtual ~request_backend_t() = default;

    virtual void start_send(const val_t *src, size_t elem_count, size_t peer) = 0;
    virtual void start_recv(val_t *dst, size_t elem_count, size_t peer) = 0;
    virtual void wait() = 0;
};

class slot_backend_t
{
  public:
    virtual ~slot_backend_t() = default;

    virtual void configure(size_t segment_len) = 0;
    virtual void pre_exchange(val_t *send_segment, size_t peer) = 0;
    virtual val_t *wait_exchange() = 0;
    virtual void release() = 0;
};

std::unique_ptr<request_backend_t> make_request_backend();
std::unique_ptr<slot_backend_t> make_slot_backend();

} // namespace ZXHSim::mpi_cuda_comm
