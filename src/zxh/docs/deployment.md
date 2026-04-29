# ZXH-Sim Deployment Guide

## 1. 适用范围与前置条件

本文档只描述 ZXH-Sim 在 `mpi` 与 `mpi_cuda` 场景下的正式部署方案。

当前版本对多卡 / 多节点部署采用以下约束：

1. `Slurm` 是唯一正式支持的部署方式；
2. `mpi_cuda` 的 GPU 映射由 `Slurm` 负责，而不是由 ZXH-Sim 运行时自行推导；
3. ZXH-Sim 运行时只要求每个 rank 至少可见一张 GPU，并固定绑定到当前进程可见的 `device 0`；
4. 同一主机上的不同 rank 不得绑定到同一张物理 GPU；若发生重复映射，运行时会直接 fail fast；
5. `nprocs` 必须为 `2` 的幂；
6. 多节点部署默认按同构节点处理，即各节点的参与 GPU 数、任务数和环境保持一致；
7. 各节点必须具有一致的 MPI / CUDA / Python / 编译器环境，并能访问相同路径的仓库目录、可执行文件与 Python 解释器。

这意味着：对 `mpi_cuda` 而言，真正的 rank-device 映射职责位于调度器层。对用户来说，正式部署的标准入口应始终是 `srun`。
对 benchmark 而言，正式 `Slurm` 运行几何由 suite 内的 `deployment` 字段声明，runner 再据此拼接 `srun` 命令。

## 2. 快速开始：单节点单卡

下面给出一条最小但完整的正式部署路径。它仍然使用调度器启动，即便场景只有单节点单卡。

先准备环境并构建 `mpi_cuda`：

```bash
cp env_template.sh env.sh
source ./env.sh

cmake -S . -B build/mpi_cuda -DZXHSIM_BACKEND=mpi_cuda
cmake --build build/mpi_cuda
```

如果当前 shell 不在 Slurm allocation 内，先申请资源：

```bash
salloc -N1 -n1 --ntasks-per-node=1 --gpus-per-task=1
```

然后启动：

```bash
srun -N1 -n1 --ntasks-per-node=1 --gpus-per-task=1 \
  ./build/mpi_cuda/driver_cat
```

这一步的目标是：

1. 验证当前系统上的 `Slurm + MPI + CUDA` 启动链路可用；
2. 验证 ZXH-Sim 在正式部署契约下能够完成一次最小 `mpi_cuda` 运行。

## 3. 一般流程示例：2 节点 4 卡

下面以 `2` 节点、每节点 `4` 卡为例说明一般部署流程。

### 3.1. 申请资源

```bash
salloc -N2 -n8 --ntasks-per-node=4 --gpus-per-task=1
```

这表示：

1. 总任务数 `nprocs = 8`；
2. 每节点运行 `4` 个 rank；
3. 每个 rank 由 `Slurm` 分配 `1` 张 GPU；
4. `8` 满足 `2` 的幂约束。

### 3.2. 对齐节点环境

在所有参与节点上保证以下内容一致：

1. MPI / CUDA / Python / 编译器环境；
2. 仓库路径；
3. 构建目录路径；
4. 可执行文件路径。

如果节点共享文件系统，只需构建一次即可。
如果节点不共享文件系统，则需要手动保证上述路径和环境保持一致。

### 3.3. 准备构建产物

在统一路径下构建 `mpi_cuda` backend，例如：

```bash
cp env_template.sh env.sh
source ./env.sh

cmake -S . -B build/mpi_cuda -DZXHSIM_BACKEND=mpi_cuda
cmake --build build/mpi_cuda
```

### 3.4. 启动

```bash
srun -N2 -n8 --ntasks-per-node=4 --gpus-per-task=1 \
  ./build/mpi_cuda/driver_cat
```

在该规范下：

1. `Slurm` 负责将 `8` 个 rank 分布到 `2` 个节点；
2. `Slurm` 负责为每个 rank 提供对应的 GPU 可见性；
3. ZXH-Sim 运行时只绑定当前进程可见的 `device 0`。

### 3.5. Benchmark 启动

对正式 benchmark suite，不应手写 `srun` 去包裹每个 worker；而应让 benchmark runner 读取 suite 内的 `deployment` 字段并自动启动对应 job step。

例如 `dev_mpi_cuda` 当前声明：

```yaml
deployment:
  nnodes: 2
  ntasks_per_node: 4
```

则推荐流程为：

```bash
python benchmarks/prepare_suite.py --suite dev_mpi_cuda
python benchmarks/runners/run_suite.py --suite dev_mpi_cuda
python benchmarks/reports/aggregate.py --suite dev_mpi_cuda
```

其中 `run_suite.py` 会自动推导：

1. `nprocs = nnodes * ntasks_per_node`
2. `mpi_cuda` 正式部署固定使用 `--gpus-per-task=1`
3. benchmark worker 通过 `srun` 启动

若站点还要求 `account / partition / qos` 等额外调度参数，推荐先通过 `salloc` 或 `sbatch` 获得 allocation，再在 allocation 内运行上述三步，而不要把站点私有参数写入 suite。

## 4. 配置规范

### 4.1. 调度器规范

当前版本只正式支持 `Slurm`。因此：

1. 多节点部署应通过 `salloc` / `sbatch` / `srun` 完成；
2. `hostfile`、自定义 SSH 启动链路和手工 rank-device 映射不属于正式支持范围；
3. 若目标系统不提供 `Slurm`，则该系统上的多节点部署属于兼容性探索，而不是当前版本的正式用户契约。

### 4.2. `nprocs` 规范

在 `Slurm` 语义下，`nprocs` 对应总任务数，即 `srun -n <nprocs>` 中的 `nprocs`。

约定如下：

1. `nprocs` 必须显式给出；
2. 对 benchmark suite 而言，`nprocs` 由 `deployment.nnodes * deployment.ntasks_per_node` 推导；
3. `nprocs` 必须为 `2` 的幂；
4. `--ntasks-per-node` 应与节点上的参与 GPU 数相匹配；
5. 正式 `mpi_cuda` 部署要求每个 rank 对应一张独占 GPU。

### 4.3. 同构约束

当前部署规范默认按同构节点处理：

1. 各节点使用相同的 MPI / CUDA / Python 环境；
2. 各节点的参与 GPU 数相同；
3. 各节点上的任务排布方式一致；
4. 各节点上的可执行文件路径一致。

### 4.4. 路径与环境约束

多节点运行要求：

1. 所有参与节点都能访问同一路径的可执行文件；
2. 所有参与节点都能访问同一路径的 Python 解释器与仓库目录；
3. 所有参与节点都加载同一套 MPI / CUDA 运行环境；
4. 若使用 `sbatch` 脚本，则脚本内应显式 `source ./env.sh` 或加载等价环境模块。

## 5. Device 绑定

### 5.1. 默认行为

正式部署场景下，device 绑定语义如下：

1. `Slurm` 负责 rank 到物理 GPU 的映射；
2. 每个 rank 启动时，目标 GPU 应当已经成为该进程可见的 `device 0`；
3. ZXH-Sim 运行时固定执行 `cudaSetDevice(0)`；
4. 若某个 rank 启动时看不到任何 GPU，运行时会直接 fail fast；
5. 若同一主机上的多个 rank 实际落到同一张物理 GPU，运行时会在 `init()` 中直接 fail fast。

因此，ZXH-Sim 不在运行时内部做 `local_rank -> device_id` 推导。

### 5.2. 覆写方式

默认情况下，推荐直接依赖 `Slurm` 的 GPU 分配与绑定能力，例如：

```bash
srun -N2 -n8 --ntasks-per-node=4 --gpus-per-task=1 ...
```

如果目标集群要求显式控制 GPU 绑定策略，应继续使用 `Slurm` 自身的选项完成，例如站点规定的 `--gpu-bind` 或等价 GRES 绑定策略。

当前版本不将手工设置每个 rank 的 `CUDA_VISIBLE_DEVICES` 视为正式部署方案。

### 5.3. 实践建议

建议始终遵守以下原则：

1. correctness 测试与正式部署分开处理；
2. 正式性能数据只来自 `Slurm` 管理下的一 rank 一 GPU 部署；
3. 若只是在本机做 `mpi_cuda` 正确性验证，请使用 `testing.md` 与 `benchmarks/README.md` 中描述的本地单进程单卡路径，而不是将其视为正式部署。
