# ZXH-Sim Roadmap

## 1. 说明

本文档同时承担以下角色：

- 已归档版本：作为简要 `CHANGELOG`
- 后续版本：作为 roadmap 与 milestone 规划

项目的架构抽象与接口设计以 [tech_spec.md](./tech_spec.md) 为唯一真源；本文件只描述版本推进路径，不重复维护技术细节。当前工作的细粒度任务拆分与执行状态不再记录于本文件，而由 workspace 负责维护。

## 2. CHANGELOG

### v0.1.0

- 建立 ZXH-Sim 基本项目结构与构建系统
- 建立 `bitvec_t`、`bitmat_t`、`selector_t`、`ZXH` 等核心数据结构与接口
- 支持 C++ / Python 两个前端入口
- 建立 `single / mpi / cuda / mpi_cuda` 的后端分层骨架
- 建立技术规格文档 `tech_spec.md`

### v0.2.0

- 完成 `core / sv / mem / kernel / measure` 的模块拆分
- 明确 `vaddr_t / raddr_t` 地址体系与运行时分层
- 建立状态向量与测量路径的最小可运行实现
- 打通 `single / mpi / cuda / mpi_cuda` 的基础后端路径

### v0.2.3

- 完成 `runtime` 与 `comm` 模块拆分，并收敛后端命名与文件布局
- 将 backend 选择统一收敛到 `环境变量 -> CMake` 契约
- 建立 integration `build/run smoke` 测试 MVP，并归档 `user_guide.md`、`testing.md` 与新版 `README.md`

### v0.2.4

- 修复 `mpicxx` wrapper `REALPATH` 与 `FindMPI` 返回空 include dir 导致的 `mpi_cuda` 构建问题
- 新增 `cu-bridge` 兼容层，同时保持标准 `nvcc` 路径不受影响
- 将目标系统特有的 `cu-bridge` include/link 细节从仓库硬编码移出为环境变量契约
- 更新 `user_guide.md`、`env_template.sh` 与 `testing.md`，使目标系统开发者可以按文档复现构建流程
- 在本机与目标系统上完成 `build/run smoke` 验证

### v0.3.0

- 冻结 `public API` 边界，明确 `zxh.h / runtime.h / types.h` 为稳定入口，并将其余头文件收敛为 `internal API`
- 收敛 `runtime / comm / sv / measure / zxh` 的模块分层，清理已知 DAG 破坏，使代码结构与 `tech_spec.md` 对齐
- 重写并落实测量抽象：引入 `prob_scan_t / threshold_stream_t / segment_cdf_t` 语义，并在各 backend 中实现统一的流式测量路径
- 明确测量数值语义：`sum_block_prob` 采用 merge sum，`worker / segment` 前缀统一采用 tree-based exclusive scan
- 补充 `ZXH::set_seed(...)` 与 Python 绑定，建立同一 `seed`、同一环境、同一 backend 下的可复现性契约
- 将 `seed` 可复现性 smoke 纳入 integration 测试，并完成 `single / omp / mpi / cuda / mpi_cuda` 全矩阵 smoke 验证

### v0.3.1

- 将 backend 选择进一步收敛到 `ZXHSIM_BACKEND` 单一入口，并清理用户侧构建契约中的冗余分支
- 清理 CMake configure 输出，统一改为 `Backend / Node execution mode / MPI support / OpenMP support / CUDA support / Python frontend`
- 建立 `benchmarks/` 模块 MVP，并打通 `prepare / run / aggregate` 三段式开发期 benchmark 流程
- 建立 `single / omp / cuda / mpi / mpi_omp / mpi_cuda` 全 backend benchmark smoke
- 新增 `dev_mpi_cuda` 开发期性能 suite，形成 `mpi_cuda` 的稳定性能观察面
- 更新 `README.md`、`user_guide.md`、`testing.md` 与 benchmark 文档，使构建、测试与 benchmark 契约对齐

### v0.3.2

- 收口 `mpi_cuda` 运行时契约：每个 rank 固定绑定当前进程可见的 `device 0`，将 rank-device 映射职责留给外部部署层
- 重写 `deployment.md`，明确 `Slurm` 为唯一正式支持的多卡 / 多节点部署方案
- 将本地 correctness / benchmark smoke 与正式 deployment 分层：`mpi_cuda` 本地 smoke 收口为单进程单卡最小路径
- 为 benchmark suite 引入最小 `deployment` 几何配置，并接通 `dev_mpi_cuda -> srun` 的正式运行路径
- 扩展 benchmark 环境记录，纳入 `Slurm` 相关元数据，并完成全 backend benchmark smoke 回归

### v0.4.0

- 将 benchmark 从 smoke MVP 推进到正式开发期性能入口，建立 `prepare / run / aggregate` 的标准运行闭环
- 收敛 benchmark 与 deployment 契约：本地 `mpi_cuda` smoke 固定为单进程单卡，正式多卡 / 多节点路径统一走 `Slurm`
- 完成 `dev_mpi_cuda` 与 `dev2_mpi_cuda` 两组 `mpi_cuda` 开发期 suite，覆盖 `16-24` 与 `25-32` qubit 区间的性能观察面
- 补齐 benchmark workload 规模梯度，形成面向开发期性能测试的标准 `qasm` 数据集组织方式
- 在本机完成 benchmark smoke 回归，并在目标系统上完成 `Slurm` 路径的 `dev_mpi_cuda` 运行验证
- 使 `mpi_cuda` benchmark 能够在不同环境上完成配置、部署与运行，并产出多节点性能数据

### v0.4.1

- 将 `mpi_cuda` 运行时进一步收口到“一 rank 一 GPU”语义；若同一主机上的多个 rank 映射到同一张物理 GPU，则在 `init()` 阶段直接 fail fast
- 为 `mpi_cuda` 引入 `NCCL` 生命周期管理与运行时探测接口，为后续通信快路径实现做准备
- 将 `comm_mpi_cuda` 重构为 transport 分层，并为 `NCCL` 通信路径落地留出稳定接入点
- 将本地 `mpi_cuda` integration / benchmark smoke 收口为单进程单卡最小路径，避免与正式 deployment 契约混淆

### v0.4.2

- 将 `mpi_cuda` 通信路径进一步收口到 `NCCL` 单一路径，并同步对齐 `runtime / comm` 接口
- 将 `cuda / mpi_cuda` 测量路径中的 `segment_cdf` 前缀扫描切换为 `CUB` 实现，解除原有单 block scan 路径的扩展限制
- 将开发期 benchmark QASM workload 收口到仓库内 `benchmarks/workloads/qasm/`，不再依赖 `workspace/` 下的本地数据
- 将外部 `CUB` 依赖收口为 `env.sh -> benchmark stage -> CMake find_package(CUB CONFIG)` 的统一构建契约
- 同步更新 `README.md`、`user_guide.md`、benchmark 文档与本 roadmap，使构建、部署与 benchmark 契约一致

### v0.4.3

- 将门执行路径中本地 `delta_b=0` 的 kernel 语义正式收口为 `block_kernel`，不再沿用 `reflexive` 命名复用整块本地地址空间
- 同步更新 `tech_spec.md`，使 `H/U3/Z` 路径中的 kernel 粒度说明与当前 block-local 实现一致
- 更新项目版本号，为 `0.4.3` 归档做准备

## 3. 规划版本

### v0.5.0: CUDA + MPI Performance Strategy

目标：实现 `CUDA + MPI` 预定的性能优化策略。

里程碑：

- 落地 `CUDA + MPI` 通信与测量路径的预定优化方案
- 完成与执行模型相匹配的异步、双缓冲与流水化实现
- 围绕既定 `NCCL` 路线继续完善高性能 `mpi_cuda` 实现，例如拓扑友好的通信调度、测量/通信协同与流水化优化
- 建立针对 `mpi_cuda` 的专项性能实验与对比基线

### v0.6.0: Circuit Optimization

目标：完成`tech_spec.md`中预定的电路优化功能。

### v0.7.0: Advanced Features

目标：在稳定执行模型上扩展更高层功能。

候选方向：

- 噪声模型
- 部分测量
- MBQC
- 更细粒度的 profiling / tracing 能力

## 4. 当前开发原则

当前阶段优先级如下：

1. 先确保运行时抽象、通信原语与构建契约稳定
2. 再围绕这些稳定接口完善 `tech_spec.md`
3. 在抽象层基本冻结后集中实现后端与性能优化
4. 以集成测试和 benchmark 作为后续版本推进的主要验收手段
