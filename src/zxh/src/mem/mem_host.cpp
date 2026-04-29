#include "zxhsim/mem.h"

#include <algorithm>
#include <cstdlib>
#include <cstdio>
#include <mutex>
#include <unordered_map>
#include <unistd.h>

namespace ZXHSim
{
namespace
{
val_t zero_val()
{
    return val_t(0.0, 0.0);
}

void fill_zero(val_t *ptr, size_t begin, size_t end)
{
    if (ptr == nullptr || begin >= end)
        return;

    for (size_t i = begin; i < end; i++)
        ptr[i] = zero_val();
}

const char *rank_env()
{
    const char *rank = std::getenv("PMI_RANK");
    if (rank != nullptr)
        return rank;
    rank = std::getenv("OMPI_COMM_WORLD_RANK");
    if (rank != nullptr)
        return rank;
    rank = std::getenv("MV2_COMM_WORLD_RANK");
    if (rank != nullptr)
        return rank;
    return "na";
}

bool mem_trace_enabled()
{
    const char *env = std::getenv("ZXHSIM_MEM_TRACE");
    return env != nullptr && env[0] != '\0' && env[0] != '0';
}

bool mem_trace_verbose()
{
    const char *env = std::getenv("ZXHSIM_MEM_TRACE_VERBOSE");
    return env != nullptr && env[0] != '\0' && env[0] != '0';
}

struct mem_tracker_t
{
    std::mutex mu;
    std::unordered_map<const void *, size_t> bytes_by_ptr;
    size_t current_bytes = 0;
    size_t peak_bytes = 0;
    bool enabled = mem_trace_enabled();
    bool verbose = mem_trace_verbose();

    static mem_tracker_t &instance()
    {
        static mem_tracker_t inst;
        return inst;
    }

    mem_tracker_t()
    {
        if (enabled)
            std::atexit(&mem_tracker_t::dump_summary_atexit);
    }

    static void dump_summary_atexit()
    {
        mem_tracker_t::instance().dump_summary();
    }

    void note_alloc(const void *ptr, size_t elem_count)
    {
        if (!enabled || ptr == nullptr || elem_count == 0)
            return;

        const size_t bytes = elem_count * sizeof(val_t);
        std::lock_guard<std::mutex> lock(mu);
        bytes_by_ptr[ptr] = bytes;
        current_bytes += bytes;
        peak_bytes = std::max(peak_bytes, current_bytes);

        if (verbose)
        {
            std::fprintf(stderr, "[ZXHSim][mem_host][pid=%d][rank=%s] alloc ptr=%p bytes=%zu current=%zu peak=%zu\n",
                         static_cast<int>(::getpid()), rank_env(), ptr, bytes, current_bytes, peak_bytes);
        }
    }

    void note_free(const void *ptr)
    {
        if (!enabled || ptr == nullptr)
            return;

        std::lock_guard<std::mutex> lock(mu);
        auto it = bytes_by_ptr.find(ptr);
        if (it == bytes_by_ptr.end())
            return;

        const size_t bytes = it->second;
        current_bytes = (current_bytes >= bytes) ? (current_bytes - bytes) : 0;
        bytes_by_ptr.erase(it);

        if (verbose)
        {
            std::fprintf(stderr, "[ZXHSim][mem_host][pid=%d][rank=%s] free  ptr=%p bytes=%zu current=%zu peak=%zu\n",
                         static_cast<int>(::getpid()), rank_env(), ptr, bytes, current_bytes, peak_bytes);
        }
    }

    void dump_summary()
    {
        if (!enabled)
            return;

        std::lock_guard<std::mutex> lock(mu);
        const double peak_mib = static_cast<double>(peak_bytes) / (1024.0 * 1024.0);
        std::fprintf(stderr,
                     "[ZXHSim][mem_host][summary][pid=%d][rank=%s] peak_bytes=%zu peak_mib=%.3f current_bytes=%zu "
                     "live_allocs=%zu\n",
                     static_cast<int>(::getpid()), rank_env(), peak_bytes, peak_mib, current_bytes,
                     bytes_by_ptr.size());
    }
};
} // namespace

val_t *worker_alloc(size_t elem_count)
{
    if (elem_count == 0)
        return nullptr;

    val_t *ptr = new val_t[elem_count];
    fill_zero(ptr, 0, elem_count);
    mem_tracker_t::instance().note_alloc(ptr, elem_count);
    return ptr;
}

void worker_free(val_t *ptr)
{
    mem_tracker_t::instance().note_free(ptr);
    delete[] ptr;
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
        for (size_t i = 0; i < keep; i++)
            new_ptr[i] = old_ptr[i];
        worker_free(old_ptr);
    }
    return new_ptr;
}

void worker_set_zero(val_t *ptr, size_t begin, size_t end)
{
    fill_zero(ptr, begin, end);
}

void worker_mem_set(val_t *ptr, val_t value)
{
    if (ptr == nullptr)
        return;
    *ptr = value;
}

void worker_copy_to_host(val_t *dst, const val_t *src, size_t elem_count)
{
    if (elem_count == 0 || dst == nullptr || src == nullptr)
        return;
    std::copy_n(src, elem_count, dst);
}

val_t *host_alloc(size_t elem_count)
{
    if (elem_count == 0)
        return nullptr;
    val_t *ptr = new val_t[elem_count];
    mem_tracker_t::instance().note_alloc(ptr, elem_count);
    return ptr;
}

void host_free(val_t *ptr)
{
    mem_tracker_t::instance().note_free(ptr);
    delete[] ptr;
}

void host_set_zero(val_t *ptr, size_t begin, size_t end)
{
    fill_zero(ptr, begin, end);
}

} // namespace ZXHSim
