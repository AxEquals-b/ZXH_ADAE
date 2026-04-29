#include "zxhsim/runtime.h"

#include <cstdlib>
#include <iostream>
#include <mpi.h>

namespace ZXHSim
{

namespace
{
size_t g_rank = 0;
size_t g_nprocs = 1;
bool g_initialized = false;

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

    g_initialized = true;
}

void finalize()
{
    if (!g_initialized)
        return;

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
    return false;
}

void *runtime_nccl_comm()
{
    return nullptr;
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
