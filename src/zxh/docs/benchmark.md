# ZXH-Sim Benchmark Design

## 1. 文档定位

`benchmarks/` 用于承载 ZXH-Sim 的标准化性能复现流程。

其目标有两类：

1. 作为后续性能优化的基线与对比指标来源；
2. 提供可复现的运行流程、环境记录、原始数据与图表产物。

本文档描述 benchmark 模块的最终设计，可能与现阶段实现有所出入。

## 2. 与 `examples/`、`tests/` 的边界

- `examples/`：面向库调用者，展示如何使用 ZXH-Sim；其重点是调用方式与最小可运行示例，不承担标准化实验职责。
- `tests/`：面向开发者，承担 build smoke、runtime smoke、correctness smoke 等回归验证；其重点是 `pass / fail`。
- `benchmarks/`：面向验证者，承担标准化性能实验、可复现环境记录、原始结果归档、统计汇总与图表生成；其重点是“可测量、可复现、可比较”。

## 3. 总体流程

benchmark 模块遵循如下数据流：

```text
config -> runner -> task -> metrics -> result -> aggregate -> plots
```

其中：

1. `config`：描述要跑什么、如何跑、如何汇总、如何绘图；
2. `runner`：将配置展开为可执行任务并驱动运行；
3. `task`：最小执行单元；
4. `metrics`：从单次任务中采集的原始测量值；
5. `result`：单次任务的结构化结果记录；
6. `aggregate`：按 workload / backend / 参数维度聚合原始结果；
7. `plots`：由聚合结果生成图表与表格。

应当强调：`plots` 不应直接依赖临时 stdout，而应只消费结构化 `aggregate` 数据。

## 4. 核心抽象

### 4.1. `config`

`config` 是 benchmark 的静态输入层，用于声明：

- suite 列表；
- workload family；
- 参数范围；
- `shots / warmup / repeats`；
- 需要采集的 metric；
- 聚合方式；
- 图表定义。

`config` 只描述实验，不执行实验。

在当前规范中，`suite` 是 benchmark 的唯一外部入口。标准 benchmark 流程中的 `prepare / run / aggregate` 都应仅由 suite 驱动，而不再暴露额外的 backend 覆盖或输出路径覆盖。backend 的构建与本地默认运行契约应由仓库内部共享注册表提供；若需要正式 `Slurm` 部署，则由 suite 内的 `deployment` 字段声明最小运行几何，而不是由 benchmark 用户在命令行多处重复指定。

### 4.2. `runner`

`runner` 是 benchmark 的编排层，用于：

- 解析 `config`；
- 展开 workload family；
- 物化执行计划；
- 调用 ZXH-Sim 前端与后端完成实际运行；
- 收集环境信息与日志；
- 写出结构化结果。

`runner` 不应重新定义 workload 语义或结果格式；它只负责调度与落盘。

### 4.3. `task`

`task` 是 benchmark 的最小执行单元。一个 `task` 至少应唯一对应：

- 一个已物化的 workload instance；
- 一个 backend；
- 一个 repeat 编号；
- 一组运行参数，如 `shots / warmup / nprocs / threads`。

若 suite 声明了正式部署几何，则 `task` 还隐式绑定一组 `deployment` 参数，例如 `nnodes / ntasks_per_node`；由 runner 进一步推导 `nprocs` 并拼接 `srun`。

若同一 suite 中存在 warmup，则 warmup 运行应以显式任务记录，但默认不进入最终统计。

### 4.4. `metrics`

`metrics` 是单次 `task` 的原始测量值。标准 metric 集至少应包括：

- `compile_time_ms`
- `execute_time_ms`
- `sample_time_ms`
- `total_time_ms`
- `status`

后续可扩展：

- `peak_host_mem_bytes`
- `peak_worker_mem_bytes`
- `build_id`
- `binary_size_bytes`

metric 的定义应尽量稳定。若某一项无法在部分 backend 上采集，应显式记为缺失，而不是临时改名。

### 4.5. `result`

`result` 是单次 `task` 的结构化落盘记录。它应包含：

- task 身份信息；
- metric 值；
- 环境信息引用；
- 日志位置；
- 失败状态与错误消息。

`result` 是 benchmark 的事实层，后续统计与画图都应从这里导出。

### 4.6. `aggregate`

`aggregate` 用于跨重复运行和参数维度做统计汇总。典型聚合维度包括：

- `family_id`
- `instance_id`
- `backend`
- 参数列，如 `nqubits`

典型统计量包括：

- `mean`
- `std`
- `median`
- `min / max`
- `count`

若后续需要 speedup 或版本间回归比较，也应建立在 `aggregate` 层，而不是直接比较单次结果。

### 4.7. `plots`

`plots` 面向人阅读。它们由 `aggregate` 自动生成，至少支持：

- scaling curve
- backend comparison
- 重复运行波动图
- 论文表格

图表本身不是 benchmark 的事实来源；原始结果与聚合结果才是事实来源。

## 5. Workload 数据模型

benchmark 不应只建模为一组彼此独立的 `case_id`。对于 `QFT`、`QAOA` 等需要按参数区间画图的实验，更合适的数据模型是：

```text
family -> instance -> task -> result
```

### 5.1. `family`

`family` 表示一类逻辑相关的 workload，例如：

- `qft_scaling`
- `ghz_scaling`
- `qaoa_small`

`family` 可以来自：

- 静态 QASM 列表；
- 参数化生成器；
- 混合型数据集。

### 5.2. `instance`

`instance` 表示一个具体 workload 实例，例如：

- `qft_n12`
- `qft_n14`
- `qaoa_p2_n10`

它应带有稳定的参数列，例如：

- `nqubits`
- `depth`
- `p`
- `family_id`

### 5.3. `task`

`task` 表示一个具体执行计划，例如：

- `instance=qft_n12`
- `backend=mpi_cuda`
- `repeat_id=3`
- `shots=1024`

规范上，一个 suite 对应一个 backend；跨 backend 对比应当通过多次独立运行后在 `aggregate` 层完成，而不是把多个 backend 混在同一次 suite 运行中。
若 suite 需要正式多节点运行，则只声明最小 `deployment` 信息，如 `nnodes / ntasks_per_node`；一 rank 一 GPU 属于 deployment 规范本身，不应在 suite 中重复声明。

### 5.4. `materialization`

若 `family` 来自生成器而不是静态 QASM 文件，则 benchmark 运行时应能输出“冻结后的 workload 工件”，例如：

- 物化后的 QASM；
- 或生成器输入参数与规范化后的电路表示。

这是论文 AD 可复现性的要求之一。否则生成器逻辑变更后，同名 instance 可能不再对应同一个电路。

## 6. 环境与可复现性

benchmark 的可复现性不只依赖 workload，还依赖运行环境。因此，benchmark 应显式采集环境信息，包括：

- Git commit / dirty 状态；
- backend 类型；
- 编译器与工具链；
- MPI launcher 与 `nprocs`；
- GPU / CUDA / `cu-bridge` 信息；
- CPU / OMP 线程配置；
- 关键环境变量。

环境信息应与 `result` 解耦，作为独立对象记录，并由 `env_id` 关联到结果。

## 7. 目录划分

benchmark 模块的最终目录设计如下：

```text
benchmarks/
  README.md
  manifest.yaml

  suites/
    smoke_single.yaml
    smoke_mpi_cuda.yaml
    regression.yaml
    paper_ad.yaml

  workloads/
    README.md
    qasm/
    lists/
    generators/

  runners/
    run_suite.py
    run_task.py
    env_capture.py
    backend_matrix.py

  metrics/
    README.md
    timing.py
    memory.py
    env.py

  schemas/
    result.schema.json
    aggregate.schema.json
    env.schema.json

  reports/
    aggregate.py
    plot.py
    templates/

  baselines/
    README.md
    v0.4.0/

  outputs/
    .gitkeep
```

各子模块职责如下：

- `manifest.yaml`：benchmark 的全局默认值与 workload 目录；
- `suites/`：不同实验套件定义；
- `workloads/`：workload family 的来源定义；
- `runners/`：执行与调度；
- `metrics/`：标准 metric 采集逻辑；
- `schemas/`：结果格式约束；
- `reports/`：统计与绘图；
- `baselines/`：已归档基线；
- `outputs/`：当前运行生成的临时产物。

## 8. Suite 分层

benchmark 至少应分为三类 suite：

### 8.1. `smoke`

目标：验证 benchmark runner 本身能跑通。

特点：

- 小数据集；
- 少量 repeats；
- 不追求稳定结论；
- 可纳入日常回归。

### 8.2. `regression`

目标：服务于开发期性能回归观察。

特点：

- 覆盖主要 workload family；
- 输出可比较的 `aggregate` 数据；
- 适合版本间或分支间对比。

### 8.3. `paper_ad`

目标：服务于论文 AD 的标准化复现实验。

特点：

- 固定 suite 与参数范围；
- 固定输出 schema；
- 固定图表模板；
- 强制记录环境信息；
- 强制物化 generator 型 workload。

## 9. 输入输出契约

### 9.1. 输入

 benchmark 的输入应至少覆盖：

- suite 选择；
- workload family 或 case list；
- 参数范围；
- `shots / warmup / repeats`；
- 输出目录；
- 运行环境约束。

其中 backend 选择与输出目录选择应被 suite 和 manifest 吸收，而不是作为独立命令行输入暴露给复现者。backend 本身的构建与本地默认运行契约由仓库内部的共享 backend 注册表维护；正式 `Slurm` 运行几何则由 suite 的 `deployment` 字段吸收。

### 9.2. 原始输出

benchmark 的原始输出至少应包括：

- 原始 `result` 文件；
- 环境信息文件；
- 物化后的 workload 工件；
- stdout / stderr 日志。

### 9.3. 聚合输出

benchmark 的聚合输出至少应包括：

- `aggregate` 表；
- backend 对比表；
- scaling 表；
- 供绘图脚本消费的稳定中间文件。

### 9.4. 最终输出

面向验证者的最终产物至少包括：

- 原始性能数据；
- 聚合结果；
- 图表；
- 运行说明；
- 环境说明。

## 10. 设计约束

benchmark 模块应满足以下约束：

1. 不复制 `examples/` 或 `tests/` 中已有的 QASM 驱动逻辑；
2. 不依赖人工解析 stdout 作为主要数据源；
3. 不把图表脚本写成一次性脚本；
4. 不把当前机器特有路径硬编码到 suite 配置中；
5. 不将性能结论写死在仓库中，仓库中只归档流程、schema 与必要基线。
6. 一个 suite 只对应一个 backend；多 backend 对比必须拆成多次独立运行。

## 11. 与版本推进的关系

- `v0.4.0`：完成 benchmark 的标准运行闭环、`Slurm` 正式部署路径与 `mpi_cuda` 多节点性能数据获取能力；
- `v0.5.0`：使用 benchmark 作为 `CUDA + MPI` 性能优化的对比基线；
- 更后续版本可继续扩展 workload family、图表模板与环境采集粒度，但不应推翻本模块的总体流程与分层。
