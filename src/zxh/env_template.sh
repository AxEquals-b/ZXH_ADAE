#!/usr/bin/env bash

# Copy this file to env.sh and edit the values for your machine:
#   cp env_template.sh env.sh
#   source ./env.sh

# This file is for machine-specific toolchain paths only.
# Do not pin backend selection here.
#
# Select backend per build instead:
#   cmake -S . -B build/<backend> -DZXHSIM_BACKEND=<backend>
#   ZXHSIM_BACKEND=<backend> pip install .
#
# Valid backends:
#   single, omp, cuda, mpi, mpi_omp, mpi_cuda

# Optional PATH adjustments
# export PATH="$HOME/.local/bin:${PATH}"
# export PATH="/path/to/mpi/bin:${PATH}"
# export PATH="/path/to/cuda-or-cu-bridge/bin:${PATH}"

# MPI toolchain
# export MPI_CXX_COMPILER=/path/to/mpicxx
# export MPICXX="${MPI_CXX_COMPILER}"

# CUDA toolchain
# export CUDACXX=/path/to/nvcc
# export CUDACXX=/path/to/tools/cu-bridge/bin/cucc
# export CUDA_PATH=/path/to/tools/cu-bridge
# export CUDAARCHS=70
# Optional external CUB package prefix used by find_package(CUB CONFIG).
# Example local install layout:
#   $HOME/.local/include/cub
#   $HOME/.local/lib/cmake/cub
# export CUB_ROOT="$HOME/.local"
# export CMAKE_PREFIX_PATH="$CUB_ROOT${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
# export CUDAFLAGS=-gcc-version=11

# cu-bridge runtime contract
# Only needed when CUDACXX points to cucc.
# Use quoted semicolon-separated lists.
# export ZXHSIM_CU_BRIDGE_RUNTIME_ROOT=/path/to/cu-bridge-runtime
# export ZXHSIM_CU_BRIDGE_SYSTEM_INCLUDE_DIRS="/path/to/cu-bridge-runtime/include;/path/to/cu-bridge-runtime/include/hcr"
# export ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES="/path/to/cu-bridge-runtime/lib"
# export ZXHSIM_CU_BRIDGE_LINK_LIBRARIES="runtime_cu;ToolsExt_cu;hccompiler;hcruntime;stdc++;m;gcc_s;c;dl;rt;pthread"
