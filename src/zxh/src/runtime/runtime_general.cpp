#include "zxhsim/runtime.h"

#include <cstdlib>
#include <iostream>

namespace ZXHSim
{

namespace
{
size_t g_rank = 0;
size_t g_nprocs = 1;
bool g_initialized = false;

[[noreturn]] void runtime_not_initialized()
{
    abort("init must be called before constructing or using ZXH objects");
}

} // namespace

void init(int *argc, char ***argv)
{
    (void)argc;
    (void)argv;
    g_rank = 0;
    g_nprocs = 1;
    g_initialized = true;
}

void finalize()
{
    g_rank = 0;
    g_nprocs = 1;
    g_initialized = false;
}

bool active()
{
    return g_initialized;
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
    std::cout << msg << "\n";
}

void log(const std::string &msg)
{
    log(msg.c_str());
}

[[noreturn]] void abort(const char *msg)
{
    if (msg != nullptr)
        std::cerr << msg << "\n";
    std::abort();
}

[[noreturn]] void abort(const std::string &msg)
{
    abort(msg.c_str());
}

} // namespace ZXHSim
