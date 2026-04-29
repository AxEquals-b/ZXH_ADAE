#pragma once

#include <cstddef>

namespace ZXHSim
{

void runtime_init(int *argc, char ***argv);
void runtime_finalize();
size_t runtime_rank();
size_t runtime_nprocs();
bool runtime_nccl_enabled();
void *runtime_nccl_comm();

} // namespace ZXHSim
