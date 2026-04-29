# ZXH-Sim

ZXH-Sim 是一个面向 HPC 场景的量子态矢模拟器，提供 C++ 与 Python 两个前端，并支持 `single / omp / cuda / mpi / mpi_omp / mpi_cuda` 等执行后端。

## 文档

- [`docs/user_guide.md`](./docs/user_guide.md)：环境准备、backend 选择与构建方式
- [`docs/deployment.md`](./docs/deployment.md)：基于 `Slurm` 的 `mpi / mpi_cuda` 正式部署规范
- [`docs/tech_spec.md`](./docs/tech_spec.md)：架构与实现细节
- [`docs/testing.md`](./docs/testing.md)：开发者测试说明
- [`docs/benchmark.md`](./docs/benchmark.md)：性能测试说明

## 目录结构

- `include/`：C++ 公共头文件
- `src/`：C++/CUDA 后端实现
- `zxhsim/`：Python 前端与绑定入口
- `examples/`：用户示例
- `tests/integration/`：集成测试与共享 stage 构建入口
- `benchmarks/`：benchmark 运行入口与 workload 清单
- `docs/`：用户文档、技术规格与 roadmap
- `workspace/`：本地开发工作区，不属于正式文档体系
- `build/stage/<backend>/`：共享 backend stage 目录，供 test 与 benchmark 复用

## 快速开始

先准备本地工具链环境文件：

```bash
# env.sh 用于配置本机相关的编译器和路径变量。
cp env_template.sh env.sh
source ./env.sh
```


### C++

```bash
cmake -S . -B build
cmake --build build
./build/driver_cat
```

### Python

```bash
pip install .
python examples/python/driver_cat.py
```

上述快速开始默认对应 `single` backend。
若默认构建模板运行失败，或是需要构建其它backend，请参考 [`docs/user_guide.md`](./docs/user_guide.md)。
如果需要运行 QASM 示例，还需要安装 `qiskit`：

```bash
pip install qiskit
python examples/python/driver_qasm.py
```

`cmake configure` 成功后，终端会打印当前构建摘要，包括：

- `Backend`
- `Node execution mode`
- `MPI support`
- `OpenMP support`
- `CUDA support`
- `Python frontend`

## 进一步阅读

- 对于库使用者，如果你想切换到 `omp / cuda / mpi / mpi_omp / mpi_cuda` backend，请阅读 [`docs/user_guide.md`](./docs/user_guide.md)。
- 对于库开发者，如果你想一次验证多个 backend 的 build/run smoke，请阅读 [`docs/testing.md`](./docs/testing.md)。
- 对于正式的多卡 / 多节点运行，请阅读 [`docs/deployment.md`](./docs/deployment.md)；当前版本只正式支持 `Slurm`。

此外，ZXH-Sim 还提供 benchmark 模块，用于开发阶段的性能 smoke、结构化结果输出与后续性能实验入口。

- 运行说明见 [`benchmarks/README.md`](./benchmarks/README.md)。
- Benchmark系统设计见 [`docs/benchmark.md`](./docs/benchmark.md)。
