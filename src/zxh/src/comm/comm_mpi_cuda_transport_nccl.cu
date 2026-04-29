#include "comm_mpi_cuda_transport.h"
#include "../runtime_internal.h"

#include "zxhsim/mem.h"
#include "zxhsim/runtime.h"

#include <cuda_runtime.h>
#include <nccl.h>

#include <limits>
#include <memory>
#include <string>

namespace ZXHSim::mpi_cuda_comm
{

namespace
{

void ensure_nccl_runtime_active(const char *what)
{
    if (!active())
        abort(what);
    if (!runtime_nccl_enabled())
        abort(std::string(what) + ": NCCL runtime is not active");
}

void check_cuda(cudaError_t err, const char *what)
{
    if (err == cudaSuccess)
        return;
    abort(std::string(what) + ": " + cudaGetErrorString(err));
}

void check_nccl(ncclResult_t err, const char *what)
{
    if (err == ncclSuccess)
        return;
    abort(std::string(what) + ": " + ncclGetErrorString(err));
}

int checked_peer(size_t peer, const char *what)
{
    if (peer > static_cast<size_t>(std::numeric_limits<int>::max()))
        abort(what);
    return static_cast<int>(peer);
}

size_t checked_byte_count(size_t elem_count, const char *what)
{
    if (elem_count > std::numeric_limits<size_t>::max() / sizeof(val_t))
        abort(what);
    return elem_count * sizeof(val_t);
}

ncclComm_t checked_runtime_comm(const char *what)
{
    ensure_nccl_runtime_active(what);
    void *comm = runtime_nccl_comm();
    if (comm == nullptr)
        abort(std::string(what) + ": runtime NCCL communicator is null");
    return reinterpret_cast<ncclComm_t>(comm);
}

cudaStream_t make_stream(const char *what)
{
    cudaStream_t stream = nullptr;
    check_cuda(cudaStreamCreateWithFlags(&stream, cudaStreamNonBlocking), what);
    return stream;
}

void destroy_stream(cudaStream_t &stream, const char *what)
{
    if (stream == nullptr)
        return;
    check_cuda(cudaStreamDestroy(stream), what);
    stream = nullptr;
}

class nccl_request_backend_t final : public request_backend_t
{
  public:
    nccl_request_backend_t()
        : stream_(make_stream("worker_request NCCL cudaStreamCreateWithFlags failed"))
    {
    }

    ~nccl_request_backend_t() override
    {
        wait();
        destroy_stream(stream_, "worker_request NCCL cudaStreamDestroy failed");
    }

    void start_send(const val_t *src, size_t elem_count, size_t peer) override
    {
        if (elem_count == 0)
            return;
        ensure_nccl_runtime_active("worker_send requires active NCCL runtime");
        if (src == nullptr)
            abort("worker_send src is null");
        if (active_)
            abort("worker_send requires an inactive request");

        const size_t bytes = checked_byte_count(elem_count, "worker_send payload size overflow");
        const int peer_rank = checked_peer(peer, "worker_send peer exceeds NCCL int range");
        ncclComm_t comm = checked_runtime_comm("worker_send requires valid NCCL communicator");

        check_nccl(ncclGroupStart(), "worker_send ncclGroupStart failed");
        check_nccl(ncclSend(src, bytes, ncclUint8, peer_rank, comm, stream_),
                   "worker_send ncclSend failed");
        check_nccl(ncclGroupEnd(), "worker_send ncclGroupEnd failed");
        active_ = true;
    }

    void start_recv(val_t *dst, size_t elem_count, size_t peer) override
    {
        if (elem_count == 0)
            return;
        ensure_nccl_runtime_active("worker_recv requires active NCCL runtime");
        if (dst == nullptr)
            abort("worker_recv dst is null");
        if (active_)
            abort("worker_recv requires an inactive request");

        const size_t bytes = checked_byte_count(elem_count, "worker_recv payload size overflow");
        const int peer_rank = checked_peer(peer, "worker_recv peer exceeds NCCL int range");
        ncclComm_t comm = checked_runtime_comm("worker_recv requires valid NCCL communicator");

        check_nccl(ncclGroupStart(), "worker_recv ncclGroupStart failed");
        check_nccl(ncclRecv(dst, bytes, ncclUint8, peer_rank, comm, stream_),
                   "worker_recv ncclRecv failed");
        check_nccl(ncclGroupEnd(), "worker_recv ncclGroupEnd failed");
        active_ = true;
    }

    void wait() override
    {
        if (!active_)
            return;
        check_cuda(cudaStreamSynchronize(stream_), "worker_wait NCCL cudaStreamSynchronize failed");
        active_ = false;
    }

  private:
    cudaStream_t stream_ = nullptr;
    bool active_ = false;
};

class nccl_slot_backend_t final : public slot_backend_t
{
  public:
    nccl_slot_backend_t()
        : stream_(make_stream("worker_slot NCCL cudaStreamCreateWithFlags failed"))
    {
    }

    ~nccl_slot_backend_t() override
    {
        release();
        worker_free(recv_buffer_);
        recv_buffer_ = nullptr;
        destroy_stream(stream_, "worker_slot NCCL cudaStreamDestroy failed");
    }

    void configure(size_t segment_len) override
    {
        release();
        if (segment_len == segment_len_)
            return;

        worker_free(recv_buffer_);
        recv_buffer_ = nullptr;
        segment_len_ = segment_len;
        if (segment_len_ > 0)
            recv_buffer_ = worker_alloc(segment_len_);
    }

    void pre_exchange(val_t *send_segment, size_t peer) override
    {
        if (segment_len_ == 0)
            return;
        ensure_nccl_runtime_active("worker_slot_t::pre_exchange requires active NCCL runtime");
        if (send_segment == nullptr)
            abort("worker_slot_t::pre_exchange send_segment is null");
        if (recv_buffer_ == nullptr)
            abort("worker_slot_t::pre_exchange recv_buffer is null");
        if (active_)
            abort("worker_slot_t::pre_exchange requires an idle slot");

        const size_t bytes =
            checked_byte_count(segment_len_, "worker_slot_t::pre_exchange payload size overflow");
        const int peer_rank =
            checked_peer(peer, "worker_slot_t::pre_exchange peer exceeds NCCL int range");
        ncclComm_t comm =
            checked_runtime_comm("worker_slot_t::pre_exchange requires valid NCCL communicator");

        check_nccl(ncclGroupStart(), "worker_slot_t::pre_exchange ncclGroupStart failed");
        check_nccl(ncclRecv(recv_buffer_, bytes, ncclUint8, peer_rank, comm, stream_),
                   "worker_slot_t::pre_exchange ncclRecv failed");
        check_nccl(ncclSend(send_segment, bytes, ncclUint8, peer_rank, comm, stream_),
                   "worker_slot_t::pre_exchange ncclSend failed");
        check_nccl(ncclGroupEnd(), "worker_slot_t::pre_exchange ncclGroupEnd failed");
        active_ = true;
    }

    val_t *wait_exchange() override
    {
        release();
        return recv_buffer_;
    }

    void release() override
    {
        if (!active_)
            return;
        check_cuda(cudaStreamSynchronize(stream_),
                   "worker_slot_t::release NCCL cudaStreamSynchronize failed");
        active_ = false;
    }

  private:
    size_t segment_len_ = 0;
    val_t *recv_buffer_ = nullptr;
    cudaStream_t stream_ = nullptr;
    bool active_ = false;
};

} // namespace

std::unique_ptr<request_backend_t> make_request_backend()
{
    return std::make_unique<nccl_request_backend_t>();
}

std::unique_ptr<slot_backend_t> make_slot_backend()
{
    return std::make_unique<nccl_slot_backend_t>();
}

} // namespace ZXHSim::mpi_cuda_comm
