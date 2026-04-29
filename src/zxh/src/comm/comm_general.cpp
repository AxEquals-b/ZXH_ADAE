#include "zxhsim/comm.h"
#include "zxhsim/runtime.h"

#include <cstring>
#include <memory>

namespace ZXHSim
{

struct request_t::impl_t
{
};

request_t::request_t() : impl_(std::make_unique<impl_t>())
{
}

request_t::~request_t() = default;

struct worker_slot_t::impl_t
{
    size_t segment_len = 0;
    val_t *local_segment = nullptr;
};

worker_slot_t::worker_slot_t() : impl_(std::make_unique<impl_t>())
{
}

worker_slot_t::~worker_slot_t() = default;

void worker_slot_t::configure(size_t segment_len)
{
    impl_->segment_len = segment_len;
    impl_->local_segment = nullptr;
}

void worker_slot_t::pre_exchange(val_t *send_segment, size_t peer)
{
    (void)peer;
    impl_->local_segment = send_segment;
}

val_t *worker_slot_t::wait_exchange()
{
    return impl_->local_segment;
}

void worker_slot_t::release()
{
    impl_->local_segment = nullptr;
}

void worker_send(const val_t *src, size_t elem_count, size_t peer, request_t &req)
{
    (void)src;
    (void)elem_count;
    (void)peer;
    (void)req;
}

void worker_recv(val_t *dst, size_t elem_count, size_t peer, request_t &req)
{
    (void)dst;
    (void)elem_count;
    (void)peer;
    (void)req;
}

void worker_wait(request_t &req)
{
    (void)req;
}

void host_broadcast(void *data, size_t bytes, size_t root)
{
    (void)data;
    (void)bytes;
    (void)root;
}

void host_allreduce_sum(const float_t *send, float_t *recv, size_t count)
{
    if (count == 0)
        return;
    if (send == nullptr || recv == nullptr)
        abort("host_allreduce_sum null buffer");
    for (size_t i = 0; i < count; i++)
        recv[i] = send[i];
}

void host_exscan_sum(const float_t *send, float_t *recv, size_t count)
{
    (void)send;
    if (count == 0)
        return;
    if (recv == nullptr)
        abort("host_exscan_sum null buffer");
    for (size_t i = 0; i < count; i++)
        recv[i] = 0.0;
}

void host_scan_sum(const float_t *send, float_t *prefix, float_t *total,
                   size_t count)
{
    if (count == 0)
        return;
    if (send == nullptr || prefix == nullptr || total == nullptr)
        abort("host_scan_sum null buffer");

    for (size_t i = 0; i < count; i++)
    {
        prefix[i] = 0.0;
        total[i] = send[i];
    }
}

void host_gather_size(size_t local_size, size_t *root_sizes, size_t root)
{
    (void)root;
    if (root_sizes != nullptr)
        root_sizes[0] = local_size;
}

void host_gatherv(const void *send_data, size_t send_bytes,
                  void *root_data, const size_t *root_sizes,
                  const size_t *root_displs, size_t root)
{
    (void)root;
    if (send_bytes == 0)
        return;
    if (send_data == nullptr || root_data == nullptr)
        abort("host_gatherv null buffer");

    size_t dst_offset = 0;
    if (root_displs != nullptr)
        dst_offset = root_displs[0];
    if (root_sizes != nullptr && root_sizes[0] != send_bytes)
        abort("host_gatherv size mismatch");

    std::memcpy(static_cast<char *>(root_data) + dst_offset, send_data, send_bytes);
}

} // namespace ZXHSim
