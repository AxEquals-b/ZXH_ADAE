# 集成测试骨架

该目录用于存放 ZXH-Sim 的可跟踪集成测试资源。

当前 MVP 包含：

- `manifest.yaml`：声明测试用例、smoke 选择与 oracle 元数据
- `tools/backend_registry.py`：共享 backend 构建/运行注册表
- `cases/`：用于 smoke test 与 correctness smoke test 的手写小型 OpenQASM 电路
- `manifest.py`：无额外 YAML 依赖的最小 manifest 解析器
- `oracles.py`：实现 `delta / support / distribution` 三类判定
- `run_suite.py`：统一编排单 case 执行、超时控制与 oracle 判定
- `build_matrix.py`：基于共享 backend 注册表构建 backend 矩阵并产出共享 stage 工件

本目录只服务于功能正确性验证，不承担性能评测职责。

当前归档用例覆盖的最小语义路径为：

- `x_1_delta`：确定性单比特翻转
- `h_1_balanced`：局部 `H` 的分布正确性，以及最小 `seed` 可复现性检查
- `bell_2_support`：小规模纠缠态的支撑集正确性
- `u3_1_balanced`：`U3` 映射与 kernel 路径
- `h_11_inter_worker_delta`：`MPI/mpi_omp` 下最小跨 worker 交换回归路径

最小使用流程：

1. 构建某个 backend 并生成共享 stage 工件
   `python tests/integration/build_matrix.py --backend single`
2. 基于共享 stage 运行 smoke/correctness case
   `python tests/integration/run_suite.py --backend single`

如果希望将两步串成一次 post-build 回归，可以使用：

`python tests/integration/build_matrix.py --backend omp --run-smoke --smoke-case-id x_1_delta`

如果希望连同条件性 backend 一起执行，可以使用：

`python tests/integration/build_matrix.py --include-conditional --run-smoke`

其中 `mpi_cuda` 的本地 smoke 语义固定为单进程单卡，仅验证最小 CUDA + MPI 路径；正式多进程多卡运行不属于 `tests/` 的职责范围，应按 `docs/deployment.md` 执行。

当前阶段，`build_matrix.py` 与 `run_suite.py` 仍是两个显式入口，分别对应：

- `build smoke`
- `runtime smoke + correctness smoke`
