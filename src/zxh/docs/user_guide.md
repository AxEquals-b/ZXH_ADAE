# ZXH-Sim User Guide

## 1. 文档定位

本文档面向第一次接触仓库的用户，回答三个问题：

1. 如何以最小成本先把仓库跑起来；
2. 想切换到其他 backend 时，应当先做什么、再做什么；
3. 想一次验证多个 backend 时，应当使用哪个入口。

如果你只是想先确认仓库能运行，直接看第 2 节即可。

## 2. 最小使用流程

### 2.1. 默认 `single` backend

先准备本地环境文件：

```bash
cp env_template.sh env.sh
source ./env.sh
```

然后直接构建：

```bash
cmake -S . -B build
cmake --build build
./build/driver_cat
```

如果使用 Python 前端：

```bash
pip install .
python examples/python/driver_cat.py
```

如果需要运行 QASM 示例，还需要安装 `qiskit`：

```bash
pip install qiskit
python examples/python/driver_qasm.py
```

### 2.2. 什么时候需要继续往下看

当你遇到以下情况时，再继续阅读后续章节：

- 上述最小构建失败；
- 你需要指定自己的编译器路径；
- 你要构建 `omp / cuda / mpi / mpi_omp / mpi_cuda` 中的某个 backend；
- 你要一次验证多个 backend；
- 你要在 CUDA 或 `cu-bridge` 环境下复现特定构建行为。

## 3. 选择 Backend

ZXH-Sim 支持多个执行 backend，backend 在编译时确定。

选择 backend 时，可以先回答两个问题：

1. 是否启用 MPI，即 `MPI=OFF` 或 `MPI=ON`， 启用MPI需要可用的MPI编译器与运行时环境；
2. 单节点内采用 `single`、`omp` 还是 `cuda` 执行方式，启用`cuda`需要兼容CUDA的编译器。

这两个维度相互独立，因此 backend 空间可以看作一个 `2 x 3` 矩阵：

| Backend | MPI | 单节点执行方式 | 典型场景 | 需要关注的环境变量 |
| --- | --- | --- | --- | --- |
| `single` | OFF | `single` | 默认 CPU 路径 | 通常无需额外变量 |
| `omp` | OFF | `omp` | 单节点 CPU 多线程 | 通常无需额外变量 |
| `cuda` | OFF | `cuda` | 单节点单 GPU | `CUDACXX`、`CUDAARCHS`、`CUB_ROOT` |
| `mpi` | ON | `single` | 多进程 CPU | `MPICXX` |
| `mpi_omp` | ON | `omp` | 多进程 CPU + 进程内多线程 | `MPICXX` |
| `mpi_cuda` | ON | `cuda` | 多进程 GPU | `MPICXX`、`CUDACXX`、`CUDAARCHS`、`CUB_ROOT` |

如果不显式指定 backend，当前构建系统默认使用 `single`。

对单 backend 构建，backend 的指定方式是：

```bash
cmake -S . -B build/mpi -DZXHSIM_BACKEND=mpi
```

Python 构建可使用环境变量形式：

```bash
ZXHSIM_BACKEND=mpi pip install .
```

`env.sh` 不负责选择 backend，它只负责工具链环境变量。
旧的 `USE_MPI / USE_OMP / USE_CUDA` 顶层 backend 选择方式已移除。

完成 `cmake configure` 后，ZXH-Sim 会打印一组构建摘要，当前用户需要关注的字段为：

- `Backend`
- `Node execution mode`
- `MPI support`
- `OpenMP support`
- `CUDA support`
- `Python frontend`

其中：

- `Backend` 是当前选中的正式 backend 名称；
- `Node execution mode` 只描述单节点内的执行方式，即 `single / omp / cuda`；
- `MPI support / OpenMP support / CUDA support` 是由 backend 派生出的能力开关，而不是新的 backend 选择入口；
- `Python frontend` 表示本次构建是否生成 Python 扩展模块。

## 4. 准备环境变量

### 4.1. `env.sh` 说明

选定 backend 后，使用 `env.sh` 设置工具链环境变量，例如编译器路径、MPI wrapper 路径、CUDA 前端路径和相关运行时目录。
`env.sh` 包含全部backend相关的环境变量，但需要关注的只有需要用到的部分。
在变量留空时，通常会交由构建系统自动推导默认值，推导失败则返回构建错误。
`env.sh` 也是 benchmark stage 的正式构建入口环境；`pip install .`、`python benchmarks/prepare_suite.py` 等路径都会复用当前 shell 中已导出的变量，因此不要只把 CUDA 依赖写进 `~/.bashrc`。
下面是一些常用的环境变量：

| 变量 | 何时需要 |
| --- | --- |
| `CXX` | `MPI=OFF` 场景下需要显式指定 C++ 编译器时 |
| `MPICXX` | `MPI=ON` 场景下需要显式指定 MPI C++ wrapper 时 |
| `CUDACXX` | `CUDA=ON` 场景下需要显式指定 CUDA 编译前端时 |
| `CUDAARCHS` | `CUDA=ON` 场景下通常应显式设置 |
| `CUB_ROOT` | `CUDA=ON` 场景下，CUB 不在系统默认前缀时 |
| `CMAKE_PREFIX_PATH` | 需要把外部 CMake package 前缀传给 `find_package(...)` 时 |

此外， `OMP_NUM_THREADS`、`CUDA_VISIBLE_DEVICES` 等属于运行时变量，而不是构建变量，因而不出现在上表中。详见第5节：运行环境

### 4.2. CUB 依赖

当前 `cuda / mpi_cuda` backend 通过 `find_package(CUB CONFIG)` 查找 CUB。
如果 CUB 不在系统默认前缀中，建议在 `env.sh` 中同时导出：

```bash
export CUB_ROOT="$HOME/.local"
export CMAKE_PREFIX_PATH="$CUB_ROOT${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"
```

这里 `CUB_ROOT` 应当指向 package prefix，而不是直接指向头文件目录。典型布局为：

```text
$CUB_ROOT/include/cub
$CUB_ROOT/lib/cmake/cub
```

如果你是在当前机器上按本地习惯放到 `$HOME/tools/cub`，则只需要把上面的前缀路径替换成对应目录。

### 4.3. `cu-bridge` 相关变量

ZXH-Sim提供 `cu-bridge` 兼容支持。
如果使用标准 `nvcc`，通常不需要下面这些变量。
只有在使用 `cu-bridge` 时，才需要继续关注：

| 变量 | 何时需要 |
| --- | --- |
| `CUDAFLAGS` | CUDA 前端还要求额外参数时 |
| `CUDA_PATH` | `CUDACXX` 不在标准位置，或需要显式指定 CUDA / `cu-bridge` 前端前缀时 |
| `ZXHSIM_CU_BRIDGE_RUNTIME_ROOT` | `cu-bridge` 运行时前缀无法按标准布局推导时 |
| `ZXHSIM_CU_BRIDGE_SYSTEM_INCLUDE_DIRS` | `cu-bridge` 头文件目录不满足默认布局时 |
| `ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES` | `cu-bridge` 库目录不满足默认布局时 |
| `ZXHSIM_CU_BRIDGE_LINK_LIBRARIES` | `CUDACXX=cucc` 时显式提供运行时库列表 |

说明：

- 分号分隔的列表变量应使用引号，例如 `"a;b;c"`；
- 对标准 `nvcc` 构建，不需要设置 `ZXHSIM_CU_BRIDGE_*` 变量。

下面是一个在 `cuda` backend 场景下使用 `cu-bridge` 的示例：

```bash
export CUDACXX=/path/to/tools/cu-bridge/bin/cucc
export CUDA_PATH=/path/to/tools/cu-bridge
export CUDAARCHS=70
export ZXHSIM_CU_BRIDGE_RUNTIME_ROOT=/path/to/cu-bridge-runtime
export ZXHSIM_CU_BRIDGE_SYSTEM_INCLUDE_DIRS="/path/to/cu-bridge-runtime/include;/path/to/cu-bridge-runtime/include/hcr"
export ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES="/path/to/cu-bridge-runtime/lib"
export ZXHSIM_CU_BRIDGE_LINK_LIBRARIES="runtime_cu;ToolsExt_cu;hccompiler;hcruntime;stdc++;m;gcc_s;c;dl;rt;pthread"
# 可选
# export CUDAFLAGS=-gcc-version=11
```

## 5. 运行环境

### 5.1. OpenMP

- 需要编译器和运行环境支持 OpenMP；
- 线程数可用 `OMP_NUM_THREADS` 控制。

### 5.2. MPI

- 通过 `mpirun` 或等价 launcher 启动；
- 多节点场景要求各节点能访问相同二进制和运行环境。

### 5.3. CUDA

- 需要可用 GPU 和对应运行时；
- 建议设置：

```bash
export CUDA_DEVICE_ORDER=PCI_BUS_ID
```

### 5.4. MPI + CUDA

本地最小使用流程默认只面向正确性验证，而不面向正式部署。

对本机上的 `mpi_cuda` 最小运行，推荐只启动 `1` 个 MPI rank，并显式收窄 GPU 可见性：

```bash
export CUDA_VISIBLE_DEVICES=0
```

在这一默认路径下：

1. `mpi_cuda` 本地 smoke 固定为单进程单卡；
2. ZXH-Sim 运行时会固定绑定到当前进程可见的 `device 0`；
3. 若检测到多个 MPI rank 绑定到同一张物理 GPU，运行时会直接 fail fast；
4. 正式的多进程多卡 / 多节点运行应交由部署层提供一 rank 一 GPU 映射。

如果需要真实的多卡 / 多节点部署，请继续阅读 [deployment.md](./deployment.md)。
当前版本只正式支持基于 `Slurm` 的部署方案。

## 6. 示例程序

- C++ 示例：[examples/cpp/driver_cat.cpp](../examples/cpp/driver_cat.cpp)
- Python 示例：[examples/python/driver_cat.py](../examples/python/driver_cat.py)
- Python + QASM：[examples/python/driver_qasm.py](../examples/python/driver_qasm.py)
