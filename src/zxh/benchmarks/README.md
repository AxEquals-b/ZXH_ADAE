# ZXH-Sim Benchmark Guide

本目录面向开发阶段的 benchmark 使用者，目标是提供一条能跑通、能看到结构化性能数据的最小闭环。

## 1. 复现目标

当前 benchmark 模块用于：

1. 运行开发阶段的性能 smoke / 小规模性能实验；
2. 生成结构化原始结果与聚合结果；
3. 为后续性能优化保留统一入口。

## 2. 运行准备

benchmark 依赖 `qiskit` 运行，需保证当前 `python` 环境中有可用的 `qiskit` 包：

```bash
pip install qiskit
```

随后按 [docs/user_guide.md](../docs/user_guide.md) 准备 `env.sh` 并在当前 shell 中启用：

```bash
cp env_template.sh env.sh
# edit env.sh according to user_guide.md
source env.sh
```

这里需要强调：

1. `env.sh` 只负责提供工具链与平台相关配置；
2. benchmark 不在 `env.sh` 中选择 backend；
3. backend 只由 suite 决定。

如果准备 `cuda / mpi_cuda` suite，`prepare_suite.py` 会直接复用当前 shell 中的构建环境。若 `CUB` 不在系统默认前缀，请在 `env.sh` 中导出 `CUB_ROOT`，并按需把它加入 `CMAKE_PREFIX_PATH`；benchmark stage 会将这两个变量继续传给 `CMake`。

对本地默认运行路径，还需要明确：

1. `cuda` suite 在未显式设置 `CUDA_VISIBLE_DEVICES` 时，会默认收窄到 `0`；
2. 本地 `mpi_cuda` smoke 固定为单进程单卡最小路径；
3. 若需要多进程多卡或多节点 benchmark，应使用 suite 中声明 `deployment` 的正式路径；
4. 多个 MPI rank 共享同一张物理 GPU 不再属于支持范围。

如果需要正式的多卡 / 多节点部署，请阅读 [docs/deployment.md](../docs/deployment.md)。
当前版本只正式支持基于 `Slurm` 的 deployment 方案。

## 3. 运行流程

benchmark 的标准流程固定为三步：

1. 按 suite 准备共享 stage；
2. 按 suite 运行 benchmark，生成原始结果；
3. 按 suite 聚合结果。

以 `smoke_mpi_cuda` suite 为例，一次完整运行流程如下：

```bash
python benchmarks/prepare_suite.py --suite smoke_mpi_cuda
python benchmarks/runners/run_suite.py --suite smoke_mpi_cuda
python benchmarks/reports/aggregate.py --suite smoke_mpi_cuda
```

其中第 1 步不会调用 integration test 的 matrix 入口，而是只为当前 suite 对应的单个 backend 准备 `build/stage/<backend>/python`。

当前仓库内置的 benchmark smoke suite 为：

| Suite | Backend | 定位 |
| --- | --- | --- |
| `smoke_single` | `single` | 默认 CPU 路径 |
| `smoke_omp` | `omp` | 单节点 OpenMP 路径 |
| `smoke_cuda` | `cuda` | 单节点 CUDA 路径 |
| `smoke_mpi` | `mpi` | 多进程 CPU 路径 |
| `smoke_mpi_omp` | `mpi_omp` | 多进程 + OpenMP 路径 |
| `smoke_mpi_cuda` | `mpi_cuda` | CUDA + MPI 最小本地路径 |

这些 suite 当前都只承担最小 benchmark 闭环验证职责，不承担正式性能分析职责。
其中 `smoke_mpi_cuda` 的默认本地行为是单进程单卡，仅用于验证 benchmark 流程本身没有被破坏。

在 smoke 之外，当前还内置了两组开发阶段的性能观察 suite：

| Suite | Backend | 定位 |
| --- | --- | --- |
| `dev_mpi_cuda` | `mpi_cuda` | 开发阶段性能观察面，覆盖仓库内置 benchmark QASM 中 `M=16..24` 的电路 |
| `dev2_mpi_cuda` | `mpi_cuda` | 开发阶段性能观察面，面向较大规模仓库内置 benchmark QASM 电路 |

其标准入口与 smoke suite 相同：

```bash
python benchmarks/prepare_suite.py --suite dev_mpi_cuda
python benchmarks/runners/run_suite.py --suite dev_mpi_cuda
python benchmarks/reports/aggregate.py --suite dev_mpi_cuda
```

`dev_mpi_cuda` 当前是固定 `backend=mpi_cuda` 的开发期 suite。它的目标不是论文归档，而是在后端开发阶段提供稳定、可复现、可比较的性能观察面。`dev_mpi_cuda` 与 `dev2_mpi_cuda` 的 workload 选择参考 `workspace/qasm_circuits/circuit_lists.txt` 中的大写 `M`（实际使用的 qubit 数）分桶，而不是按文件名中的总线宽 `n` 分桶；但 benchmark 运行所需的 QASM 现已收口到 `benchmarks/workloads/qasm/`，不再依赖 `workspace/` 下的本地数据。每个电路族当前只保留一个原始 QASM 版本，不再把同一电路的 transpiled 版本重复加入 suite。
`dev_mpi_cuda` 通过 suite 内的 `deployment` 字段声明正式运行几何；当该字段存在时，runner 会自动切换到 `Slurm` 的 `srun` 路径。
如果需要生成正式的多 GPU / 多节点性能数据，应按 [docs/deployment.md](../docs/deployment.md) 在 `Slurm` 环境中执行 `dev_mpi_cuda`，而不应把本地单进程单卡 smoke 结果视为正式 benchmark 结果。

`dev_mpi_cuda` 面向 `M=16..24` 区间；`dev2_mpi_cuda` 面向更大规模区间。规划层仍按 `M=25..32` 理解该桶位，当前具体电路清单以 suite 与 manifest 为准。

## 4. 配置

### 4.1 配置入口

benchmark 仓库内存在两层静态配置，但标准运行只需要显式指定 suite：

1. `benchmarks/manifest.yaml`
2. `benchmarks/suites/*.yaml`

其中：

`manifest.yaml` 是仓库内部目录表，负责声明全局默认值和 workload 目录。标准复现流程通常不需要修改它：

- `defaults.output_root`
- `defaults.shots`
- `defaults.warmup`
- `defaults.repeats`
- `defaults.timeout_s`
- `defaults.opt_level`
- `defaults.stop_on_error`
- `workloads[]`

`suites/*.yaml` 是 benchmark 的公开运行入口，负责声明某一次标准实验要跑什么。规范要求一个 suite 只对应一个 backend：

- `suite_id`
- `backend`
- `deployment`（可选，仅正式 `Slurm` 部署时使用）
- `workloads`
- `metrics`
- `shots`
- `warmup`
- `repeats`
- `opt_level`
- `timeout_s`

以 `suites/smoke_mpi_cuda.yaml` 为例，一个典型的配置如下：

```yaml
backend: mpi_cuda
workloads: [x_1_delta]
shots: 256
warmup: 0
repeats: 1
opt_level: 1
timeout_s: 20
```

而一个正式 `Slurm` benchmark suite 则可进一步声明：

```yaml
backend: mpi_cuda
deployment:
  nnodes: 2
  ntasks_per_node: 4
```

此时 runner 会自动推导：

1. `nprocs = nnodes * ntasks_per_node`
2. `mpi_cuda` 正式部署固定使用 `--gpus-per-task=1`
3. benchmark worker 由 `srun` 启动

这里的职责划分是：

1. `manifest.yaml` 定义 benchmark 的全局默认值和 workload 目录；
2. `suite` 定义“本次 benchmark 跑哪个 backend、哪些 workload、采用哪些参数”；
3. `suite.deployment` 只描述正式 `Slurm` 运行所需的最小几何信息，而不描述站点私有参数；
4. backend 的构建与本地默认运行契约由仓库内部共享注册表自动提供，不再要求调用者在 benchmark 层重复指定；
5. benchmark 的三个标准入口都只接受 `--suite`，不再提供额外覆盖。

因此，benchmark 的 backend 选择是正交的：

1. 在 suite 中选择一次；
2. `prepare / run / aggregate` 三步都由 suite 派生；
3. 不再需要在命令行、环境变量、manifest 或 aggregate 输入路径中重复指定。

### 4.2 标准入口参数

当前 benchmark 的三个标准入口都只接受一个公开参数：

- `--suite`

分别对应：

- `python benchmarks/prepare_suite.py --suite <suite>`
- `python benchmarks/runners/run_suite.py --suite <suite>`
- `python benchmarks/reports/aggregate.py --suite <suite>`

## 5. 输出

benchmark 的标准输出分为两层：

1. `raw results`：单次任务的原始结构化结果；
2. `aggregate`：聚合后的统计表。

默认输出位置由 `manifest.yaml` 中的 `defaults.output_root` 决定。当前默认值为：

```text
build/benchmarks/<suite_id>/
```

当前输出默认视为开发期临时结果，保存在 `build/` 下即可，不要求归档目录。

## 6. 环境记录

benchmark 结果仍应伴随环境记录。当前输出至少包含：

- Git commit；
- backend 类型；
- 编译器与工具链信息；
- MPI / CUDA 相关环境；
- 关键运行参数。

这足以支撑开发阶段的结果回看与简单对比。

## 7. 当前边界

当前 MVP 已实现：

1. 静态 QASM workload；
2. 单 backend suite runner；
3. `raw.json` / `env.json` / `aggregate.json` / `aggregate.csv`；
4. benchmark 环境记录；
5. 基于共享目录 `build/stage/<backend>/python` 的标准 backend 工件导入。

当前 MVP 暂未实现：

1. workload generator；
2. 多 suite 编排；
3. 图表脚本；
4. benchmark 结果归档流程。
