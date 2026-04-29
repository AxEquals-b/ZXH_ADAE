#pragma once

#include "zxhsim/defs.h"

#include <cstddef>
#include <memory>

namespace ZXHSim
{

class request_t
{
  public:
    request_t();
    ~request_t();

    request_t(const request_t &) = delete;
    request_t &operator=(const request_t &) = delete;
    request_t(request_t &&) = delete;
    request_t &operator=(request_t &&) = delete;

  private:
    struct impl_t;
    std::unique_ptr<impl_t> impl_;

    friend void worker_send(const val_t *src, size_t elem_count, size_t peer, request_t &req);
    friend void worker_recv(val_t *dst, size_t elem_count, size_t peer, request_t &req);
    friend void worker_wait(request_t &req);
};

class worker_slot_t
{
  public:
    worker_slot_t();
    ~worker_slot_t();

    worker_slot_t(const worker_slot_t &) = delete;
    worker_slot_t &operator=(const worker_slot_t &) = delete;
    worker_slot_t(worker_slot_t &&) = delete;
    worker_slot_t &operator=(worker_slot_t &&) = delete;

    void configure(size_t segment_len);
    void pre_exchange(val_t *send_segment, size_t peer);
    val_t *wait_exchange();
    void release();

  private:
    struct impl_t;
    std::unique_ptr<impl_t> impl_;
};

void worker_send(const val_t *src, size_t elem_count, size_t peer, request_t &req);
void worker_recv(val_t *dst, size_t elem_count, size_t peer, request_t &req);
void worker_wait(request_t &req);

void host_broadcast(void *data, size_t bytes, size_t root);
void host_allreduce_sum(const float_t *send, float_t *recv, size_t count);
void host_exscan_sum(const float_t *send, float_t *recv, size_t count);
// Exclusive scan on host memory. prefix[i] receives the sum of ranks < i,
// while total[i] receives the global sum over all ranks.
void host_scan_sum(const float_t *send, float_t *prefix, float_t *total,
                   size_t count);
void host_gather_size(size_t local_size, size_t *root_sizes, size_t root);
void host_gatherv(const void *send_data, size_t send_bytes,
                  void *root_data, const size_t *root_sizes,
                  const size_t *root_displs, size_t root);

} // namespace ZXHSim
