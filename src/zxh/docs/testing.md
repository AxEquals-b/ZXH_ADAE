# ZXH-Sim 测试文档

## 1. 文档定位

本文档用于归档 ZXH-Sim 测试体系中已经确定的设计结论与稳定约定。

它不记录当前阶段正在执行的测试任务、阻塞项或临时 checklist；这类高频变化内容应维护在本地 `workspace/` 中。

## 2. 测试范围

当前测试体系面向功能正确性与最小可运行闭环，不承担性能评测、扩展性分析或大规模 benchmark 的职责。
它也不承担正式的多节点部署验证职责。

测试系统覆盖四层：

1. `build smoke`：不同 backend 组合能够完成配置与编译
2. `runtime smoke`：最小电路能够被加载、执行并采样，不发生崩溃或挂死
3. `correctness smoke`：选定的小规模电路满足预期的测量行为
4. `seed reproducibility smoke`：同一 `seed`、同一环境、同一 backend 下重复采样结果保持一致

## 3. 测试分层

### 3.1. Build Smoke

`build smoke` 用于验证构建系统、backend 选择逻辑以及工具链配置没有被破坏。

其判定标准是：

- `cmake configure` 成功
- configure 摘要中的 `Backend / Node execution mode / MPI support / OpenMP support / CUDA support` 与预期一致
- 目标 backend 成功编译
- 基本可执行入口能够被链接生成
- Python staging 工件能够被隔离安装并用于后续 smoke 运行

### 3.2. Runtime Smoke

`runtime smoke` 用于验证一条最小执行路径可以端到端跑通。

它主要覆盖：

- QASM 文件读取
- 前端到 `ZXH` 的门映射
- `execute()`
- `Sampling()` 或 `measure()`

### 3.3. Correctness Smoke

`correctness smoke` 用于验证系统不是“能跑但结果错误”。

它不试图给出完备的数值正确性证明，而是用少量小电路覆盖关键语义路径，并作为后续开发的回归基线。

### 3.4. Seed Reproducibility Smoke

`seed reproducibility smoke` 用于验证测量模块的最小随机契约没有被破坏。

其判定标准是：

- 对同一个已执行完成的电路对象，重复设置同一个 `seed`
- 在同一 backend、同一运行环境下重复调用 `Sampling(...)`
- 返回的样本序列逐项一致

它不要求跨 backend、跨平台或跨标准库实现一致；这与 `tech_spec.md` 中对测量随机性的约束保持一致。

## 4. Backend 测试矩阵

backend 空间按 `2 x 3` 组织：

| MPI 维度 | 执行维度 | Backend |
| --- | --- | --- |
| `MPI=OFF` | `single` | `single` |
| `MPI=OFF` | `omp` | `omp` |
| `MPI=OFF` | `cuda` | `cuda` |
| `MPI=ON` | `single` | `mpi` |
| `MPI=ON` | `omp` | `mpi_omp` |
| `MPI=ON` | `cuda` | `mpi_cuda` |

其中 `omp` 与 `cuda` 互斥。

当前归档 smoke 测试矩阵包含以下 backend：

| Backend | Build | Run | Correctness | 说明 |
| --- | --- | --- | --- | --- |
| `single` | 必测 | 必测 | 必测 | 参考执行路径 |
| `omp` | 必测 | 必测 | 必测 | 语义上应与 `single` 保持一致 |
| `mpi` | 必测 | 必测 | 必测 | 先从小规模 `nprocs` 开始 |
| `mpi_omp` | 必测 | 必测 | 必测 | MPI 路径叠加 OpenMP kernel 路径 |
| `cuda` | 条件性测试 | 条件性测试 | 条件性测试 | 仅在具备 CUDA 环境时执行 |
| `mpi_cuda` | 条件性测试 | 条件性测试 | 条件性测试 | 仅在同时具备 MPI 与 CUDA 环境时执行 |

这里的“条件性测试”表示：该 backend 属于正式矩阵的一部分，但在本地机器不具备相应环境时允许被显式跳过。

对于 `mpi_cuda`，当前测试系统的默认运行语义进一步约定为：

1. 测试入口只面向单机 correctness；
2. 本地 smoke 固定为单进程单卡；
3. 若未显式设置 `CUDA_VISIBLE_DEVICES`，runner 会默认将其收窄为 `0`；
4. 正式多进程多卡 / 多节点运行不属于 `tests/` 职责范围，而由 `deployment.md` 约束；
5. 若多个 MPI rank 绑定到同一张物理 GPU，`mpi_cuda` 运行时会直接 fail fast。

## 5. Oracle 类型

测试系统当前采用三类 oracle：

1. `delta`：唯一一个 bitstring 的概率应为 `1`
2. `support`：采样结果只允许落在一个已知 bitstring 集合中
3. `distribution`：小电路的采样频率应近似匹配参考分布

三类 oracle 的职责分别是：

- `delta`：捕获最直接、最明显的状态更新错误
- `support`：验证 Bell/GHZ 等结构化叠加态的支撑集是否正确
- `distribution`：覆盖相位相关路径，避免仅凭支撑集检查而漏掉干涉错误

此外，部分归档用例还会附加 `seed reproducibility smoke` 检查，用于覆盖 `set_seed` 到 `Sampling` 的随机数据流是否稳定；它属于附加测试维度，而不是新的 oracle 类型。

## 6. 当前归档用例

当前已归档的种子用例包括：

1. `x_1_delta`：验证最基本的确定性状态更新
2. `h_1_balanced`：验证局部 `H` 的 50/50 采样分布
3. `bell_2_support`：验证纠缠态测量结果只落在预期支撑集
4. `u3_1_balanced`：验证 `U3` 映射与对应 kernel 路径
5. `h_11_inter_worker_delta`：验证 `mpi/mpi_omp` 下跨 worker 交换后的结果仍能回到确定态

其中 `h_11_inter_worker_delta` 的定位不是大规模压力测试，而是当前测试矩阵中用于最小触发跨 worker 路径的回归用例。

当前 `h_1_balanced` 还额外承担一个归档职责：验证同一 `seed` 下的重复采样结果在同一 backend / 同一环境中保持一致。

这些用例的职责不是覆盖全部门语义，而是为后续 backend 演化提供稳定、可重复的最小回归基线。

## 7. 目录结构

正式可跟踪的测试资源位于 `tests/integration/`。

约定如下：

- `tests/integration/manifest.yaml`：声明测试用例、smoke 选择与 oracle 元数据
- `tools/backend_registry.py`：共享 backend 构建/运行注册表
- `tests/integration/cases/`：存放小规模、可维护的 QASM 测试电路
- `tests/integration/manifest.py`：最小 manifest 解析器
- `tests/integration/build_matrix.py`：基于共享 backend 注册表构建 backend 矩阵并准备共享 stage 工件
- `tests/integration/run_suite.py`：统一运行入口，负责超时控制与结构化结果收集
- `tests/integration/oracles.py`：实现 `delta / support / distribution` 判定

在当前阶段，`manifest.yaml`、共享 backend 注册表、种子 QASM 用例、`build_matrix.py`、`run_suite.py` 与 `oracles.py` 构成测试系统的最小可运行骨架。

`build_matrix.py` 默认只执行 `build smoke`。当前实现会先基于当前 shell 环境执行 `cmake configure/build`，确认 backend 二进制和 `driver_cat` 可以生成；随后再执行 `pip install . --target ...` 准备共享 stage 工件。

测试系统遵循与用户文档一致的契约分层：

1. 调用者只负责提供工具链环境；
2. `build_matrix.py` 负责多 backend 编排；
3. backend 列表由共享 backend 注册表维护；
4. 调用者不应通过 `env.sh` 中的 backend 开关驱动 matrix 行为。

当前共享 stage 的标准目录为：

```text
build/stage/<backend>/
```

其中 Python 工件固定放在：

```text
build/stage/<backend>/python
```

`run_suite.py` 会按 `backend` 参数自动从该共享目录导入对应工件，而不是再通过单独的 stage 路径环境变量指定。

`build_matrix.py` 的 backend 列表来自共享 backend 注册表，而工具链与平台相关变量仍由调用者当前环境提供，例如 `MPICXX`、`CUDACXX`、`CUDA_PATH`、`CUDAARCHS`、`CUDAFLAGS`，以及 `cu-bridge` 场景下的 `ZXHSIM_CU_BRIDGE_RUNTIME_ROOT`、`ZXHSIM_CU_BRIDGE_SYSTEM_INCLUDE_DIRS`、`ZXHSIM_CU_BRIDGE_LINK_DIRECTORIES`、`ZXHSIM_CU_BRIDGE_LINK_LIBRARIES`。它不负责猜测本机 `cu-bridge` 或 MPI 安装布局。

当显式传入 `--run-smoke` 时，它会在 backend 构建成功后，基于共享 stage 工件调用 `run_suite.py` 做一轮最小运行回归；这属于对 `run_suite.py` 的编排复用，而不改变两者原本的职责分层。

需要特别说明的是：当前测试系统中的 `mpi` / `mpi_cuda` smoke 与正式 deployment 是两个不同层次的问题。前者只验证本地功能正确性；后者由 [deployment.md](./deployment.md) 约束，且当前版本只正式支持 `Slurm`。

## 8. 与 `driver_qasm.py` 的关系

`examples/python/driver_qasm.py` 目前仍是 QASM 驱动原型。测试系统应围绕它扩展，而不是复制一套独立的前端逻辑。

当前已经抽出的稳定接口包括：

- `zxhsim.qasm.load_qasm(...)`：基于 `qiskit` 读取 OpenQASM 文件
- `zxhsim.qasm.load_circuit(...)`：对原始 `QuantumCircuit` 执行 zxh 前端 transpile，然后加载到 `ZXH`
- `zxhsim.qasm.load_circuit_transpiled(...)`：直接加载已 transpile 到 zxh 原生门集的 `QuantumCircuit`

后续演化原则是：

1. 持续从 `driver_qasm.py` 中抽取可复用的稳定接口
2. 在测试 runner 中复用这些接口
3. 在复用层之上增加结构化输出、超时控制与 oracle 判定

这样可以保证 example 路径与测试路径共享同一套前端行为。
