#include "zxhsim/runtime.h"

#include <cuda_runtime.h>
#include <mpi.h>

#if defined(ZXHSIM_USE_NCCL)
#include <nccl.h>
#endif

#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

namespace ZXHSim
{

namespace
{
size_t g_rank = 0;
size_t g_nprocs = 1;
bool g_initialized = false;

#if defined(ZXHSIM_USE_NCCL)
ncclComm_t g_nccl_comm = nullptr;
#endif

bool is_power_of_two(size_t n)
{
    return n != 0 && (n & (n - 1)) == 0;
}

bool mpi_runtime_active()
{
    int initialized = 0;
    MPI_Initialized(&initialized);
    if (!initialized)
        return false;

    int finalized = 0;
    MPI_Finalized(&finalized);
    return finalized == 0;
}

void check_cuda(cudaError_t err, const char *what)
{
    if (err == cudaSuccess)
        return;
    abort(std::string(what) + ": " + cudaGetErrorString(err));
}

#if defined(ZXHSIM_USE_NCCL)
void check_nccl(ncclResult_t err, const char *what)
{
    if (err == ncclSuccess)
        return;
    abort(std::string(what) + ": " + ncclGetErrorString(err));
}
#endif

void bind_visible_device_zero()
{
    int device_count = 0;
    check_cuda(cudaGetDeviceCount(&device_count), "cudaGetDeviceCount failed");
    if (device_count < 1)
        abort("mpi_cuda init requires at least one visible CUDA device per rank");

    check_cuda(cudaSetDevice(0), "cudaSetDevice(0) failed");

    int current_device = -1;
    check_cuda(cudaGetDevice(&current_device), "cudaGetDevice failed");
    if (current_device != 0)
        abort("mpi_cuda init requires each rank to bind to its visible device 0");
}

#if defined(ZXHSIM_USE_NCCL)
void require_unique_host_local_device_mapping()
{
    int current_device = -1;
    check_cuda(cudaGetDevice(&current_device), "cudaGetDevice failed");

    char local_host[MPI_MAX_PROCESSOR_NAME] = {};
    int local_host_len = 0;
    MPI_Get_processor_name(local_host, &local_host_len);

    char local_bus_id[64] = {};
    check_cuda(cudaDeviceGetPCIBusId(local_bus_id, static_cast<int>(sizeof(local_bus_id)),
                                     current_device),
               "cudaDeviceGetPCIBusId failed");

    struct record_t
    {
        char host[MPI_MAX_PROCESSOR_NAME];
        char bus_id[64];
    };

    record_t local{};
    std::strncpy(local.host, local_host, sizeof(local.host) - 1);
    std::strncpy(local.bus_id, local_bus_id, sizeof(local.bus_id) - 1);

    std::vector<record_t> gathered(g_nprocs);
    MPI_Allgather(&local, static_cast<int>(sizeof(record_t)), MPI_BYTE,
                  gathered.data(), static_cast<int>(sizeof(record_t)), MPI_BYTE,
                  MPI_COMM_WORLD);

    for (size_t i = 0; i < gathered.size(); i++)
    {
        for (size_t j = i + 1; j < gathered.size(); j++)
        {
            if (std::strcmp(gathered[i].host, gathered[j].host) == 0 &&
                std::strcmp(gathered[i].bus_id, gathered[j].bus_id) == 0)
            {
                abort("mpi_cuda runtime requires one MPI rank per physical GPU; "
                      "detected duplicate host-local GPU mapping across ranks");
            }
        }
    }
}

void init_nccl_runtime()
{
    if (g_nccl_comm != nullptr)
        return;
    require_unique_host_local_device_mapping();

    ncclUniqueId unique_id{};
    if (g_rank == 0)
        check_nccl(ncclGetUniqueId(&unique_id), "ncclGetUniqueId failed");

    MPI_Bcast(&unique_id, static_cast<int>(sizeof(unique_id)), MPI_BYTE, 0,
              MPI_COMM_WORLD);
    check_nccl(ncclCommInitRank(&g_nccl_comm, static_cast<int>(g_nprocs),
                                unique_id, static_cast<int>(g_rank)),
               "ncclCommInitRank failed");
}

void finalize_nccl_runtime()
{
    if (g_nccl_comm == nullptr)
        return;

    check_cuda(cudaDeviceSynchronize(), "cudaDeviceSynchronize before ncclCommDestroy failed");
    check_nccl(ncclCommDestroy(g_nccl_comm), "ncclCommDestroy failed");
    g_nccl_comm = nullptr;
}
#endif

[[noreturn]] void runtime_not_initialized()
{
    abort("init must be called before constructing or using ZXH objects");
}

} // namespace

void init(int *argc, char ***argv)
{
    if (g_initialized)
        return;

    int initialized = 0;
    MPI_Initialized(&initialized);
    if (!initialized)
        MPI_Init(argc, argv);

    int mpi_rank = 0;
    int mpi_nprocs = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &mpi_rank);
    MPI_Comm_size(MPI_COMM_WORLD, &mpi_nprocs);

    g_rank = static_cast<size_t>(mpi_rank);
    g_nprocs = static_cast<size_t>(mpi_nprocs);
    if (!is_power_of_two(g_nprocs))
        abort("init requires MPI world size to be a power of two");

    bind_visible_device_zero();
#if defined(ZXHSIM_USE_NCCL)
    init_nccl_runtime();
#endif
    g_initialized = true;
}

void finalize()
{
    if (!g_initialized)
        return;

#if defined(ZXHSIM_USE_NCCL)
    finalize_nccl_runtime();
#endif

    int finalized = 0;
    MPI_Finalized(&finalized);
    if (!finalized)
        MPI_Finalize();

    g_rank = 0;
    g_nprocs = 1;
    g_initialized = false;
}

bool active()
{
    return g_initialized && mpi_runtime_active();
}

size_t rank()
{
    if (!g_initialized)
        runtime_not_initialized();
    return g_rank;
}

size_t nprocs()
{
    if (!g_initialized)
        runtime_not_initialized();
    return g_nprocs;
}

bool runtime_nccl_enabled()
{
#if defined(ZXHSIM_USE_NCCL)
    return g_initialized && g_nccl_comm != nullptr;
#else
    return false;
#endif
}

void *runtime_nccl_comm()
{
#if defined(ZXHSIM_USE_NCCL)
    return reinterpret_cast<void *>(g_nccl_comm);
#else
    return nullptr;
#endif
}

void log(const char *msg)
{
    if (msg == nullptr)
        return;

    if (!mpi_runtime_active())
    {
        std::cout << msg << "\n";
        return;
    }

    int mpi_rank = 0;
    MPI_Comm_rank(MPI_COMM_WORLD, &mpi_rank);
    if (mpi_rank == 0)
        std::cout << msg << "\n";
}

void log(const std::string &msg)
{
    log(msg.c_str());
}

[[noreturn]] void abort(const char *msg)
{
    if (msg != nullptr)
    {
        if (mpi_runtime_active())
        {
            int mpi_rank = 0;
            MPI_Comm_rank(MPI_COMM_WORLD, &mpi_rank);
            if (mpi_rank == 0)
                std::cerr << msg << "\n";
        }
        else
        {
            std::cerr << msg << "\n";
        }
    }

    if (mpi_runtime_active())
        MPI_Abort(MPI_COMM_WORLD, 1);
    std::abort();
}

[[noreturn]] void abort(const std::string &msg)
{
    abort(msg.c_str());
}

} // namespace ZXHSim
