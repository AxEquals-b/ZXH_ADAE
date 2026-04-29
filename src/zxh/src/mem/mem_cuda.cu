#include "zxhsim/mem.h"
#include "zxhsim/runtime.h"

#include <algorithm>
#include <cuda_runtime.h>
#include <string>

namespace ZXHSim
{
namespace
{
void check_cuda(cudaError_t err, const char *what)
{
    if (err == cudaSuccess)
        return;
    abort(std::string(what) + ": " + cudaGetErrorString(err));
}

void fill_zero_host(val_t *ptr, size_t begin, size_t end)
{
    if (ptr == nullptr || begin >= end)
        return;
    std::fill(ptr + begin, ptr + end, val_t(0.0, 0.0));
}

} // namespace

val_t *worker_alloc(size_t elem_count)
{
    if (elem_count == 0)
        return nullptr;

    val_t *ptr = nullptr;
    check_cuda(cudaMalloc(reinterpret_cast<void **>(&ptr), elem_count * sizeof(val_t)), "cudaMalloc failed");
    check_cuda(cudaMemset(ptr, 0, elem_count * sizeof(val_t)), "cudaMemset failed");
    return ptr;
}

void worker_free(val_t *ptr)
{
    if (ptr == nullptr)
        return;
    check_cuda(cudaFree(ptr), "cudaFree failed");
}

val_t *worker_realloc(val_t *old_ptr, size_t old_elem_count, size_t new_elem_count)
{
    if (new_elem_count == 0)
    {
        worker_free(old_ptr);
        return nullptr;
    }

    val_t *new_ptr = worker_alloc(new_elem_count);
    if (old_ptr != nullptr)
    {
        const size_t keep = std::min(old_elem_count, new_elem_count);
        if (keep > 0)
        {
            check_cuda(cudaMemcpy(new_ptr, old_ptr, keep * sizeof(val_t), cudaMemcpyDeviceToDevice),
                       "cudaMemcpy D2D failed");
        }
        worker_free(old_ptr);
    }
    return new_ptr;
}

void worker_set_zero(val_t *ptr, size_t begin, size_t end)
{
    if (ptr == nullptr || begin >= end)
        return;

    check_cuda(cudaMemset(ptr + begin, 0, (end - begin) * sizeof(val_t)), "cudaMemset range failed");
}

void worker_mem_set(val_t *ptr, val_t value)
{
    if (ptr == nullptr)
        return;
    check_cuda(cudaMemcpy(ptr, &value, sizeof(val_t), cudaMemcpyHostToDevice), "cudaMemcpy H2D scalar failed");
}

void worker_copy_to_host(val_t *dst, const val_t *src, size_t elem_count)
{
    if (elem_count == 0 || dst == nullptr || src == nullptr)
        return;
    check_cuda(cudaMemcpy(dst, src, elem_count * sizeof(val_t), cudaMemcpyDeviceToHost), "cudaMemcpy D2H failed");
}

val_t *host_alloc(size_t elem_count)
{
    if (elem_count == 0)
        return nullptr;

    val_t *ptr = nullptr;
    check_cuda(cudaMallocHost(reinterpret_cast<void **>(&ptr), elem_count * sizeof(val_t)),
               "cudaMallocHost failed");
    return ptr;
}

void host_free(val_t *ptr)
{
    if (ptr == nullptr)
        return;
    check_cuda(cudaFreeHost(ptr), "cudaFreeHost failed");
}

void host_set_zero(val_t *ptr, size_t begin, size_t end)
{
    fill_zero_host(ptr, begin, end);
}

} // namespace ZXHSim
