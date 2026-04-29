#include "zxhsim/comm.h"
#include "zxhsim/runtime.h"

#include "comm_mpi_cuda_transport.h"

#include <algorithm>
#include <limits>
#include <memory>
#include <mpi.h>
#include <type_traits>
#include <vector>

namespace ZXHSim
{

namespace
{
MPI_Datatype mpi_float_dtype()
{
    if constexpr (std::is_same_v<float_t, float>)
        return MPI_FLOAT;
    else
        return MPI_DOUBLE;
}

int checked_int_count(size_t count, const char *what)
{
    if (count > static_cast<size_t>(std::numeric_limits<int>::max()))
        abort(what);
    return static_cast<int>(count);
}

void ensure_runtime_active(const char *what)
{
    if (!active())
        abort(what);
}

size_t next_pow2(size_t x)
{
    size_t v = 1;
    while (v < x)
        v <<= 1;
    return v;
}

float_t exclusive_scan_merge(const float_t *input, size_t count,
                             std::vector<float_t> &work)
{
    if (count == 0)
        return 0.0;

    const size_t padded = next_pow2(count);
    work.assign(padded, 0.0);
    for (size_t i = 0; i < count; i++)
        work[i] = input[i];

    for (size_t stride = 1; stride < padded; stride <<= 1)
    {
        const size_t step = stride << 1;
        for (size_t i = 0; i < padded; i += step)
            work[i + step - 1] += work[i + stride - 1];
    }

    const float_t total = work[padded - 1];
    work[padded - 1] = 0.0;

    for (size_t stride = padded >> 1; stride >= 1; stride >>= 1)
    {
        const size_t step = stride << 1;
        for (size_t i = 0; i < padded; i += step)
        {
            const float_t left = work[i + stride - 1];
            work[i + stride - 1] = work[i + step - 1];
            work[i + step - 1] += left;
        }
        if (stride == 1)
            break;
    }

    return total;
}

void root_tree_scan(const float_t *gathered, size_t nranks, size_t count,
                    std::vector<float_t> &prefix_by_rank,
                    std::vector<float_t> &total_out)
{
    prefix_by_rank.assign(nranks * count, 0.0);
    total_out.assign(count, 0.0);

    std::vector<float_t> rank_values(nranks, 0.0);
    std::vector<float_t> work;
    for (size_t j = 0; j < count; j++)
    {
        for (size_t r = 0; r < nranks; r++)
            rank_values[r] = gathered[r * count + j];

        total_out[j] = exclusive_scan_merge(rank_values.data(), nranks, work);
        for (size_t r = 0; r < nranks; r++)
            prefix_by_rank[r * count + j] = work[r];
    }
}

} // namespace

struct request_t::impl_t
{
    std::unique_ptr<mpi_cuda_comm::request_backend_t> backend =
        mpi_cuda_comm::make_request_backend();
};

request_t::request_t() : impl_(std::make_unique<impl_t>())
{
}

request_t::~request_t() = default;

struct worker_slot_t::impl_t
{
    std::unique_ptr<mpi_cuda_comm::slot_backend_t> backend =
        mpi_cuda_comm::make_slot_backend();
};

worker_slot_t::worker_slot_t() : impl_(std::make_unique<impl_t>())
{
}

worker_slot_t::~worker_slot_t() = default;

void worker_slot_t::configure(size_t segment_len)
{
    if (impl_ == nullptr || impl_->backend == nullptr)
        abort("worker_slot_t backend is not initialized");
    impl_->backend->configure(segment_len);
}

void worker_slot_t::pre_exchange(val_t *send_segment, size_t peer)
{
    if (impl_ == nullptr || impl_->backend == nullptr)
        abort("worker_slot_t backend is not initialized");
    impl_->backend->pre_exchange(send_segment, peer);
}

val_t *worker_slot_t::wait_exchange()
{
    if (impl_ == nullptr || impl_->backend == nullptr)
        abort("worker_slot_t backend is not initialized");
    return impl_->backend->wait_exchange();
}

void worker_slot_t::release()
{
    if (impl_ == nullptr || impl_->backend == nullptr)
        return;
    impl_->backend->release();
}

void worker_send(const val_t *src, size_t elem_count, size_t peer, request_t &req)
{
    if (req.impl_ == nullptr || req.impl_->backend == nullptr)
        abort("worker_send request backend is not initialized");
    req.impl_->backend->start_send(src, elem_count, peer);
}

void worker_recv(val_t *dst, size_t elem_count, size_t peer, request_t &req)
{
    if (req.impl_ == nullptr || req.impl_->backend == nullptr)
        abort("worker_recv request backend is not initialized");
    req.impl_->backend->start_recv(dst, elem_count, peer);
}

void worker_wait(request_t &req)
{
    if (req.impl_ == nullptr || req.impl_->backend == nullptr)
        return;
    req.impl_->backend->wait();
}

void host_broadcast(void *data, size_t bytes, size_t root)
{
    if (bytes == 0)
        return;
    ensure_runtime_active("host_broadcast requires active MPI runtime");
    if (data == nullptr)
        abort("host_broadcast data is null");
    const int byte_count = checked_int_count(bytes, "host_broadcast payload exceeds MPI int range");
    MPI_Bcast(data, byte_count, MPI_BYTE, static_cast<int>(root), MPI_COMM_WORLD);
}

void host_allreduce_sum(const float_t *send, float_t *recv, size_t count)
{
    if (count == 0)
        return;
    ensure_runtime_active("host_allreduce_sum requires active MPI runtime");
    if (send == nullptr || recv == nullptr)
        abort("host_allreduce_sum null buffer");
    const int icount = checked_int_count(count, "host_allreduce_sum count exceeds MPI int range");
    MPI_Allreduce(send, recv, icount, mpi_float_dtype(), MPI_SUM, MPI_COMM_WORLD);
}

void host_exscan_sum(const float_t *send, float_t *recv, size_t count)
{
    if (count == 0)
        return;
    ensure_runtime_active("host_exscan_sum requires active MPI runtime");
    if (send == nullptr || recv == nullptr)
        abort("host_exscan_sum null buffer");
    const int icount = checked_int_count(count, "host_exscan_sum count exceeds MPI int range");
    MPI_Exscan(send, recv, icount, mpi_float_dtype(), MPI_SUM, MPI_COMM_WORLD);
    if (rank() == 0)
    {
        for (size_t i = 0; i < count; i++)
            recv[i] = 0.0;
    }
}

void host_scan_sum(const float_t *send, float_t *prefix, float_t *total,
                   size_t count)
{
    if (count == 0)
        return;
    ensure_runtime_active("host_scan_sum requires active MPI runtime");
    if (send == nullptr || prefix == nullptr || total == nullptr)
        abort("host_scan_sum null buffer");

    const int icount = checked_int_count(count, "host_scan_sum count exceeds MPI int range");
    const int root = 0;

    std::vector<float_t> gathered;
    std::vector<float_t> prefix_by_rank;
    std::vector<float_t> total_buf;
    if (rank() == static_cast<size_t>(root))
        gathered.resize(nprocs() * count, 0.0);

    MPI_Gather(const_cast<float_t *>(send), icount, mpi_float_dtype(),
               rank() == static_cast<size_t>(root) ? gathered.data() : nullptr,
               icount, mpi_float_dtype(), root, MPI_COMM_WORLD);

    if (rank() == static_cast<size_t>(root))
        root_tree_scan(gathered.data(), nprocs(), count, prefix_by_rank, total_buf);

    MPI_Scatter(rank() == static_cast<size_t>(root) ? prefix_by_rank.data() : nullptr,
                icount, mpi_float_dtype(), prefix, icount, mpi_float_dtype(), root,
                MPI_COMM_WORLD);

    if (rank() == static_cast<size_t>(root))
        std::copy(total_buf.begin(), total_buf.end(), total);
    MPI_Bcast(total, icount, mpi_float_dtype(), root, MPI_COMM_WORLD);
}

void host_gather_size(size_t local_size, size_t *root_sizes, size_t root)
{
    ensure_runtime_active("host_gather_size requires active MPI runtime");
    const unsigned long long send = static_cast<unsigned long long>(local_size);
    std::vector<unsigned long long> root_sizes_ull;
    if (rank() == root)
        root_sizes_ull.resize(nprocs(), 0);

    MPI_Gather(const_cast<unsigned long long *>(&send), 1, MPI_UNSIGNED_LONG_LONG,
               rank() == root ? root_sizes_ull.data() : nullptr,
               1, MPI_UNSIGNED_LONG_LONG, static_cast<int>(root), MPI_COMM_WORLD);

    if (rank() == root)
    {
        if (root_sizes == nullptr)
            abort("host_gather_size root_sizes is null on root");
        for (size_t i = 0; i < nprocs(); i++)
            root_sizes[i] = static_cast<size_t>(root_sizes_ull[i]);
    }
}

void host_gatherv(const void *send_data, size_t send_bytes,
                  void *root_data, const size_t *root_sizes,
                  const size_t *root_displs, size_t root)
{
    ensure_runtime_active("host_gatherv requires active MPI runtime");
    const int send_count = checked_int_count(send_bytes, "host_gatherv send bytes exceed MPI int range");

    std::vector<int> recv_counts;
    std::vector<int> recv_displs;
    if (rank() == root)
    {
        if (root_data == nullptr && send_bytes != 0)
            abort("host_gatherv root_data is null on root");
        if (root_sizes == nullptr || root_displs == nullptr)
            abort("host_gatherv root layout is null on root");
        recv_counts.resize(nprocs(), 0);
        recv_displs.resize(nprocs(), 0);
        for (size_t i = 0; i < nprocs(); i++)
        {
            recv_counts[i] = checked_int_count(root_sizes[i], "host_gatherv recv bytes exceed MPI int range");
            recv_displs[i] = checked_int_count(root_displs[i], "host_gatherv displacement exceeds MPI int range");
        }
    }

    MPI_Gatherv(const_cast<void *>(send_data), send_count, MPI_BYTE,
                root_data,
                rank() == root ? recv_counts.data() : nullptr,
                rank() == root ? recv_displs.data() : nullptr,
                MPI_BYTE, static_cast<int>(root), MPI_COMM_WORLD);
}

} // namespace ZXHSim
