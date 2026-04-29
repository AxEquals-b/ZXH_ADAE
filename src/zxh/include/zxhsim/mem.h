#pragma once

#include "zxhsim/defs.h"

namespace ZXHSim
{

// Worker memory may reside in host memory or device memory depending on backend.
val_t *worker_alloc(size_t elem_count);
void worker_free(val_t *ptr);
val_t *worker_realloc(val_t *old_ptr, size_t old_elem_count, size_t new_elem_count);
void worker_set_zero(val_t *ptr, size_t begin, size_t end);
void worker_mem_set(val_t *ptr, val_t value);
void worker_copy_to_host(val_t *dst, const val_t *src, size_t elem_count);

// Host memory always resides in system memory.
val_t *host_alloc(size_t elem_count);
void host_free(val_t *ptr);
void host_set_zero(val_t *ptr, size_t begin, size_t end);

} // namespace ZXHSim
