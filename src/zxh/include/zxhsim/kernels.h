#pragma once

#include "zxhsim/defs.h"

#include <vector>

namespace ZXHSim
{

// Synchronize backend kernels once at a phase boundary.
void kernel_sync();

// Block-local U3: in-place pair mixing within one local block.
void u3_block_kernel(val_t *ptr1, size_t local_bits, raddr_t delta_so, selector_t S_block, val_t u00, val_t u01,
                     val_t u10, val_t u11);

// Block-local explicit X/CX permutations used by ablation mode.
void x_block_kernel(val_t *ptr, size_t local_bits, raddr_t delta_so, selector_t S_q_block);
void cx_block_kernel(val_t *ptr, size_t local_bits, raddr_t delta_so, selector_t S_cq_block, selector_t S_q_block);

// Block-local U3 batch over one local block.
void u3_block_batch_kernel(val_t *ptr1, size_t local_bits, const std::vector<u3_batch_desc_t> &descs);

// Intra U3: pair mixing across two local segments.
void u3_intra_kernel(val_t *ptr1, val_t *ptr2, size_t I, raddr_t delta_o, selector_t S_k, val_t u00, val_t u01,
                     val_t u10, val_t u11);

// Inter U3: pair mixing using a remote readonly segment snapshot.
void u3_inter_kernel(val_t *ptr1, const val_t *ptr2, size_t I, raddr_t delta_o, selector_t S_k, val_t u00, val_t u01,
                     val_t u10, val_t u11);

// P gate kernel over one local block.
void p_block_kernel(val_t *ptr, size_t local_bits, selector_t S_block, float_t theta);

// Diagonal window lifecycle.
void diag_pending_reset();
void diag_pending_push_p(selector_t S_block, float_t theta);
bool diag_pending_try_push_cp(selector_t S_cq_block, selector_t S_q_block, float_t theta);
bool diag_pending_empty();
void diag_pending_flush(val_t *ptr, size_t local_bits);

// P gate kernel batch over one local block.
void p_block_batch_kernel(val_t *ptr, size_t local_bits, std::vector<selector_t> S_block, std::vector<float_t> theta);

// CP kernel over one local block.
void cp_kernel(val_t *ptr, size_t local_bits, selector_t S_cq_block, selector_t S_q_block, float_t theta);

} // namespace ZXHSim
