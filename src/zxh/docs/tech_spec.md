# ZXH-Sim Technical Specifications

## 1. 项目概览

`ZXH-Sim` 是一个高性能量子模拟器库，使用与 Clifford+T 类似的优化策略，能够高效处理 `CX/X` 类门电路，消除 `Rz/CRz` 门的通信开销，将大部分复杂性 offload 到少量 `H` 门中。`ZXH-Sim` 面向的前端包括：

- C++
- Python

面向的后端包括：

- 可选单节点/多节点（MPI 支持）
- 每个节点可选单线程/多线程加速（OpenMP 支持）/GPU 加速（CUDA 支持）

## 2. 项目构建

本节只描述理解代码组织所必需的构建层抽象。具体环境配置、平台差异与命令示例统一放在 [user_guide.md](./user_guide.md) 中维护。

### 2.1. Public API 与 Internal API

- 本项目当前承诺稳定的 `public API` 仅包括面向调用者的入口头文件：`zxh.h`、`runtime.h` 与 `types.h`。其中 `zxh.h` 对应模拟器对象与执行入口，`runtime.h` 对应运行时生命周期接口，`types.h` 对应公共基础类型。
- `types.h` 中定义的 `float_t`、`val_t`、`bitvec_t` 与 `res_t` 属于对外契约的一部分；它们服务于前端调用、结果表示与基础数据交换，不承载后端执行语义。
- `defs.h` 及其余模块头文件即使当前位于 `include/zxhsim/` 下，也应视为 `internal API`：它们主要服务于仓库内部模块协作，允许在后续版本中继续调整。例如 `defs.h`、`sv.h`、`comm.h`、`measure.h` 都属于此类实现层接口。
- 示例程序与 Python 绑定应只直接依赖这些 `public API` 头文件，而不直接包含 `internal API` 头文件。

### 2.2. 构建系统与目录组织

- 构建系统：CMake（`CMakeLists.txt`），要求 CMake >= 3.18，C++17。
- Python 构建：`pyproject.toml` 使用 scikit-build-core + pybind11，驱动同一套 CMake 目标图生成扩展模块；在该路径下 `USE_PYTHON` 默认自动为 `ON`。
- 关键目录：
  - `include/`：C++ 头文件（对外 API 与内部工具）。
  - `src/core/`：后端无关核心实现（如 `bitvec/bitmat/addr/selector/utils/zxh`）。
  - `src/runtime/`：运行时实现，承载 `init/finalize/active/rank/nprocs/log/abort` 等进程级接口。
  - `src/comm/`：通信原语实现，提供 `request_t`、`worker_slot_t` 与 `host` collectives 等底层 build block，屏蔽 `general / mpi / mpi_cuda` 差异。
  - `src/sv/`：状态向量实现，以及基于 `segment` / `neighbor` 的中层调度逻辑。
  - `src/kernel/`：门核函数实现（`general / omp / cuda` 选择）。
  - `src/mem/`：内存管理实现（`host / cuda` 选择）。
  - `src/measure/`：测量公共入口与后端实现。
  - `src/pybind/`：Python 绑定实现。
  - `examples/`：示例程序。
  - `zxhsim/`：Python 包装层（`__init__.py`）。

### 2.3. 目标与产物

- `zxhsim_core`：OBJECT library，聚合 `src/core/*.cpp` 与按构建开关选择的 `runtime/comm/sv/kernel/mem/measure` 实现文件。
- `zxhsim`：静态库 `libzxhsim.a`。
- `_core`：Python 扩展模块（启用 `USE_PYTHON` 时生成）。
- `driver_xxx`：示例可执行文件（链接 `zxhsim`）。

### 2.4. 构建开关与作用

- `ZXHSIM_BACKEND`：唯一正式 backend 选择入口。当前合法取值为 `single / omp / cuda / mpi / mpi_omp / mpi_cuda`。
- 由 `ZXHSIM_BACKEND` 派生出的 `MPI support / OpenMP support / CUDA support` 只是构建摘要中的能力字段，而不是新的 backend 入口。
- 后端与实现路径的对应关系为：
  - `single`：单节点单线程 CPU 路径；选择 CPU `runtime/comm/sv/kernel/mem/measure` 实现。
  - `omp`：单节点 OpenMP CPU 路径；链接 `OpenMP::OpenMP_CXX`，并选择 `kernel_omp.cpp`。
  - `cuda`：单节点 CUDA 路径；启用 CUDA 语言，并选择 CUDA `kernel/mem/measure` 实现。
  - `mpi`：多进程 CPU 路径；解析 `mpicxx` wrapper、链接 `MPI::MPI_CXX`，并选择 MPI `runtime/comm/sv/measure` 实现。
  - `mpi_omp`：多进程 + OpenMP CPU 路径；在 `mpi` 基础上进一步选择 OpenMP `kernel` 实现。
  - `mpi_cuda`：多进程 CUDA 路径；同时选择 MPI `runtime/comm/sv/measure` 与 CUDA `kernel/mem/measure` 实现。
- 单节点执行方式只可能是 `single / omp / cuda` 三者之一；其中 `omp` 与 `cuda` 分别对应 CPU 多线程和 GPU 执行路径。
- `USE_PYTHON`：启用 Python 前端；生成 `_core` 并编译 `src/pybind/bindings.cpp`。

### 2.5. 前端入口与契约

- C++ 前端与 Python 前端共享同一套后端选择契约；差别只在于谁触发 CMake 以及是否生成 `_core`。
- C++ 路径直接生成静态库与示例可执行文件；Python 路径通过 scikit-build-core 触发相同的 CMake 目标图，并额外生成 `_core`。
- 构建命令、环境变量示例、平台相关说明与 `cu-bridge` 特例均不在本规范中展开，统一以 [user_guide.md](./user_guide.md) 为准。

## 3. 算法原理

本节描述 ZXH-Sim 算法的数学原理。

### 3.1. 地址空间

对于 $N$ 个 qubit，系统的状态向量长度为 $2^N$。我们可以将每个向量分量与 **一个地址** 一一对应，该地址可由长度 $N$ 的 bitstring 表示：
$$
x = (x_0, x_1, \dots, x_{N-1})^T \in \{0,1\}^N
$$
因此，整个状态向量天然拥有一个 **地址空间**，每个元素对应一个二进制序号。

---

### 3.2. `X` 类门与地址空间映射

在固定的 $N$ 位地址空间 $\mathbb{F}_2^N$ 上，`X` 类门（仅包含 $X$ 与 $CX$）只重排地址，因此可视为地址空间上的一个置换。

- **单比特 $X_i$ 门**
$$
x \mapsto x \oplus e_i
$$
- **受控非门 $CX_{i\to j}$**
$$
x[j] \mapsto x[j] \oplus x[i],\quad x[k\neq j]\ \text{不变}
$$

不难看出，任意由 $X/CX$ 构成的可逆子电路都可写为仿射变换：
$$
x \mapsto A x \oplus b,\quad A\in GL(N,\mathbb{F}_2),\ b\in \mathbb{F}_2^N
$$

其中 $A$ 对应线性部分、$b$ 对应平移部分。该表示正是有限域上的仿射一般线性群：
$$
AGL(N,\mathbb{F}_2)=\mathbb{F}_2^N \rtimes GL(N,\mathbb{F}_2)
$$

我们将变换的原空间和象空间分别称为实地址空间与虚地址空间，其中的元素分别记为 $x_r$ 与 $x_v$。即：

$$
\begin{aligned}
x_r, x_v, b &\in \mathbb{F}_2^N,\quad A \in GL(N,\mathbb{F}_2) \\
x_v &= A x_r \oplus b
\end{aligned}
$$

初始映射：
$$
A \leftarrow I_N,\quad b \leftarrow 0^N
$$

由于 $A$ 可逆，实地址空间与虚地址空间保持一一对应。在虚地址空间上执行 `X` 类门时，算法无需修改或访问实地址空间中的元素，仅通过更新 $(A,b)$ 即可维护映射关系，对虚地址空间进行重排。X(i)/CX(i, j) 门执行策略：
$$
X_i:\quad b \leftarrow b \oplus e_i
$$
$$
\begin{aligned}
CX_{i\to j}:\quad
A_{j,:} &\leftarrow A_{j,:} \oplus A_{i,:} \\
b_j &\leftarrow b_j \oplus b_i
\end{aligned}
$$

上述内容仅作为逻辑抽象参考，实际算法实现需要考虑实地址空间与虚地址空间不等长的情况，详见[第4.4节：地址映射](#44-地址映射)。

---

### 3.3. `H` 门与 `U3` 门的处理

在虚地址空间中，作用于第 $k$ 个 qubit 的 `H` 门对状态向量 $sv$ 的操作可以直接用地址表示：

- 对于每个地址 $x_i$：
$$
sv[x_i] \gets
\begin{cases}
\frac{1}{\sqrt{2}} \left( sv[x_i] + sv[x_i \oplus e_k] \right), & x_i[k] = 0 \\
\frac{1}{\sqrt{2}} \left( sv[x_i] - sv[x_i \oplus e_k] \right), & x_i[k] = 1
\end{cases}
$$

类似地，U3 门作用在第 $k$ 个 qubit 上，也只影响地址 $x_i$ 与 $x_i \oplus e_k$ 对应的振幅，但加上参数化旋转因子。

---

#### 3.3.1. neighbor 的定义与信息交换

根据上述公式，我们可以看到每个地址 $x_i$ 仅与一个特定地址 $x_j = x_i \oplus e_k$ 发生振幅混合。我们称这两个地址互为 **neighbor**。
- neighbor 的特点：两者仅在第 $k$ 位不同，其余位相同。
- 在虚地址空间中，`H`/`U3` 门相当于在每对 neighbor 上进行信息交换。

为避免后续实现中的符号歧义，我们进一步引入有序定义：

- **even neighbor**：满足虚地址空间中第 $k$ 位为 0 的地址
$$
x_{\text{even}}[k]=0 \iff \langle x_{\text{even}}, e_k\rangle=0
$$
- **odd neighbor**：满足虚地址空间中第 $k$ 位为 1 的地址
$$
x_{\text{odd}}[k]=1 \iff \langle x_{\text{odd}}, e_k\rangle=1
$$
- 二者关系：
$$
x_{\text{odd}} \oplus x_{\text{even}} = e_k
$$

因此，每个 neighbor pair 都可唯一写成 $(x_{\text{even}}, x_{\text{odd}})$。在实现层通常只遍历二者之一，以避免同一对地址被重复处理两次。

---

#### 3.3.2. 实地址空间中的neighbor

考虑虚地址空间 $x$ 与实地址空间 $x'$ 的映射：
$$
x = A x' \oplus b
$$

对于一对虚地址 neighbor $x_i, x_j$：
$$
x_i = A x_i' \oplus b, \quad x_j = A x_j' \oplus b
$$

由 neighbor 定义：
$$
x_i \oplus x_j = e_k \implies A (x_i' \oplus x_j') = e_k \implies x_i' \oplus x_j' = A^{-1} e_k
$$

这说明，对于第 $k$ 个 qubit 的 `H`/`U3` 门：

- 虚地址空间中 neighbor 相差 $e_k$
- 实地址空间中 neighbor 相差 $A^{-1} e_k$

记
$$
\delta \equiv A^{-1}e_k
$$
则实地址空间中的 neighbor 可统一写为 $x_r \oplus \delta$。

进一步考虑 even/odd 判定。对任一实地址 $x_r$，其虚地址在第 $k$ 位的值可写为：
$$
p_k(x_r) \equiv \langle x_v, e_k\rangle
= \langle A x_r \oplus b, e_k\rangle
$$
由 $\mathbb{F}_2$ 线性性可得：
$$
p_k(x_r)
= \langle A x_r, e_k\rangle\oplus \langle b,e_k\rangle
= \langle x_r, A^\top e_k\rangle\oplus \langle b,e_k\rangle
$$
定义
$$
\alpha_k \equiv A^\top e_k,\quad \beta_k \equiv \langle b,e_k\rangle
$$
则
$$
p_k(x_r)=\langle x_r, \alpha_k\rangle \oplus \beta_k
$$
因此：

- 若 $p_k(x_r)=0$，则 $x_r$ 对应虚地址 even；
- 若 $p_k(x_r)=1$，则 $x_r$ 对应虚地址 odd。

并且，满足 $p_k(x_r)=0/1$ 的实地址原象分别构成两个仿射超平面：
$$
\mathcal{H}_{\text{even}}=\{x_r\mid \langle x_r,\alpha_k\rangle=\beta_k\}
$$
$$
\mathcal{H}_{\text{odd}}=\{x_r\mid \langle x_r,\alpha_k\rangle=\beta_k\oplus 1\}
$$

据此定义奇偶判定子（selector）：
$$
S_k:\ x_r\mapsto \langle x_r,\alpha_k\rangle\oplus \beta_k
$$
其返回值为 0 表示 even，返回值为 1 表示 odd。

**结论（实现所需）**：给定实地址 $x_i$ 与地址变换 $(A,b)$，
1. neighbor 可由
$$
x_{i,\text{neighbor}} = x_i \oplus \delta
$$
直接计算；
2. $x_i$ 是否为 even 可由
$$
S_k(x_i)=0
$$
判定（等价于 $\langle x_i, A^\top e_k\rangle=\langle b,e_k\rangle$）。

---

### 3.4. `Z` 类门的处理

`Z` 类门（包含 $Rz(q,\theta)$ 和 $CRz(cq,q,\theta)$）通过 **遍历实地址空间地址索引 $i$** 实现，而操作仍在虚地址空间判定上完成。

标准定义采用：
$$
Rz(\theta)=\mathrm{diag}(e^{-i\theta/2},\,e^{i\theta/2})
$$
$$
CRz(\theta)=\mathrm{diag}(1,\,1,\,e^{-i\theta/2},\,e^{i\theta/2})
$$

在[第3.3.2节：实地址空间中的neighbor](#332-实地址空间中的neighbor)中我们已定义判定子 $S_k$。
对任意实地址索引 $i$，$S_q(i), S_{cq}(i)\in\{0,1\}$ 分别表示虚地址在目标位 $q$、控制位 $cq$ 上的比特值。

据此，`Z` 类门可统一写为：

1. 单比特 $Rz(q,\theta)$（一个 selector）
$$
sv[i]\gets sv[i]\cdot e^{i\theta\,(S_q(i)-\tfrac{1}{2})}
$$

2. 受控旋转 $CRz(cq,q,\theta)$（两个 selector）

$$
sv[i]\gets sv[i]\cdot e^{i\theta\,S_{cq}(i)(S_q(i)-\tfrac{1}{2})}
$$

**优化执行**：

- 多个 `Z` 类门可合并，在一次遍历所有 $i$ 时累计总相位，减少遍历次数；
- 无需通信，所有操作在本地地址空间完成，通过虚实映射直接计算振幅。

该设计保证了 **`X` 类门映射更新** 与 **`Z` 类门振幅更新** 在算法中协调执行，实现高效的虚拟-实际地址管理。

### 3.5. 总结

本章节中，我们介绍了量子模拟中各类门在虚/实地址空间上的处理方法：

1. **`Z` 类门**（$Rz$ 与 $CRz$）
   - 作用在虚地址空间上
   - 遍历实地址空间，计算每个虚地址象并更新振幅
   - 多个 `Z` 类门可以合并执行，无需通信

2. **`X` 类门**（$X$ 与 $CX$）
   - 对应虚地址空间上的仿射变换：
     $$
     x_v \mapsto A x_r \oplus b
     $$
   - 通过维护 $(A,b)$ 即可更新虚实地址映射
   - 无需计算或通信，仅更新映射矩阵和向量

3. **`H` 门/`U3` 门**
   - 对每个虚地址 neighbor 进行信息交换：
     $$
     sv[x_i] \gets \frac{1}{\sqrt{2}} ( sv[x_i] \pm sv[x_i \oplus e_k] )
     $$
   - 在实地址空间中，通过计算 $\delta = A^{-1} e_k$ 定位 neighbor
   - 遍历实地址空间交换振幅，带来计算开销

综上，`Z` 类门、`X` 类门和 `H`/`U3` 门共同构成了一个 **完备量子门集**。
- `Z` 类门：无通信，可合并执行
- `X` 类门：无计算与通信，仅更新映射
- `H` 门/`U3` 门：需要遍历实地址空间，产生计算开销

这种设计充分利用虚/实地址空间映射，实现了高效的量子门模拟。

## 4. 数据结构定义

本节描述顶层 API 以及下层模块的数据结构和接口定义。下层模块包含基本类型、地址与地址映射、`sv` 向量以及门电路。本节只负责给出模块级接口抽象与功能描述，不涉及 backend 实现细节。对调用者稳定的接口以 `public API` 语义描述；对执行模型所必需、但仅供仓库内部模块协作的接口，会显式标注为 `internal API`。本文档不讨论全局相位问题，但实现细节应将其纳入考虑。

### 4.1. 基本类型定义

本小节统一定义规范中复用的基础类型。实现可替换底层容器，但应保持语义一致。

```cpp
using size_t = std::size_t;

// 实数参数类型（旋转角、概率等）
using float_t = double;

// 振幅类型（单个状态向量元素）
using val_t = std::complex<float_t>;

// bitstring 抽象类型（具体容器由实现决定）
class bitvec_t
{
  public:
    // 获取位长
    size_t length() const;
    // 访问和修改bit
    bool get_bit(size_t i) const;
    void set_bit(size_t i, bool value);
    // 复制和比较
    bitvec_t copy() const;
    bool equal(const bitvec_t &other) const;
    // F2 异或
    bitvec_t operator^(const bitvec_t &rhs) const;
    // F2 内积
    bool dot(const bitvec_t &rhs) const;
    // 位切片：低位/高位子向量
    bitvec_t lower_bits(size_t n) const;
    bitvec_t higher_bits(size_t n) const;
};

// 测量结果类型保持为纯bitstring，不带地址算术
typedef bitvec_t res_t;
```

### 4.2. 顶层 API

顶层 API 由运行时接口与 `ZXH` 类共同提供。运行时接口定义如下：

```cpp
void init(int *argc, char ***argv);
void finalize();
bool active();
size_t rank();
size_t nprocs();
void log(const char *msg);
[[noreturn]] void abort(const char *msg);
```

其中 `init/finalize` 用于建立/释放进程级运行时环境；`active()` 用于判断该运行时当前是否处于有效期内；`rank/nprocs` 用于查询当前运行时视角下的全局编号与进程数；`log/abort` 分别对应运行时日志与统一失败退出接口。

`ZXH` 类提供以下接口：

```cpp
class ZXH
{
  public:
    // 构造函数，指定逻辑 qubit 数量（即地址空间位长），但不申请实际内存
    explicit ZXH(size_t N);

    // 设置测量随机种子。该配置在对象生命周期内持续生效，
    // 直到再次调用 set_seed 修改之
    void set_seed(uint64_t seed);

    // 清空已记录的门序列
    void clear_gates();

    // 向电路中添加门。仅记录门列表，不作优化/计算
    void Rz(size_t q, float_t theta);
    void CRz(size_t cq, size_t q, float_t theta);
    void Z(size_t q);
    void X(size_t q);
    void CX(size_t cq, size_t q);
    void H(size_t q);
    void U3(size_t q, float_t theta, float_t lambda, float_t phi);
    void Rx(size_t q, float_t theta); // 在底层使用U3实现

    // 首先进行电路编译优化，计算所需的物理内存空间
    // 若当前尚未申请内存或已申请的内存空间不足，则重新执行内存申请
    // 完成编译优化和内存申请后，将sv状态重置为(1, 0, ..., 0)，并执行演化
    // 可以被多次执行，每次都会重复执行上述完整流程
    void execute();

    // 执行cnt次测量，将结果写入results
    // measure 包含必要的准备过程作为子过程
    void measure(res_t* results, size_t cnt);

    // 便捷接口
    vector<res_t> Sampling(size_t shots);
    size_t required_M() const;
    size_t num_qubits() const;
};
```

### 4.3. 地址

为区分虚地址与实地址，本规范引入两种类型：

- `vaddr_t`：虚地址类型，等价于 `bitvec_t`，用于表示 $\mathbb{F}_2^N$ 中的 bitstring。
- `raddr_t`：实地址类型，定义为线性地址索引 `uint64_t`。

其中 `vaddr_t` 仅保留 bitvector 语义，不提供线性地址语义相关接口（如加法、顺序比较等）；线性地址运算由 `raddr_t` 及其辅助函数承载。

```cpp
using vaddr_t = bitvec_t;

typedef uint64_t raddr_t;

// raddr 位操作辅助函数
raddr_t raddr_e_i(size_t i);                     // 1ULL << i
raddr_t raddr_lower_bits(raddr_t x, size_t n);  // x 的低 n 位
raddr_t raddr_higher_bits(raddr_t x, size_t n); // x 去掉低 n 位后的高位部分
```

### 4.4. 地址映射

在[第3.2节：`X` 类门与地址空间映射](#32-x-类门与地址空间映射)中说明了 $N$ 维实-虚地址空间映射：$x_v = A x_r \oplus b$。考虑到以下事实：

- 虚地址空间下的状态向量往往会出现高度稀疏性，例如 cat state：$\tfrac{1}{\sqrt{2}}\lvert 0\cdots 0\rangle + \tfrac{1}{\sqrt{2}}\lvert 1\cdots 1\rangle$。
- `sv` 的初始状态 $\lvert 0\cdots 0\rangle$ 同样具有高度稀疏性。
- `Z` 类门 / `X` 类门不会引入新增非零元，仅有 `H`/`U3` 门可能导致非零元数量增加。

本节定义地址映射矩阵类型 `bitmat_t`；奇偶判定子抽象 `selector_t`（对应[第3.3.2节：实地址空间中的neighbor](#332-实地址空间中的neighbor)中的 $S_k$）放在[第4.5节：判定子](#45-判定子)中说明。

因此，我们可以在实地址空间中仅存储虚地址空间中的非零元，以此支持更多 qubit。这通过引入变长实地址向量 $x_r$ 实现。设 $x_r$ 长度为 $m$，$A$ 由 $N$ 阶方阵变为 $N\times m$ 阶矩阵，并且 $m$ 可随着电路演化而增长。从而，我们只需要使用实地址空间中的低位连续 $2^m$ 个元素 `sv[0..2^m)` 就可以完整描述虚地址空间。

#### 4.4.1. 变长实地址空间

对于 $m$ 的取值，首先考虑两个平凡情况：

- **初始状态**：`sv` 初始逻辑状态为 $(1,0,\dots,0)$。此时非零元数量为 $1$，即 $m$ 的初始值为 $\log_2 1 = 0$，$A$ 为空（$N\times 0$ 阶），$b$ 为 $N$ 阶全 0 向量。实地址空间中仅保存一个非零元 `1`。
- **$m$ 与 $N$ 相等**：$A$ 成为 $N$ 阶方阵，退化为[第3.2节：`X` 类门与地址空间映射](#32-x-类门与地址空间映射)中描述的双射。

对于 $0 \le m < N$ 的一般情况，分别考虑 `Z/X` 类门的作用：

- **`X` 类门**：不影响非零元数量，只在 $A$ 和 $b$ 上进行行变换，规则同[第3.2节：`X` 类门与地址空间映射](#32-x-类门与地址空间映射)所述。
- **`Z` 类门**：不影响非零元数量，只需要遍历实地址空间中的 $2^m$ 个元素并更新振幅。

`H`/`U3` 门的处理相对复杂。回顾[第3.3节：`H` 门与 `U3` 门的处理](#33-h-门与-u3-门的处理)中的实地址空间 neighbor 关系：在等长情形下可写为 $\delta = A^{-1}e_k$。在变长情形中等价为线性方程组 $A\delta=e_k$，当：

- 方程组有解 $\hat{\delta}$ 时，该门仅涉及实地址空间上现有非零元之间的信息交换，不引入新增非零元。直接在实地址空间上使用 $\hat{\delta}$ 进行振幅更新即可。
- 方程组无解（超定）时，执行实地址空间扩张操作 `expand`。此时仅令 $m\leftarrow m+1$ 以扩大逻辑可见区间；新增区间在此前的 `reset()` 阶段已被预置为 0，因此 `expand()` 本身无需额外清零。随后令 $A'=(A,e_k)$，则方程组 $A'\delta' = e_k$ 有解 $\hat{\delta'}=(0,\dots,0,1)^T$，退化至上一种情况。

$m$ 随电路演化的增长过程可以在编译期确定，因而可以在实际运行前确定 $m$ 的最大值 $M$ 并提前申请好足够的内存。

#### 4.4.2. 接口

地址映射矩阵类型 `bitmat_t` 提供的接口如下（注意 `x` 为实地址，`rhs` 为虚地址）：

```cpp
class bitmat_t
{
  public:
    // 构造N*0阶矩阵
    bitmat_t(size_t N);
    size_t N() const;
    size_t m() const;

    // 行操作（F2）
    void row_xor(size_t dst, size_t src);
    // 返回第 i 行 bitstring 的线性编码
    raddr_t get_row(size_t i) const;

    // 线性方程（F2）：求解 A x = rhs
    // rhs 为虚地址，x 为实地址
    // 若有解，返回 true 并将一个解写入 x；否则返回 false
    bool solve(const vaddr_t &rhs, raddr_t &x) const;

    // 地址变换运算
    bitvec_t mul(raddr_t real) const;

    // 右侧追加一列（用于 expand 后 A <- (A, e_k)）
    void append_col(const bitvec_t &col);
};
```

此外，执行层基于 `A/b/sv` 还需要如下内部组合操作：

```cpp
// 求解 A*delta=e_k；若无解则执行 expand 并返回可用delta
raddr_t solve_expand(size_t k);
```

该接口属于 `internal API`，用于门执行流程中的地址扩张与邻居求解，不对库调用者直接暴露。

### 4.5. 判定子

判定子 `selector_t` 对应[第3.3.2节：实地址空间中的neighbor](#332-实地址空间中的neighbor)中定义的
$$
S_k(x_r)=\langle x_r,\alpha_k\rangle\oplus\beta_k
$$
用于在实地址空间上进行 even/odd 判定。

实现层面中，`selector_t` 内部使用一个 `uint64_t` 打包存储：

- 最高位 `bit63` 存储 `beta`；
- 低 63 位 `bits[0..62]` 存储 `alpha`。

接口如下：

```cpp
class selector_t
{
  public:
    // 定义 S(x)=<x,alpha> xor beta
    // 内部用一个 uint64_t 打包存储：最高位(bit63)=beta，低63位(bits[0..62])=alpha
    selector_t(raddr_t alpha, bool beta);

    // 在实地址空间上计算判定值：false=even, true=odd
    bool eval(raddr_t real) const;

  private:
    uint64_t packed_;
};
```

在实现中，kernel 既可能遍历单个 `segment`，也可能遍历整个本地 `block`；两者都可以统一看成“某个连续本地区间”上的局部索引 `i`（范围 `0..2^L-1`）。
因此需要把“全局判定子”投影为“局部判定子”，使得对任意实地址
$$
x_r = \mathrm{local\_base} + i
$$
都有：
$$
S_{\mathrm{local}}(i) = S_k(x_r)
$$
具体做法是：保留 `alpha` 的低 `L` 位作为 `alpha_low`，并把本地区间基址的高位贡献折叠进 `beta`：
$$
\alpha_{\text{low}} = \alpha \ \& \ \big((1\ll L)-1\big),\quad
\beta_{\text{local}} = S_k(\mathrm{local\_base})
$$
从而定义
$$
S_{\mathrm{local}}(i)=\langle i,\alpha_{\text{low}}\rangle\oplus\beta_{\text{local}}
$$
这保证了在本地 kernel 内仅用 `i` 即可得到与全局判定子一致的 even/odd 划分，并避免每次计算都携带高位参与内积。

执行层需要构造第 `k` 个 qubit 的全局判定子 $S_k$，并进一步结合本地区间基址 `local_base` 生成局部判定子 $S_{local}$。对应内部 helper 可抽象为：

```cpp
selector_t make_selector(size_t k);
selector_t make_local_selector(selector_t S_k, raddr_t local_base, size_t local_bits);
```

这些 helper 同样属于 `internal API`，只服务于门执行流程。

### 4.6. sv 向量

`sv` 向量由 `ZXH` 的内部状态持有，类型为 `sv_t`，负责管理物理内存空间的申请和释放，并在物理内存空间上建立一个抽象的实地址空间视图，即一个 `val_t` 数组。

#### 4.6.1. 实地址空间抽象

对任一时刻的 `sv_t`，定义：

- `M`：当前实地址空间位宽（逻辑可见长度为 `2^M`）；
- `m`：当前已使用位宽（仅 `sv[0..2^m)` 可能非零）。

两者满足约束关系：
$$
0 \le m \le M
$$

初始态与位宽演化语义如下：

1. `reset()` 将所有 `worker` 的本地 block 置零，并仅由 `worker0` 写入 `sv[0]=1`，从而将状态重置为基态；
2. `expand()` 仅令 `m = m+1` 以扩展逻辑可见区间，不额外改写 `worker` 内存；
3. 在门层面，`Z` 类门与 `X` 类门不改变 `m`，仅 `H`/`U3` 门可能触发 `expand()`。

物理内存空间可能分布在多个 `worker` 上，关于物理内存空间和实地址空间分布方式以及 `expand` 规则的细节详见[第6节：内存抽象](#6-内存抽象)。

#### 4.6.2. 接口

`sv_t` 与存储布局直接相关的接口如下：

```cpp
class sv_t
{
  public:
    // 当前已使用位宽 m，始终满足 0 <= m <= M
    size_t used_bits() const;

    // 复位：所有 worker 的本地 block 置零，仅 worker0 写入 sv[0] = 1
    void reset();
    // 重新申请物理内存空间
    void resize(size_t M_new);
    // 扩展：m <- m+1，仅扩大逻辑可见区间（要求 m < M）
    void expand();

    // 获取某个 segment 起始地址对应的连续内存指针（长度为 2^I）
    val_t *segment_ptr(raddr_t seg);
};
```

其中 `M/I/J/K/block_start/block_end` 等布局相关状态属于 `sv` 内部协同语义的一部分，可由实现保存在 `sv_t` 中，但不要求作为稳定的 `public API` 对库调用者暴露。跨 `worker` 协同所依赖的底层通信原语定义见[第7节：通信原语](#7-通信原语)。

#### 4.6.3. 中层协同接口（Internal API）

除上述 `public API` 外，为支持 `H`/`U3` 门的 inter `segment` 计算，`sv` 层还需要一组中层 `internal API`。它们位于 `comm` 原语之上、`ZXH` 门执行流程之下，用于把“按本地 `segment` 遍历、计算 neighbor、组织交换与复用 slot”这类逻辑从执行层中抽离出来。

其抽象可写为：

```cpp
struct neighbor_t
{
    raddr_t seg;
    val_t *local;
    const val_t *remote;
};

class neighbor_stream_t
{
  public:
    neighbor_stream_t(sv_t &sv, raddr_t delta_bs);
    bool acquire(neighbor_t &neighbor);
    void release();
};
```

其语义为：

1. `neighbor_t` 表示一个已经就绪的 `segment` 邻居视图；其中 `seg` 为当前本地 `segment` 起始地址，`local` 指向本地可写 `segment`，`remote` 指向远端只读 `segment` 快照；
2. `neighbor_stream_t` 的生命周期仅覆盖一次门执行中的 inter 分支；它负责遍历当前 `worker` 本地区间内的各个 `segment`，并逐个产出可供计算使用的 `neighbor_t`；
3. `sv_t` 在内部持有稳定的 `slot_pool_t`，用于管理可复用的通信 `slot`。`resize()` 负责在 `segment_len = 2^I` 变化时重新配置该 `slot pool`；`expand()` 只改变逻辑可见区间，不触发 `slot pool` 重配；
4. `acquire(...)` 返回下一个已就绪的 `neighbor_t`，并允许内部继续为后续 `segment` 推进交换；`release()` 表示当前 `neighbor_t` 已消费完成，对应底层 `slot` 可以复用；
5. `neighbor.remote` 的有效期仅持续到与之配对的 `release()` 调用之前。

### 4.7. 门电路

门电路由 `ZXH` 类的一个私有成员变量 `vector<gate_t> gates` 表示。
关于 `gates` 上的等价变换操作定义详见[第9节：电路变换](#9-电路变换)。
`gate_t` 的类型定义如下：

```cpp
enum class gate_type_t
{
    None,
    Z, // 被Rz包含，但部分情况下可以用于编译优化
    Rz,
    CRz,
    X,
    CX,
    H,
    U3
};

// 对所有类型的 gate 采用同一个定义以保证 gate_t 定长
class gate_t
{
    gate_type_t type;
    size_t cq, q;
    float_t theta, lambda, phi;
};
```

## 5. 进程抽象

本节定义运行时中的 `process`、`device`、`worker` 与 `runtime` 关系，以及它们与 `ZXH` 生命周期的约束。

### 5.1. worker 的定义

运行时涉及如下概念：

- **Process**：由操作系统或 launcher（如 `mpirun`）启动的宿主进程；
- **Device**：`process` 绑定的执行设备。CPU 后端对应 host memory，CUDA 后端对应一张 GPU；
- **Worker**：单个 `ZXH` 实例在一次 `execute`/`measure` 期间使用的最小执行与通信单元，持有一个 `sv_t` 并负责该状态上的本地计算与跨 `worker` 协同；
- **Runtime**：进程级运行时环境，负责初始化/结束 MPI、日志与异常退出等全局行为。

对当前项目，规定：

1. 单个 `worker` 持有一个 `sv_t`；
2. 单个 `ZXH` 对象持有一个 `sv_t`，因此对应一个 `worker`；
3. 一个 `process` 对应一张 `Device`；
4. 同一 `process` 可以持有多个 `worker`，这些 `worker` 共享同一张 `Device`；
5. 共享同一张 `Device` 的多个 `worker` 不可并发执行 `execute`；当前规范仅要求顺序执行；
6. `Runtime` 的生命周期属于 `process` 级，而不属于某个 `worker` 或 `ZXH` 对象。

### 5.2. 当前版本的映射规则

当前版本采用“每进程一张 Device”的执行模型：

- 对 `single / omp / cuda` backend，系统只有一个 `process`；对任意一次 `execute`，仅存在 `worker0`；
- 对 `mpi / mpi_omp / mpi_cuda` backend，对任意一次 `execute`，每个 MPI 进程恰好提供一个活动 `worker`；
- 因此对同一次 `execute`，当前版本固定采用 `worker_id == mpi_rank`；
- 对 `cuda / mpi_cuda` backend，每个 `process` 绑定一张 GPU，其活动 `worker` 使用该 GPU；
- 尽管同一 `process` 可以持有多个 `worker`，但在任意时刻最多只有一个本地 `worker` 参与 `execute`；
- `init(...)` 时检测到的 MPI 进程数必须为 `2` 的幂；否则直接 fail fast。对不带 MPI 的 backend，可等价看作 `nprocs = 1`，天然满足该约束。

`worker` 本身是一层屏蔽 MPI 差异的抽象封装。上层只依赖活动 `worker` 数、`worker_id` 与跨 `worker` 协同语义，而不直接区分底层是否带 MPI。特别地，对 `single / omp / cuda` backend，约定 `nprocs = 1`、`rank = 0`，因此唯一活动 `worker` 的 `worker_id = 0`；这样 `sv_t`、测量流程与通信相关接口仍可沿用同一组后端无关调用路径。

在该模型下，多节点多卡执行通过 `mpi_cuda` 后端实现：对同一次 `execute`，每个 MPI 进程上的活动 `worker` 使用其本地 `sv_t` 负责一个 `worker` 地址区间的计算与通信。

### 5.3. 拓扑与配置职责

为降低运行时复杂度，当前版本不在代码层对 `worker_id` 做重映射，而是直接采用 launcher 给出的 `mpi_rank` 顺序。拓扑相关职责交由配置层负责，包括：

- 节点内 `rank` 排列；
- 每个 `rank` 绑定哪一张 GPU；
- `CUDA_VISIBLE_DEVICES` 等设备可见性设置；
- 多节点场景下的 hostfile / scheduler placement。

因此，配置层应尽量保证拓扑友好的 `rank` 编码。例如在多节点多卡场景下，同一节点上的 `worker_id` 宜连续编号，以使低位 `xor` 触发的 neighbor 通信尽可能留在节点内。

若仅 `rank` 排列不合理，则会影响通信 locality 与性能，但不改变计算语义；若出现多个 `rank` 绑定同一张 GPU、某个 `rank` 未绑定 GPU、或 `init(...)` 检测到 MPI 进程数不是 `2` 的幂等情况，则属于运行环境错误。

### 5.4. 程序生命周期示例

完整程序的推荐生命流程如下：

```cpp
int main(int argc, char **argv)
{
    init(&argc, &argv); // 建立进程级 runtime；MPI OFF 时等价于单进程初始化

    {
        ZXH z1(n1); // 当前 process 上的本地 worker #1
        build_circuit_1(z1);
        z1.execute();
        z1.measure(results_1, shots_1);
    }

    {
        ZXH z2(n2); // 与 z1 共享同一 process / Device 的本地 worker #2
        build_circuit_2(z2);
        z2.execute(); // 必须与 z1 顺序执行，不能并发
        z2.measure(results_2, shots_2);
    }

    finalize(); // 释放进程级 runtime
}
```

该伪代码同时适用于 MPI 开启与关闭两种情况：

1. `init(...)` 与 `finalize()` 负责进程级运行时初始化/释放；
2. MPI 开启时，所有进程都执行同一套顶层控制流，只是每个进程持有自己的活动 `worker`；
3. MPI 关闭时，可视为 `nprocs = 1`、`rank = 0` 的特例，因此上述调用顺序保持不变；
4. 同一 `process` 可以顺序创建和使用多个 `ZXH` 对象，但这些对象对应的 `worker` 不可并发执行 `execute`。

## 6. 内存抽象

本节定义统一的内存空间抽象，作为上下层的参考接口：上层仅依赖抽象语义，下层可替换实现细节。

### 6.1. 内存类型

当前系统区分两类内存：

- **Worker 内存**：后端无关的工作内存，可位于主存或 Device 内存，主要用于存储 `sv` 向量及其相关的本地 `segment` 数据；
- **Host 内存**：位于主存，主要用于测量流程以及少量辅助数据结构。

两类内存的基础接口定义如下：

```cpp
val_t *worker_alloc(size_t elem_count);
void worker_free(val_t *ptr);
void worker_set_zero(val_t *ptr, size_t begin, size_t end);

val_t *host_alloc(size_t elem_count);
void host_free(val_t *ptr);
void host_set_zero(val_t *ptr, size_t begin, size_t end);

// 对 worker 内存中的单个元素写入给定值
void worker_mem_set(val_t *ptr, val_t value);
```

其中 `worker_alloc/worker_free/worker_set_zero` 操作 `worker` 内存，`host_alloc/host_free/host_set_zero` 操作 `host` 内存；`worker_mem_set` 用于执行 `sv[0]=1` 这类单元素初始化。

除非特别说明，本节后续内容中的地址空间、`segment`、`worker slice`、`expand` 等概念均针对 `worker` 内存。

### 6.2. 实地址空间层级（Address Space Hierarchy）

可用实地址空间在 `execute` 时被按位宽需求 `M` 申请，并自底向上被分为三个层级：

- **Segment**：长度为 `2^I` 的连续内存空间，是计算 kernel 与通信的最小单位。`I` 决定分片粒度，默认上限为 `10`，可由用户配置。
- **Worker Slice**：由 `2^J` 个连续 Segment 组成，总长度为 `2^(I+J)`。`J` 表示单个 `worker` 本地区间内的 segment 编号位宽，并受本地可申请物理内存容量约束。
- **Address Space**：由 `2^K` 个离散 Worker Slice 组成，总长度为 `2^(I+J+K)`。`K` 表示 `worker_id` 位宽，因此同一次 `execute` 需使用 `2^K` 个活动 `worker`。

因此实地址空间的总位宽满足：
$$
M = I + J + K \le 63
$$

实地址空间中任意地址可统一表示为：
$$
addr=[worker\_id:K][segment\_id:J][offset:I]
$$

其等价的线性展开形式为：
$$
addr = worker\_id \cdot 2^{I+J} + segment\_id \cdot 2^I + offset
$$
其中约束为：
$$
0 \le offset < 2^I,\quad 0 \le segment\_id < 2^J,\quad 0 \le worker\_id < 2^K
$$

`execute` 时 `M` 与 `I/J/K` 的对应关系的伪代码如下：

```cpp
I=J=K=0;
if (M < I_MAX)
    I = M;
else if (M < I_MAX + K_MAX)
{
    I = I_MAX;
    K = M - I;
}
else
{
    I = I_MAX;
    K = K_MAX;
    J = M - I - K;
}
```

`M` 与 `I/J/K` 的增长策略如下：当 `M=0` 时，`I=J=K=0`；随着 `M` 增长，`I` 优先增长至其配置上限，其后 `K` 增长至可用 `worker` 上限，最后由 `J` 承担剩余增长。

### 6.3. 物理内存分布与 expand 逻辑

在分布式执行中，每个活动 `worker` 持有一个本地 `sv_t` 实例，且该 `sv_t` 对应唯一的本地连续地址区间。
换言之，单个 `sv_t` 仅持有某个固定 `worker_id` 对应的连续地址区间。

对给定 `worker_id`，定义该 `sv_t` 的可用地址起点 `block_start` 为：
$$
block\_start=[worker\_id:K][0^J][0^I]
$$

此外，每个 `sv_t` 还需维护一个实际使用的地址长度 `len`，满足 `len <= pow(2, I + J)`。`reset()` 时，所有 `worker` 会先将整个本地 block 清零，再由 `worker0` 写入 `sv[0]=1`；因此在 `m = 0` 时，`worker0.len == 1`，其他 `worker` 的 `len` 为 `0`。由于 `expand()` 只会单调扩大 `len`，且未激活区间在 `reset()` 后始终保持为 `0`，因此 `expand()` 本身不需要额外的 memset。随着电路运行，每次触发 `expand` 操作都会引起一个或多个 `worker` 上 `len` 变量的变化。具体规则为：

1. 前 `I` 次 `expand` 优先填满 `worker0` 的低 `I` 位（即一个 `segment`）；
2. 随后 `K` 次 `expand` 填满所有 `worker` 的低 `I` 位；
3. 最后 `J` 次填满整个实地址空间。

伪代码如下：

```cpp
m++;
if (m <= I && worker_id == 0)
    len = len * 2;
else if (m <= I + K && worker_id < pow(2, m - I))
    len = pow(2, I);
else
    len = pow(2, m - K);
```

## 7. 通信原语

本节定义跨 `worker` 协同所需的底层 build block。它位于内存抽象之上、计算流程与测量流程之下；后续各章节只依赖本节给出的接口语义，而不依赖具体 backend 实现。

### 7.1. 总览

通信原语统一共享[第5节：进程抽象](#5-进程抽象)中运行时提供的 `rank()/nprocs()` 语义，即：

- `rank()` 给出当前 `worker` 的全局编号；
- `nprocs()` 给出当前活动 `worker` 总数；
- 对不带 MPI 的 backend，退化为 `rank()=0, nprocs()=1`。

在此基础上，本节区分两类通信接口：

1. **Worker memory 原语**：操作 `worker` 内存；主要用于 `sv` 的 `segment` 级点对点交换；
2. **Host memory 原语**：操作 `host` 内存；主要用于电路广播、测量中的全局概率协同与结果汇总。

应当指出，这里的区分只针对内存语义，而不针对编号体系：两类原语均使用同一套 `rank()/nprocs()`。

### 7.2. Worker memory 原语

`worker` 内存原语面向跨 `worker` 的 `segment` 级数据交换。它们屏蔽底层 `worker` 内存位于主存还是 device memory 的差异，并统一提供异步点对点接口。

首先引入异步请求类型 `request_t`：

```cpp
class request_t
{
  public:
    request_t();
};
```

其配套原语如下：

```cpp
void worker_send(const val_t *src, size_t elem_count, size_t peer, request_t &req);
void worker_recv(val_t *dst, size_t elem_count, size_t peer, request_t &req);
void worker_wait(request_t &req);
```

其语义分别为：

1. `worker_send(...)`：从当前 `worker` 的 `worker` 内存向 `peer` 异步发送 `elem_count` 个 `val_t`；
2. `worker_recv(...)`：在当前 `worker` 的 `worker` 内存中准备长度为 `elem_count` 的接收缓冲，并从 `peer` 异步接收数据；
3. `worker_wait(...)`：同步等待对应请求完成。

在这些原语之上，可将“一次 `segment` 的双向交换”封装为基本类型 `worker_slot_t`：

```cpp
class worker_slot_t
{
  public:
    worker_slot_t();

    // 配置当前 slot 的 segment 长度
    void configure(size_t segment_len);

    // 对 peer 发起一次双向 segment 交换
    void pre_exchange(val_t *send_segment, size_t peer);

    // 同步等待本轮 exchange 完成，并返回接收缓冲区指针
    val_t *wait_exchange();

    // 当前 segment 消费完成后调用，以复用该 slot
    void release();
};
```

`worker_slot_t` 的语义是：

- `pre_exchange(...)` 内部先对接收缓冲区发起 `worker_recv(...)`，再对 `send_segment` 发起 `worker_send(...)`；
- `wait_exchange()` 对内部请求依次调用 `worker_wait(...)`，并返回已就绪的接收缓冲；
- `release()` 仅表示该 `slot` 对当前 `segment` 的占用结束，后续可被再次用于新的 `segment`。

因此，`worker_slot_t` 只是对“一个 `segment` 的双向交换”的基本封装，不承担更上层的调度策略。

### 7.3. Host memory 原语

`host` 内存原语工作在主存上，主要用于 `worker` 级协调逻辑，而不直接传输 `sv` 的 `segment` 数据。

基础接口可抽象为：

```cpp
void host_broadcast(void *data, size_t bytes, size_t root);

void host_allreduce_sum(const float_t *send, float_t *recv, size_t count);
void host_exscan_sum(const float_t *send, float_t *recv, size_t count);

void host_gather_size(size_t local_size, size_t *root_sizes, size_t root);
void host_gatherv(const void *send_data, size_t send_bytes,
                  void *root_data, const size_t *root_sizes,
                  const size_t *root_displs, size_t root);
```

其语义分别为：

1. `host_broadcast(...)`：由 `root` 将一段 `host` 缓冲区广播到所有 `worker`；
2. `host_allreduce_sum(...)`：对各 `worker` 的 `host` 标量或数组做求和归约，并将结果写回所有 `worker`；
3. `host_exscan_sum(...)`：对各 `worker` 的 `host` 标量或数组做前缀和扫描，并返回当前 `worker` 之前的和；
4. `host_gather_size(...)`：将各 `worker` 的本地大小信息汇总到 `root`；
5. `host_gatherv(...)`：按 `root_sizes/root_displs` 描述的可变长度布局，将各 `worker` 的 `host` 数据汇总到 `root`。

对不带 MPI 的 backend，这些接口均退化为单 `worker` 语义：`broadcast` 为 no-op，归约或扫描结果等于本地输入，`gather` 等价于本地复制。

### 7.4. 基本使用模式

对 `H`/`U3` 的 inter `segment` 计算，`worker_slot_t` 的同步使用方式可写为：

```cpp
worker_slot_t slot;
slot.configure(segment_len);
slot.pre_exchange(send_segment, peer);
val_t *recv_segment = slot.wait_exchange();
// 使用 recv_segment 执行后续计算
slot.release();
```

若需要在“当前段计算”和“下一段交换”之间形成 overlap，则可直接使用多个 `worker_slot_t` 交替推进。例如双缓冲写法如下：

```cpp
worker_slot_t slots[2];
slots[0].configure(segment_len);
slots[1].configure(segment_len);

slots[0].pre_exchange(ptr_seg0, peer0);
for (size_t t = 0; t < num_segments; t++)
{
    size_t cur = t & 1;
    size_t nxt = cur ^ 1;

    val_t *remote = slots[cur].wait_exchange();

    if (t + 1 < num_segments)
        slots[nxt].pre_exchange(ptr_next, peer_next);

    // 使用 remote 与本地 segment 做后续计算

    slots[cur].release();
}
```

这段伪代码只描述原语层的调用关系；具体如何选择 `slot` 数量、是否使用双缓冲，以及如何组织更复杂的调度，属于实现层优化细节，不属于本节规范范围。

需要进一步明确的是：`comm` 层只暴露这些底层原语，本身不承担门级调度职责。对 `H`/`U3` 的 inter `segment` 计算，执行层应通过[第4.6.3节：中层协同接口](#463-中层协同接口internal-api)中定义的 `neighbor_stream_t` 使用这些原语，而不在 `ZXH` 层直接维护多个 `worker_slot_t` 的复用关系。

## 8. 计算流程

本节描述：在[第7节：通信原语](#7-通信原语)定义的底层接口之上，`ZXH::execute` 如何逐个处理输入门序列 `vector<gate_t> gates`。本节仅覆盖上层调用流程以及各类 `kernel` 的作用，不涉及 `kernel` 的具体实现。

### 8.1. Overview

`execute` 执行过程中维护以下 4 个核心状态变量：

- **`val_t data[]`**：当前 `worker` 的本地实地址切片抽象；逻辑上覆盖当前 `worker` 地址区间（长度 `2^{I+J}`）。执行 `reset()` 后，所有 `worker` 的本地 block 均为 0，且仅 `worker0` 的 `data[0] = 1`。
- **`size_t m`**：实际使用的实地址空间位长。仅 `data` 的低 $2^m$ 位有实际意义，其余位在逻辑上视为 0。初始状态下 `m = 0`。
- **`bitmat_t A`**：地址变换矩阵，列数随 `m` 变化；初始状态下为 `N×0` 阶矩阵。
- **`bitvec_t b`**：`N` 阶地址变换向量，初始状态下为零向量。

从模块分层上看，`execute` 采用如下调用关系：

1. `ZXH` 负责门级控制流、地址映射更新以及 `kernel` 选择；
2. `sv` 负责按 `segment` 组织本地遍历，并在 inter 情况下提供 `neighbor_stream_t` 这一中层调度接口；
3. `comm` 仅负责 `worker_slot_t`、`request_t` 与 `host` collectives 等底层原语，不直接承担门级流水调度。

`execute` 的整体流程可简化为以下伪代码：

```cpp
void execute()
{
    vector<gate_t> gates_opt;
    size_t gate_count = 0;

    if (rank() == 0)
    {
        gates_opt = compile_optimize(gates); // 在 root worker 上先做电路编译优化
        gate_count = gates_opt.size();
    }

    host_broadcast(&gate_count, sizeof(size_t), 0);
    if (rank() != 0)
        gates_opt.resize(gate_count);
    host_broadcast(gates_opt.data(), gate_count * sizeof(gate_t), 0);

    size_t M = calc_mem(gates_opt); // 计算电路所需的实地址空间位长 M
    sv.resize(M); // 若 capacity 足够则复用物理空间，否则扩容
    sv.reset(); // 所有本地 block 清零；仅 worker0 上 sv[0]=1
    A = bitmat_t(N); // N×0
    b = 0^N;
    for (gate_t g : gates_opt)
        apply_gate(sv, g); // 8.2: `X` 类门, 8.3: `H`/`U3` 门, 8.4: Z 类门
}
```

编译优化的具体规则见[第9节：电路变换](#9-电路变换)。
`execute` 执行完成后，`sv` 的最终状态可用于测量（详见[第10节：测量](#10-测量)）。

### 8.2. `X` 类门的计算流程

`X` 类门（`X/CX`）不直接更新 `sv` 振幅，而是通过更新地址映射 `(A, b)` 生效。
其数学定义与更新规则见[第3.2节：`X` 类门与地址空间映射](#32-x-类门与地址空间映射)，对应伪代码如下：

```cpp
void apply_x(bitvec_t &b, size_t i)
{
    b.set_bit(i, !b.get_bit(i));
}

void apply_cx(bitmat_t &A, bitvec_t &b, size_t i, size_t j)
{
    A.row_xor(j, i);
    b.set_bit(j, b.get_bit(j) != b.get_bit(i));
}
```

### 8.3. `H`/`U3` 门的计算流程

两者执行逻辑类似。本节以作用在第 $k$ 个 qubit 上的 `H` 门为例，
描述在给定 $k$ 和地址变换 $(A, b)$ 时，如何：

1. 调用 `solve_expand(k)` 计算 $\delta$；
2. 调用 `make_selector(k)` 构造本轮判定子 $S_k$，并据此判定本轮计算的内存访问模式；
3. 遍历当前 `worker` 地址区间中的所有 `segment`，按访问模式调用不同的计算 `kernel` 执行振幅混合；
4. 在 inter 情况下，通过[第4.6.3节：中层协同接口](#463-中层协同接口internal-api)定义的 `neighbor_stream_t` 组织跨 `worker` 的 `segment` 遍历与异步交换；其底层再调用[第7.2节](#72-worker-memory-原语)中的 `worker_slot_t`。

先回顾[第3.3.2节：实地址空间中的neighbor](#332-实地址空间中的neighbor)中的 selector 记号：
$$
S_k(x_r)\equiv \langle x_r,\alpha_k\rangle\oplus\beta_k,\quad
\alpha_k \equiv A^\top e_k,\quad
\beta_k \equiv \langle b,e_k\rangle
$$

在变长实地址空间下，`solve-expand` 逻辑由内部 helper `solve_expand(k)` 封装（见[第4.4.2节：接口](#442-接口)）。
对应调用流程如下：
```cpp
raddr_t delta = solve_expand(k);
selector_t S_k = make_selector(k);
```

由此得到本轮门的 $\delta$ 与判定子 $S_k$ 后，即可进行后续计算。
对任意实地址 $x_r$，$S_k(x_r)=0$ 时表示其为 even，$S_k(x_r)=1$ 表示 odd。$x_r$ 的 neighbor 为：
$$
x_{\text{neighbor}} = x_r \oplus \delta
$$

当执行 `H` 门时，每对 $(x_r, x_{\text{neighbor}})$ 的两振幅会发生 2x2 线性混合。考虑当前 `worker` 本地地址区间内所有地址的 neighbor，易知：

1. 当 $\delta_b=0$ 时，neighbor 始终留在当前 `worker` 的本地 `block` 内，因此可把整个本地 `block` 视为一个统一的可写区间；
2. 当 $\delta_b\neq 0$ 时，neighbor 位于其他 `worker` 的本地区间，仍需按 `segment` 粒度组织交换与消费；
3. 无论是 block 还是 segment，局部地址空间内都可同时包含 even/odd 地址，因此 kernel 内部统一按 selector 判定，而不在外层再按奇偶拆分。

按[第6节：内存抽象](#6-内存抽象)中的地址布局
$$
addr=[worker\_id:K][segment\_id:J][offset:I]
$$
将 `delta` 分为三段：
$$
\delta=[\delta_b:K][\delta_s:J][\delta_o:I]
$$

对任意 `segment` 的起始地址 `seg`，其 neighbor `segment` 可写为：
$$
seg_{\text{neighbor}} = seg \oplus [\delta_b,\delta_s,0^I]
$$

为对齐当前实现，再进一步把低 `I+J` 位合并记为
$$
\delta_{so}=[\delta_s:J][\delta_o:I]
$$

据此得到两类情况：

1. **本地 Block 路径**：$\delta_b=0$
   neighbor 留在当前 `worker` 的本地 `block` 内；旧的 Reflexive（$\delta_s=0$）和 Intra（$\delta_s\neq 0$）两种情况在这一层统一由 block kernel 处理。
2. **跨 `worker` 的 Inter segment**：$\delta_b\neq 0$
   `neighbor segment` 位于不同 `worker` 的本地区间，需要通过 `sv` 层中层接口组织交换；其底层再调用第7.2节中的 `worker_slot_t`。

下面分别说明这两种情况的处理方式。

#### 8.3.1. Block-local path

当 $\delta_b=0$ 时，
$$
\delta=[0^K,\delta_{so}]
$$
因此任意本地地址 $x_r=[worker\_id][local\_off:(I+J)]$ 的 neighbor 为
$$
x_r^{(n)} = x_r \oplus \delta
$$
其高 `K` 位不变，仅当前 `worker` 内的低 `I+J` 位发生翻转。
换言之，pair 的两端都在同一个本地 `block` 内，可做原地更新。

为避免重复更新，对每个地址仅在 $S_k(x_r)=0$（even）时执行一次 pair 混合。
`H` 门下，若 $x_r$ 的 block 内偏移为 `i`，其 neighbor 偏移为
$$
j = i \oplus \delta_{so}
$$
并执行
$$
sv[i]\gets \frac{sv[i]+sv[j]}{\sqrt{2}},\quad
sv[j]\gets \frac{sv[i]-sv[j]}{\sqrt{2}}
$$
（实现时需先缓存旧值）。

```cpp
// Block-local 情况：对整个本地 block 原地执行 neighbor 振幅混合
void h_block_kernel(val_t *ptr1, size_t local_bits, raddr_t delta_so, selector_t S_block);

void h_block(sv_t &sv, raddr_t delta_so, selector_t S_k)
{
    selector_t S_block = make_local_selector(S_k, sv.block_start, sv.I + sv.J);
    val_t *ptr1 = sv.segment_ptr(sv.block_start);
    h_block_kernel(ptr1, sv.I + sv.J, delta_so, S_block);
}
```

这一路径统一覆盖旧语义中的两种局部情况：

1. $\delta_s=0$ 时，pair 落在同一 `segment` 内，对应原 Reflexive 情况；
2. $\delta_s\neq 0$ 时，pair 横跨当前 `worker` 内两个不同的 `segment`，对应原 Intra 情况。

对当前实现而言，这两种情况都不再单独暴露为不同的 kernel 接口，而是统一由 `block_kernel` 在 `I+J` 位局部地址空间上处理。

#### 8.3.2. Inter segment

Inter segment 的情况下，`neighbor segment` 位于其他 `worker` 的本地区间，不能直接作为本地可写输入。
与 block-local 情况不同，这里不再把整个本地 `block` 作为单次输入，而是继续按 `segment` 粒度推进；并且不需要 `seg < neighbor` 条件：每个本地 `seg` 都必须被更新一次。

按照[第6节：内存抽象](#6-内存抽象)中的地址分解，`neighbor segment` 的目标 `worker` 编号就是其高 `K` 位，因此：
$$
peer = seg_{\text{neighbor}} >> (I+J)
$$

在分层设计上，这一路径不应由 `ZXH` 直接维护多个 `worker_slot_t`。更合适的职责划分是：

1. `comm` 层提供单个 `segment` 交换所需的 `worker_slot_t`；
2. `sv_t` 内部持有稳定的 `slot_pool_t`，作为这些 `slot` 的长期资源拥有者；
3. `neighbor_stream_t` 在一次门执行期间负责：
   - 逐个遍历当前 `worker` 的本地 `segment`；
   - 计算 `neighbor = seg ^ delta_bs` 与 `peer`；
   - 组织 `pre_exchange / wait_exchange / release` 的推进顺序；
4. `ZXH` 只消费已经就绪的 `neighbor_t`，并调用 `h_inter_kernel(...)` 或 `u3_inter_kernel(...)` 完成计算。

对应的上层调用流程可抽象为：

```cpp
// Inter 情况：第二输入来自远端只读 segment；仅写回本地 segment
void h_inter_kernel(val_t *ptr1, const val_t *ptr2, size_t I, raddr_t delta_o, selector_t S_seg);

void h_inter(sv_t &sv, raddr_t delta, selector_t S_k)
{
    raddr_t delta_o = raddr_lower_bits(delta, sv.I);
    raddr_t delta_bs = raddr_higher_bits(delta, sv.J + sv.K);
    neighbor_stream_t stream(sv, delta_bs);
    neighbor_t neighbor;

    while (stream.acquire(neighbor))
    {
        selector_t S_seg = make_local_selector(S_k, neighbor.seg, sv.I);
        h_inter_kernel(neighbor.local, neighbor.remote, sv.I, delta_o, S_seg);
        stream.release();
    }
}
```

其中，`neighbor_stream_t` 的内部实现可采用单缓冲、双缓冲或其他异步推进策略，但这些策略都被限制在 `sv` 层内部；对 `ZXH` 而言，它只观察到“逐个取得 ready 的 `neighbor_t` 并在消费后显式 `release()`”这一稳定语义。

`U3` 门的 Block/Inter 两类情况与 `H` 门完全同构，只是将 `2x2` 的 Hadamard 线性变换替换为给定的 `U3` 矩阵。

#### 8.3.3. 第一版 `u3-batch` 的边界

`u3-batch` 的调度单位不是单个 `U3/H` 门，而是一个连续的 `u3-cluster`。这里的 `u3-cluster` 指执行扫描中、被 `Z`-window flush 之后遇到的一个 maximal `H/U3` 连续区间。其内部只包含单比特基变换，不包含 `X/CX/CP/P` 等门。

第一版 `u3-batch` 不尝试覆盖整个 `u3-cluster` 的全部执行情况，而只覆盖其中的 **local no-expand 子区间**：

1. 若某个 `H/U3` 在当前 `(A,b)` 下需要 `expand()`，则它不进入 batch，而是作为 eager gate 立即执行；
2. 若某个 `H/U3` 的 neighbor 落到其他 `worker`，即 `delta_b != 0`，则它也不进入 batch，而是继续走现有的 inter 逐门执行路径；
3. 只有同时满足“**不触发 expand**”且“**`delta_b = 0`**”的门，才进入当前 local batch。

这样做的目的有两个：

- 不修改现有 `solve_expand()` 语义；
- 不把原本应在较小 `m` 上完成的门推迟到更大的 `m` 后执行，从而保持与 `\rho_L` 一致的执行成本模型。

换言之，第一版 `u3-batch` 不是“整段 cluster 一次性做完”，而是把一个 `u3-cluster` 顺序切分为：

1. 若干个 local-batch run；
2. 若干个 eager scalar gate（expand 或 inter）。

其中 eager gate 本身仍按原顺序执行；只有 local-batch run 内部允许合并与批处理。

#### 8.3.4. Host-side 调度与连续 `U3` 合并

第一版实现不引入 shadow `A/m/sv` 预演状态，而是直接基于当前真实 `(A,b,sv)` 对 `u3-cluster` 做一次从左到右的扫描。

在扫描 local-batch run 时，host 侧维护一个按 qubit 编号索引的 `pending_u3[q]`。它表示当前 run 内、尚未固化到 descriptor 列表中的单比特变换矩阵。处理规则如下：

1. 对当前门 `g(q)`，先用当前真实 `A` 探测 `e_q` 是否已在列空间中；
2. 若探测失败，则说明该门会触发新的 `expand()`：
   - 先 flush 当前 local batch；
   - 再按现有逐门路径 eager 执行该门；
   - 该 eager 执行内部仍调用现有 `solve_expand()`；
3. 若探测成功，再检查该门是否满足 `delta_b = 0`：
   - 若 `delta_b != 0`，先 flush 当前 local batch，再按现有 inter 路径逐门执行；
   - 若 `delta_b = 0`，则把该门吸收到 `pending_u3[q]` 中；
4. `u3-cluster` 扫描结束后，再 flush 一次当前 local batch。

由于一个 `u3-cluster` 内只包含单比特门，不同 qubit 上的门彼此可交换，因此 local-batch run 内可以安全地在 host 侧做“同 qubit 连续 `U3` 合并”的兜底优化，而不依赖编译器事先已经完成这项工作。合并后的结果是：

- 每个 qubit 在一个 local-batch run 内至多对应一个 fused `U3` 描述子；
- 因而一个 batch 的 descriptor 数上界就是当前可表示的 qubit 数。

结合当前实现中的 `M <= 63` 约束，第一版 `u3-batch` 的 descriptor 数上界固定为：

$$
N_{\text{desc}} \le 63
$$

因此这里不需要像 diagonal IR 那样引入 chunk 机制；一块固定大小、最多容纳 `63` 个 descriptor 的常量内存即可覆盖第一版实现。

可抽象为如下 host 调度流程：

```text
scan one u3-cluster from left to right:
    if gate expands:
        flush_local_batch()
        apply_u3_scalar(g)
        continue

    if gate is inter:
        flush_local_batch()
        apply_u3_scalar(g)
        continue

    absorb g into pending_u3[q]

flush_local_batch()
```

这里的 `flush_local_batch()` 会把所有非平凡的 `pending_u3[q]` 收集出来，生成一个 local descriptor list，并调用一次 batch kernel。若当前 run 中可收集到的描述子数量为 `0/1`，则可直接回退到现有逐门 `u3_block_kernel(...)` 路径。

#### 8.3.5. 第一版 local `u3-batch` kernel

第一版 `u3-batch` 只针对 `delta_b = 0` 的本地路径。其 device IR 不再按 `H/U3` 原始参数存储，而是直接存储融合后的 `2x2` 单比特矩阵：

```cpp
struct u3_batch_desc_t
{
    uint64_t packed_sel;
    uint64_t delta_so;

    float_t u00_re;
    float_t u00_im;
    float_t u01_re;
    float_t u01_im;
    float_t u10_re;
    float_t u10_im;
    float_t u11_re;
    float_t u11_im;
};
```

host 侧准备一块固定长度的 descriptor 缓冲，并把它一次性复制到 device 常量内存：

```cpp
constexpr size_t kU3BatchMaxDesc = 63;
__constant__ u3_batch_desc_t g_u3_batch_desc[kU3BatchMaxDesc];
```

第一版 kernel 设计目标不是减少 `U3` 数学上的总访存量，而是：

1. 减少逐门 kernel launch 开销；
2. 减少运行时逐门构造 selector / matrix / launch 参数的 host 开销；
3. 兜底完成同 qubit 的连续 `U3` 合并。

为保持一个 local-batch run 内多门 `U3` 的顺序语义，第一版建议采用 cooperative kernel。单次 launch 处理整个 local-batch run，并在 kernel 内对 descriptor 做顺序迭代；每处理完一个 descriptor 后做一次全 grid 同步，再进入下一个 descriptor。伪代码如下：

```cpp
cooperative kernel u3_local_batch_kernel(ptr, local_bits, gate_count):
    grid = this_grid()
    n = 2^local_bits

    for g in [0, gate_count):
        desc = g_u3_batch_desc[g]

        for off in grid_stride_range(0, n):
            if selector_eval(desc.packed_sel, off):
                continue

            j = off ^ desc.delta_so
            apply_2x2(desc, ptr[off], ptr[j])

        grid.sync()
```

这里的语义与当前单门 `u3_block_kernel(...)` 完全一致：

- `packed_sel` 决定当前地址是否属于 even 一侧；
- `delta_so` 给出 pair 对应的 neighbor 偏移；
- `apply_2x2(...)` 按融合后的 `U3` 矩阵更新这一对振幅。

由于 descriptor 数固定不超过 `63`，第一版实现不需要任何 chunk/header/cursor 设计。若运行环境不支持 cooperative launch，或当前 local-batch run 规模过小，则直接回退到现有逐门路径即可。

需要再次强调的是：这一版 `u3-batch` 只是第一阶段实现。它覆盖的是 local no-expand fast path，主要收益来自 launch reduction 与 host-side fusion；对 inter 路径的批处理、以及对 expand 触发点的更激进调度，留待后续版本处理。

### 8.4. `Z` 类门的计算流程

`Z` 类门按实地址遍历并按 selector 判定施加相位，不涉及 neighbor 交换。
其统一公式与 `Rz/CRz` 的数学定义见[第3.4节：`Z` 类门的处理](#34-z-类门的处理)。

本节描述的目标实现不再采用“逐门发射一个对角 kernel”的策略，而是把当前执行扫描中遇到的对角门统一降低为 `P/CP` 两类 primitive，在一个 diagonal window 内批量累计后一次性作用到当前本地 `block` 上。

这里约定：

- `diagonal window` 指执行扫描期间、被 `H/U3/RESET` 截断的一个对角累计区间；
- `X/CX` 不会截断该 window；它们只更新 `(A, b)`，后续对角门在更新后的 selector 语义下继续追加到同一 window；
- 若某个 window 中从未加入任何对角描述子，则该 window 是 `X-only block`，不会产生任何对角 kernel launch；
- 本节只定义运行时 batching 方案，不引入跨 window 的交换/重排 pass。

#### 8.4.1. 内部 lowering

执行层不直接保留 `Z/Rz/CRz` 三种独立 kernel 语义，而是统一降低为 `P` 与 `CP` 两类 primitive：

1. `Z(q)`：
$$
Z(q)\equiv e^{-i\pi/2}\,P(q,\pi)
$$
因此执行层做两件事：
- `global_phase *= e^{-i\pi/2}`
- 向当前 window 追加一个 `P(q, \pi)` 描述子

2. `Rz(q,\theta)`：
$$
Rz(q,\theta)\equiv e^{-i\theta/2}\,P(q,\theta)
$$
因此执行层做两件事：
- `global_phase *= e^{-i\theta/2}`
- 向当前 window 追加一个 `P(q, \theta)` 描述子

3. `CP(cq,q,\theta)`：
- 不改变 `global_phase`
- 直接向当前 window 追加一个 `CP(cq, q, \theta)` 描述子

4. `CRz(cq,q,\theta)`：
$$
CRz(cq,q,\theta)\equiv P(cq,-\theta/2)\cdot CP(cq,q,\theta)
$$
因此执行层顺序降低为：
- 先追加 `P(cq, -\theta/2)`
- 再追加 `CP(cq, q, \theta)`

上述 lowering 后，运行时只需要维护 `P` 与 `CP` 两类 batched diagonal primitive；`CRz` 不再对应单独的执行 kernel。

#### 8.4.2. Six-bucket 分类

对当前本地 `block` 而言，局部地址记为：
$$
off = [slice][lane]
$$

其中 `lane` 固定取低 `B=8` 位；若 `local_bits \le 8`，则退化为只有一个 `slice`。

对任一局部 selector
$$
S(off)=\langle off,\alpha\rangle\oplus\beta
$$
定义：
$$
\alpha_{low} = \alpha \bmod 2^B,\quad \alpha_{high} = \alpha >> B
$$

据此把 `P` 描述子分为 3 类：

1. `P_L`：`alpha_high = 0`
   selector 仅依赖 `lane`
2. `P_H`：`alpha_low = 0`
   selector 仅依赖 `slice`
3. `P_X`：其余情况
   selector 同时依赖 `slice` 与 `lane`

对 `CP` 描述子，分别观察控制位与目标位 selector 的类别：

1. `CP_LL`
   两个 selector 都是 low-only
2. `CP_HH`
   两个 selector 都是 high-only
3. `CP_HL`
   一个 low-only，一个 high-only

其中 `CP_HL` 包含 `HL/LH` 两种次序；进入 bucket 前要求在 host 侧做次序规范化，始终把 low-only selector 放在 `packed_sel0`，high-only selector 放在 `packed_sel1`。

这 6 个 bucket 构成当前 fast path 的完整集合：

- `P_L / P_H / P_X`
- `CP_LL / CP_HH / CP_HL`

若某个 `CP` 描述子不属于 `LL/HH/HL` 之一，即至少一端是 `cross` selector，则该项不进入 6-bucket IR，而是触发 fallback，详见[第8.4.6节：flush 与 fallback](#846-flush-与-fallback)。

#### 8.4.3. Host-side bucket accumulators 与 IR buffer

每个 diagonal window 在 host 侧维护两层结构：

1. **bucket accumulators**：6 个 typed `vector`，用于在扫描 basic block 时增量累计；
2. **IR buffer**：在 basic block 尾部把上述 6 个 bucket 线性编码为一块连续缓冲，用于后续一次 `memcpy_H2D` 发送。

其中 bucket accumulators 的抽象可写为：

```cpp
enum class diag_p_bucket_t : uint32_t
{
    P_L = 0,
    P_H = 1,
    P_X = 2,
    P_BUCKETS = 3,
};

enum class diag_cp_bucket_t : uint32_t
{
    CP_LL = 0,
    CP_HH = 1,
    CP_HL = 2,
    CP_BUCKETS = 3,
};

struct diag1_desc_t
{
    uint64_t packed_sel;
    float_t theta;
};

struct diag2_desc_t
{
    uint64_t packed_sel0;
    uint64_t packed_sel1;
    float_t theta;
};

struct diag_bucket_accum_t
{
    std::vector<diag1_desc_t> p_l;
    std::vector<diag1_desc_t> p_h;
    std::vector<diag1_desc_t> p_x;

    std::vector<diag2_desc_t> cp_ll;
    std::vector<diag2_desc_t> cp_hh;
    std::vector<diag2_desc_t> cp_hl;

    void clear();
    bool empty() const;
};

struct diag_chunk_counts_t
{
    uint32_t cnt_p_l;
    uint32_t cnt_p_h;
    uint32_t cnt_p_x;

    uint32_t cnt_cp_ll;
    uint32_t cnt_cp_hh;
    uint32_t cnt_cp_hl;
};

struct diag_chunk_cursor_t
{
    size_t idx_p_l;
    size_t idx_p_h;
    size_t idx_p_x;

    size_t idx_cp_ll;
    size_t idx_cp_hh;
    size_t idx_cp_hl;
};

struct diag_ir_buffer_t
{
    std::vector<uint64_t> words;
    void clear();
};
```

其中：

- `diag_bucket_accum_t` 是扫描期的数据结构；进入 basic block 时清空，扫描过程中只做 `push_back`；
- `diag_ir_buffer_t` 是编码期的数据结构；它不需要 header，只是一段连续 `uint64_t` 数组；
- bucket 内保持插入顺序即可，首版不要求对完全相同 descriptor 做 host-side 合并；
- 编码顺序固定为
  `P_L | P_H | P_X | CP_LL | CP_HH | CP_HL`；
- `P` 项按 2 个 word 编码：
  `[packed_sel, theta_bits]`；
- `CP` 项按 3 个 word 编码：
  `[packed_sel0, packed_sel1, theta_bits]`；
- 因此所有 bucket 共享同一个 word budget，而不是各自拥有独立上限。

这里 `theta_bits` 表示把 `float_t` 按位解释为一个 `uint64_t` word；由于当前 `float_t = double`，该编码无额外填充。若后续 `float_t` 改为 `float`，则仍保留一个完整 word 存储其 bit pattern。

#### 8.4.4. Device ABI 与工作区

本方案不再引入单独的 `diag_workspace_t`。device 侧 IR 直接使用一整块静态 constant memory：

```cpp
constexpr size_t kDiagIrWordCap = ...;
__constant__ uint64_t g_diag_ir_words[kDiagIrWordCap];
```

每次 flush 时的 ABI 约定为：

1. 扫描某个 basic block 时，只更新 `diag_bucket_accum_t`；
2. 到 basic block 尾部后，使用 `diag_chunk_cursor_t` 从 6 个 bucket 中按固定顺序切出一个 chunk；
3. 将该 chunk 编码到 `diag_ir_buffer_t.words`；
4. 执行一次
   `cudaMemcpyToSymbol(g_diag_ir_words, host_ir.words.data(), used_words * sizeof(uint64_t))`；
5. 将本 chunk 的 `diag_chunk_counts_t` 作为 kernel 参数按值传入；
6. 发射一次 block-local diagonal kernel；
7. 若 6 个 bucket 尚有剩余项，则继续编码下一个 chunk，直到该 basic block 完成。

对应的 kernel ABI 可写为：

```cpp
void diag_block_batch_kernel(
    val_t *block_ptr,
    size_t local_bits,
    diag_chunk_counts_t counts);
```

这里：

- `g_diag_ir_words` 是唯一的 device-side IR 存储；
- `counts` 不是 IR header，只是本次 launch 的 bucket item 数；
- bucket 的 word offset 由固定顺序和 `counts` 在 host/kernel 两侧各自用 prefix sum 计算；
- 由于 IR 只有一整块连续存储，因此所有 bucket 自然共享同一个 constant-memory budget，并且每个 chunk 只需要一次 `memcpy_H2D`。

#### 8.4.5. Kernel 计算模式

设当前本地 `block` 长度为 `2^{local_bits}`，仍按
$$
off = [slice][lane]
$$
组织遍历。一个 thread 的目标是对其负责的 `off` 累计总相位：
$$
\theta(off) =
\theta_{P_L}(lane)
\;+\;
\theta_{P_H}(slice)
\;+\;
\theta_{P_X}(off)
\;+\;
\theta_{CP_{LL}}(lane)
\;+\;
\theta_{CP_{HH}}(slice)
\;+\;
\theta_{CP_{HL}}(slice, lane)
$$
并最终执行
$$
sv[off] \gets sv[off]\cdot e^{i\theta(off)}
$$

给定 `diag_chunk_counts_t counts` 后，6 个 bucket 的 word offset 由固定顺序唯一确定：

$$
\begin{aligned}
off_{P_L}   &= 0 \\
off_{P_H}   &= off_{P_L}   + 2\cdot cnt_{P_L} \\
off_{P_X}   &= off_{P_H}   + 2\cdot cnt_{P_H} \\
off_{CP_{LL}} &= off_{P_X} + 2\cdot cnt_{P_X} \\
off_{CP_{HH}} &= off_{CP_{LL}} + 3\cdot cnt_{CP_{LL}} \\
off_{CP_{HL}} &= off_{CP_{HH}} + 3\cdot cnt_{CP_{HH}}
\end{aligned}
$$

kernel 在上述 offset 上解码 `g_diag_ir_words` 即可，不需要额外 header。

其中各项定义为：

1. `P_L`
   只依赖 `lane`，可在每个 thread 进入主循环前一次性累计

2. `P_H`
   只依赖 `slice`，可像当前 `p_batch` 的 high-only 路径一样，按 `slice tile` 预计算到 shared memory

3. `P_X`
   走通用 packed selector 判定，对完整 `off` 求值

4. `CP_LL`
   两个 selector 都只依赖 `lane`，因此也可在 thread 进入主循环前一次性累计

5. `CP_HH`
   两个 selector 都只依赖 `slice`，可与 `P_H` 同样按 `slice tile` 预计算到 shared memory

6. `CP_HL`
   一个 selector 只依赖 `lane`，一个只依赖 `slice`；因此每个 descriptor 的判定可写为
$$
S_{low}(lane)\land S_{high}(slice)
$$
   这一路径仍是可分离的，不应退化为对完整 `off` 做两次 generic selector 判定。

因此，kernel 的整体伪代码可写为：

```cpp
for each thread lane:
    theta_lane = sum(P_L on lane) + sum(CP_LL on lane)

    for each slice tile:
        sh_theta_slice[s] = sum(P_H on slice_s) + sum(CP_HH on slice_s)

        for each slice_s in tile:
            off = (slice_s << lane_bits) | lane

            theta = theta_lane
            theta += sh_theta_slice[s]
            theta += sum(P_X on off)
            theta += sum(CP_HL on (lane, slice_s))

            sv[off] *= exp(i * theta)
```

这一路径的关键点不是减少对角项数量，而是保证：

- 在单个 chunk 能容纳整个 basic block 时，只需一次 `memcpy_H2D` 与一次对角遍历；
- 当 basic block 过大时，按 chunk 分块执行，但 chunk 只是容量约束，不改变 basic block 的语义边界；
- `P` 与 `CP` 的常见结构化 selector 不再退化为逐门 kernel launch；
- `CP_HL` 明确作为一等公民处理，而不是落回 fully-generic 两 selector 逻辑。

#### 8.4.6. Flush 与 fallback

运行时扫描门序列时，6 个 bucket accumulators 的生命周期遵循以下规则：

```cpp
diag_bucket_accum.clear();

for (gate_t g : gates_exec)
{
    switch (g.type)
    {
    case Z:
    case Rz:
        lower_to_P_and_push(g);
        break;

    case CRz:
        push_P(control, -theta / 2);
        if (!try_push_CP_fastpath(control, target, theta))
        {
            flush_diag_block_in_chunks(block_ptr);
            apply_cp_scalar(block_ptr, control, target, theta);
        }
        break;

    case CP:
        if (!try_push_CP_fastpath(control, target, theta))
        {
            flush_diag_block_in_chunks(block_ptr);
            apply_cp_scalar(block_ptr, control, target, theta);
        }
        break;

    case X:
    case CX:
        update_affine_mapping_only();
        break;

    case H:
    case U3:
    case RESET:
        flush_diag_block_in_chunks(block_ptr);
        apply_non_diagonal_gate(...);
        break;
    }
}

flush_diag_block_in_chunks(block_ptr);
```

这里的语义要点是：

- `X/CX` 不 flush；它们只改变后续 `P/CP` 描述子的 selector；
- `H/U3/RESET` 是 window barrier，必须先 flush；
- `CP` 若无法落入 `LL/HH/HL`，则当前 6-bucket fast path 不负责覆盖它，执行层应先 flush 已累计 IR，再回退到现有 scalar `CP` kernel；
- `X-only block` 从未向任何 bucket 追加描述子，因此 `flush_diag_block_in_chunks()` 为 no-op，不会产生对角 kernel launch。

换言之，当前方案的目标不是“所有 diagonal gate 都强行塞进一个统一 kernel”，而是：

1. 保留 `P` 的 batching 思想；
2. 把 `CP` 纳入同一 diagonal window 的一次遍历中；
3. 用 6 个结构化 bucket 覆盖常见 fast path；
4. 对不满足 bucket 约束的 `CP` 保留显式 fallback，以保证实现路径简单且语义稳定。


## 9. 电路变换

本节定义 ZXH Python 前端采用的 **support-aware boundary scheduler**。它不是面向通用 simulator 的共享 IR 优化，而是 ZXH 自身的编译过程；其目标是在不改变电路语义的前提下，尽可能延后会 materialize effective support 的 `H/U3` 边界门，并尽可能把只包含 `X` 与对角相位的廉价成分保留在当前 cluster 内传播。

下文描述的是该编译优化的**完整目标方案**。工程实现可以按子集渐进落地，但中间状态、正规形与规则优先级应以本节为准。

### 9.1. 设计目标

该优化器围绕 ZXH 的 cost model 设计，目标如下：

1. 将单比特门按“最少需要多少个 `H` core”分类，从而区分不会扩张 support 的廉价部分与真正昂贵的 basis-change 边界；
2. 在扫描过程中尽可能传播 `X` 与对角相位，而不是过早把它们和 `H` core 一起固化为一般 `U3`；
3. 使用与执行层一致的 affine address mapping 语义判断某次固化是否会引入新的 effective support；
4. 不对共享 canonical IR 做 ZXH-specific 的 shape manipulation；共享 IR 只负责统一输入表示，ZXH-specific 的 support-aware 优化属于 ZXH 自身的 procedure。

### 9.2. 扫描流程与中间状态

优化器对门序列做一次从左到右的扫描，并维护一个当前 `cluster`。该 `cluster` 由如下中间状态组成：

1. `out`：已经固化并输出的门前缀；
2. `pending[q]`：第 `q` 个 qubit 上尚未固化的单比特变换，按[第9.3节：U3 门分类](#93-u3-门分类)中的正规形存储；
3. `agl`：与结构分析器共用的 affine address mapping 状态；它描述 `out` 前缀已经提交后的 `(A, b)` 与当前 effective support；
4. 若实现层需要加速判断，可额外维护 `active_mask / class_mask` 等 helper，但这些 bitmask 只是缓存，语义上并不独立于 `pending + agl`。

编译器的主流程可抽象为：

```text
init:
    out = []
    pending[q] = Empty for all q
    agl = identity, m = 0

for gate g in circuit:
    if g is 1q:
        absorb g into pending[q]
        renormalize pending[q]
        continue

    if g is 2q:
        try to propagate pending on its endpoints using the rule order of §9.4
        if propagation succeeds:
            update pending / out / agl and continue
        else:
            flush the required endpoints
            emit g into out
            update agl if g is X/CX-like
            continue

    if g is barrier / measure / reset:
        flush all pending
        emit g
        if g is reset: reset agl

finalize:
    flush all pending
```

这里的关键点是：

- 编译器不是“遇到 `U3/H` 就立即落盘”，而是优先把它保留在 `pending` 中，直到遇到真正无法继续传播的 barrier；
- `X/CX` 作用在地址映射上，因此它们与 `agl` 强相关；
- `Z/Rz/CP/CRz` 不改变 effective support，本质上属于“廉价 shell”，应尽量留在当前 cluster 内传播；
- 某个 `pending[q]` 是否会在 flush 时引入新的 support，并不由局部 barrier 决定，而是由当前 `agl` 对该 qubit 的表示能力决定。

### 9.3. U3 门分类

本节中的分类按“最少需要多少个 `H` core”定义，而不是按字面 gate name 定义。为此先引入单比特对角相位门：

$$
P(\theta)=\mathrm{diag}(1, e^{i\theta})
$$

忽略全局相位后，单比特门统一归一化为以下三类之一。

#### 9.3.1. `ZeroH`

`ZeroH` 表示不含任何 `H` core 的单比特变换，其正规形写为：

$$
G = X^x P(\theta),\quad x \in \{0,1\}
$$

它覆盖了：

- `I`；
- `X`；
- `Z/Rz/S/T` 等一切单比特对角门；
- `Y` 等可化为 `X` 乘对角相位的情形。

`ZeroH` 不会引入新的 effective support，因此它应优先在单比特扫描阶段被吸收与合并；一旦遇到双比特 barrier，则直接局部固化。

#### 9.3.2. `OneH`

`OneH` 表示最少只需要一个 `H` core 的单比特变换，其正规形写为：

$$
G = P(\theta_L)\, H\, P(\theta_R)
$$

这里两侧的 `P(\theta)` 是廉价 shell，而中间的 `H` 是昂贵 core。精确的 `H` 只是 `OneH` 的一个特例；很多 canonicalized `u(\theta,\phi,\lambda)` 虽然字面上是 `U3`，但仍会落入这一类。

`OneH` 的编译目标不是立刻把它固化为 `U3`，而是尽量延后其中 `H` core 的提交；两侧的廉价 shell 只在单比特扫描阶段继续吸收与合并，不在双比特边界上跨门传播。

#### 9.3.3. `TwoH`

`TwoH` 表示不属于前两类的情形，可规范地写为：

$$
G = X^x P(\theta_0)\, H\, P(\theta_1)\, H\, P(\theta_2)
$$

这类门需要两个 `H` core，属于当前前端中的 generic fallback。对 `TwoH`，优化器通常不会尝试复杂穿越，而是把它视为 barrier，并在必要时固化。

#### 9.3.4. 归一化与重分类

对任一 qubit，扫描到新的单比特门 `U_new` 时，先左乘吸收到当前 `pending[q]` 中：

$$
pending[q] \leftarrow U_{\text{new}} \cdot pending[q]
$$

随后重新做一次正规化与分类。分类优先级应为：

1. 先尝试 `ZeroH`；
2. 再尝试 `OneH`；
3. 其余归入 `TwoH`。

这种优先级直接对应 ZXH 的 cost model：`ZeroH` 最廉价，`OneH` 次之，`TwoH` 最昂贵。

### 9.4. 门穿越规则

本节给出 `pending` 在遇到 `CX` 时的传播规则。当前规范只保留**最小且直接服务于 ZXH cost model** 的规则集：

1. `ZeroH` 不跨越双比特门传播；
2. generic `OneH` / `TwoH` 不跨越双比特门传播；
3. 只有双边的 exact `H` 可以穿越 `CX`；
4. 其余情况一律先 flush，再发射原始 `CX`。

这里的关键设计取舍是：编译优化的目标不是对所有廉价 shell 做一般性的代数搬运，而是尽可能推迟真正昂贵的 `H` core 的 materialization。若为了让 `X/Z/P(\theta)` 穿越 `CX` 而额外生成新的 `X/Z/CP/P(\theta)`，虽然代数上等价，但会膨胀 primitive gate count，并且掩盖 `M` 与 `\rho_L` 的真实变化。因此，当前前端把 shell 视为**局部可吸收但不可跨 2q 传播**的成分。

#### 9.4.1. `CX` 边界上的局部 flush

当扫描器遇到一个 `CX_{c \to t}` 时，先分别检查控制位与目标位上的 `pending`：

- 若某端为 `ZeroH`，则直接在该端局部固化为 `X` 与 Z-type diagonal gate；
- 若某端为 generic `OneH`，则按[第9.5节：Flush 与 support 语义](#95-flush-与-support-语义)中的规则局部固化；
- 若某端为 `TwoH`，同样直接局部固化；
- 只有被识别为 exact `H` 的 `pending` 才允许继续停留在边界上等待下一步判断。

因此，`CX` 边界不会主动传播 shell。shell 只在单比特扫描阶段被吸收、合并，并在遇到 2q barrier 时就地提交。

#### 9.4.2. 双边 exact `H` 穿越 `CX`

若 `CX` 的控制位与目标位上都各有一个 exact `H`，则应用唯一保留的穿越规则：

$$
H_c H_t \cdot CX_{c \to t}
=
CX_{t \to c} \cdot H_c H_t
$$

这条规则只改变 `CX` 的方向，不引入新的双比特门，也不复制任何 shell。应用后：

1. `CX` 方向反转；
2. 两侧的 exact `H` 继续保留在各自的 `pending` 中；
3. 后续扫描继续尝试吸收同 qubit 上的单比特门，或在下一个 barrier 处将其固化。

当前规范不允许“单边 `H`”穿越 `CX`，也不允许“带 shell 的 `OneH`”先剥离 shell 后再尝试穿越。若不是双边 exact `H`，则直接转入 flush。

#### 9.4.3. 何时停止传播

遇到以下任一情况时，传播停止并转入 flush：

1. 任一端点上的 `pending` 不是 exact `H`；
2. 当前双比特门不属于已支持的穿越规则闭包；
3. `barrier / measure / reset` 显式要求切断当前 cluster。

### 9.5. Flush 与 support 语义

当传播失败或遇到显式 barrier 时，编译器需要把相关 `pending` 固化到 `out` 中。其固化语义如下：

- `ZeroH`：只固化为廉价门序列，即 `X` 与 Z-type diagonal gate；它们不改变 effective support，且不会尝试跨越双比特门继续传播；
- `OneH`：按
$$
P(\theta_L)\, H\, P(\theta_R)
$$
表示的单比特门。若该 `OneH` 恰为 exact `H`，则在固化时直接发射 `H`；否则将整个 `OneH` 作为单个 `U3` 门发射，而不是拆成 `Rz-H-Rz`。这样既保留了 exact `H` 的特殊语义，又避免 generic `U3` 在 barrier 处被无谓膨胀。只有 exact `H` 才允许在 2q 边界上暂缓固化，等待[第9.4.2节：双边 exact `H` 穿越 `CX`](#942-双边-exact-h-穿越-cx)；
- `TwoH`：按
$$
X^x P(\theta_0)\, H\, P(\theta_1)\, H\, P(\theta_2)
$$
的顺序固化；每个 `H` core 都要独立与 `agl` 交互。

这里的 support 判定与执行层保持一致。对一个待固化的 `H` core，设其作用 qubit 为 `q`，则：

- 若 $e_q$ 已在当前 `agl` 的列空间中，则该次固化只重用已有 support；
- 否则，该次固化会把一个新的维度并入当前 effective support。

因此，`flush` 不只是“输出一个门”的语法动作，而是 ZXH 编译器中唯一允许 materialize 新 support 的语义提交点。

### 9.6. 规则系统对 `X` 与 canonicalized `U3` 的意义

上述规则系统仍然把 `X` 归入 `ZeroH`，但其角色仅限于**单比特局部吸收与局部固化**，而不再承担跨 `CX` 传播的职责。原因是：

$$
X P(\theta) = P(-\theta) X
$$
$$
H X = Z H,\quad X H = H Z
$$

这意味着：

1. `X` 与对角相位天然属于同一个廉价 shell；
2. `X` 遇到 `H` 时可被吸收到 `OneH` 的两侧 shell 中，而不会额外增加 `H` core 的数量；
3. canonicalized `u(\theta,\phi,\lambda)` 中大量看似复杂的门，实际会落入 `ZeroH/OneH` 而不是 `TwoH`。

因此，本节的分类不是为了“给 `U3` 贴标签”，而是为了让 canonicalized 电路中被 support-unaware 流程打散出来的单比特结构重新暴露出其廉价 shell 与 `H` core，从而恢复 ZXH 可利用的地址运输与 delayed support materialization 机会。

## 10. 测量

本章描述测量的设计方案和接口语义。

对调用者而言，测量始终是在当前态上做独立重复采样；对实现而言，测量统一发生在实地址空间上，然后再通过地址映射 `(A, b)` 还原为虚地址结果。

当前规范将测量执行抽象为三级：

1. `worker` 级（`K` 级）：先确定每个 `worker` 的概率区间与样本个数；
2. `segment` 级（`J` 级）：在每个 `worker` 内对 `2^J` 个 `segment` 计算 `mass_J / cdf_J`，并把该 `worker` 的样本数分配到各段，得到 `cnt_J / cnt_cdf_J`；
3. `in-segment` 级（`I` 级）：仅对实际命中的 `segment` 重新构造段内 CDF，并解析本段负责的样本。

其中，`cuda / mpi_cuda` backend 以该三级方案为正式实现路径；`single / omp / mpi` backend 可以采用更简单的等价实现，但必须保持本章定义的 public API 语义一致。

### 10.0. 测量的 public API 语义

- `ZXH::measure(res_t *results, size_t cnt)` 与 `ZXH::Sampling(size_t shots)` 都是在当前状态上做独立重复采样，不执行物理意义上的塌缩；调用后 `sv / A / b` 保持不变。
- `results` 由调用者提供并预先按 `cnt` 分配。在分布式场景下，所有 `worker` 最终都持有一份完整且一致的 `results`。其顺序仅表示某次实现生成的样本顺序，不承载额外语义。
- 若库调用者通过 `ZXH::set_seed(...)` 指定测量随机种子，则该种子至少控制：
  1. `worker` 粒度的样本数划分；
  2. 每个 `worker` 内 `segment` 粒度的样本数划分；
  3. 各 `segment` 内本地随机流的生成。
- 其可复现性保证范围限定为：同一 `seed`、同一运行环境、同一 `backend`。本文不要求跨平台、跨标准库实现或跨 `backend` 的随机行为一致。若未显式设置 `seed`，则由实现层自行选择运行时随机种子。

### 10.1. 实地址空间上的测量

实地址空间上的 `sv` 向量定义了概率分布
$$
p(x_r)=|sv[x_r]|^2,\quad x_r\in\mathbb{F}_2^m
$$
测量过程只需要在该分布上采样得到实地址 `x_r`，再通过地址映射
$$
x_v = A x_r \oplus b
$$
将其转换到虚地址空间。顶层接口仍可写为：

```cpp
void ZXH::measure(res_t *results, size_t cnt)
{
    vector<raddr_t> real_results(cnt);
    sample_real_batch(sv, real_results.data(), cnt, measure_seed);
    for (size_t i = 0; i < cnt; i++)
        results[i] = A.mul(real_results[i]) ^ b;
}
```

其中，`sample_real_batch(...)` 的职责是在实地址空间上完成批量采样。其逻辑目标始终是：

1. 确定每个 `worker` 负责的概率区间；
2. 在该区间内完成 `segment` 粒度的样本数划分；
3. 仅对命中的 `segment` 独立解析实地址结果。

在分布式场景下，所有 `worker` 都持有长度为 `cnt` 的 `results` 缓冲；测量结束后，各 `worker` 上的 `results` 内容一致。

为在实现层承载上述语义，引入如下辅助接口：

```cpp
struct prob_scan_t
{
    float_t local_prob;
    float_t prob_prefix;
    float_t global_total;
};

struct measure_plan_t
{
    float_t global_total;
    float_t prob_prefix;
    size_t cnt_local;
    uint64_t stream_seed;
};

// 当前 worker 的 block 总概率
float_t sum_block_prob(const sv_t &sv);

// 已知当前 worker 的 local_prob 后，建立 worker 维度上的概率区间
prob_scan_t scan_block_prob(float_t local_prob);

// 结合 seed，把 cnt 个样本分配到各 worker
measure_plan_t make_measure_plan(size_t cnt, const prob_scan_t &prob_scan,
                                 bool use_seed, uint64_t seed);

// 汇总实地址结果；所有 worker 最终都得到完整 results
void allgather_results(const raddr_t *local_results, size_t local_count,
                       raddr_t *results, size_t cnt);
```

其中：

1. `sum_block_prob / scan_block_prob / make_measure_plan` 负责 `K` 级协同；
2. `allgather_results` 负责最终实地址结果汇总；
3. 对 `cuda / mpi_cuda` backend，推荐先完成 `J` 级的 `mass_J / mass_block` 构造，再把 `mass_block` 作为当前 `worker` 的 `local_prob` 交给 `K` 级协同，避免本地概率和被重复计算。

### 10.2. `segment` 级概率分解与样本数划分

对当前 `worker` 的本地 `block=[block_start, block_end)`，按[第6节：内存抽象](#6-内存抽象)中的定义，令单个 `segment` 长度为
$$
S = 2^I
$$
则该 `block` 被划分为 `2^J` 个逻辑 `segment`：
$$
seg_j = block\_start + j \cdot S,\quad j\in[0,2^J)
$$

对每个 `segment`，定义其有效长度
$$
len_j = \min\left(S,\ \max(0,\ block\_end-seg_j)\right)
$$
以及该段的概率质量
$$
mass_J[j] = \sum_{t=0}^{len_j-1} |sv[seg_j+t]|^2
$$
若某个 `segment` 完全落在未激活区间内，则其 `len_j = 0`，从而 `mass_J[j] = 0`。

进一步定义 `segment` 级 exclusive prefix：
$$
cdf_J[j] = \sum_{u=0}^{j-1} mass_J[u]
$$
以及当前 `worker` 的 block 总质量：
$$
mass_{block} = \sum_{j=0}^{2^J-1} mass_J[j]
$$

因此，对 `cuda / mpi_cuda` backend，测量的第一步不再是按元素流式扫描整个 `block`，而是先构造 `mass_J / cdf_J / mass_block`。其抽象可写为：

```cpp
// 计算当前 worker 的 segment 级概率质量与前缀和
// mass_J / cdf_J 的长度均为 2^J，cdf_J 为 exclusive prefix
void build_segment_mass(const sv_t &sv, float_t *mass_J, float_t *cdf_J,
                        float_t &mass_block);
```

实现约束如下：

1. `sum_block_prob(sv)` 与 `build_segment_mass(...)` 返回的 `mass_block` 必须语义一致；
2. `mass_J[j] = 0` 时，该段后续不得分配样本；
3. 实现层可以内部使用更高精度的累加类型，但对上层暴露的语义仍以 `float_t` 概率区间为准。

这里的 `mass_block` 同时也是当前 `worker` 的 `local_prob`。`K` 级协同基于它确定当前 `worker` 的 `cnt_local` 后，还需要把该样本数继续分配到本地 `2^J` 个 `segment`。定义：

$$
cnt_J[j] = \text{第 } j \text{ 个 segment 负责的样本数}
$$
$$
cnt\_cdf_J[j] = \sum_{u=0}^{j-1} cnt_J[u]
$$

其中，`cnt_cdf_J[j]` 表示该 `segment` 在本地 `results` 缓冲中的起始写入位置。

语义约束如下：

1. `cnt_J[j] >= 0`；
2. 若 `mass_J[j] = 0`，则 `cnt_J[j] = 0`；
3. 总和约束
$$
\sum_{j=0}^{2^J-1} cnt_J[j] = cnt_{local}
$$
4. `cnt_cdf_J` 为 exclusive prefix，因此第 `j` 个 `segment` 的结果写入区间为
$$
[cnt\_cdf_J[j],\ cnt\_cdf_J[j] + cnt_J[j])
$$

从概率语义上看，这一步等价于把 `cnt_local` 个样本落在当前 `worker` 的概率区间
$$
[prob\_prefix,\ prob\_prefix + mass_{block})
$$
内，然后按 `cdf_J` 定义的 `segment` 边界完成分桶。实现层可以采用两种等价方式：

1. 显式生成 block-level 的有序阈值流，并按 `cdf_J` 做 bucket；
2. 直接按
$$
\rho_j = \frac{mass_J[j]}{mass_{block}}
$$
对 `cnt_local` 做等价的 `segment`-level multinomial 划分。

无论采用哪一种实现，产生的 `cnt_J / cnt_cdf_J` 都承载相同的上层语义。对 `cuda / mpi_cuda` backend，推荐以 `mass_J` 为输入直接得到 `cnt_J / cnt_cdf_J`，避免回到整个 `block` 的串行流式扫描。

对应内部 helper 可抽象为：

```cpp
// 输入当前 worker 的 cnt_local 与 segment 质量分布
// 输出各 segment 的样本个数与结果写入前缀
void distribute_segment_counts(size_t cnt_local, float_t prob_prefix,
                               const float_t *mass_J, const float_t *cdf_J,
                               size_t seg_count, uint64_t stream_seed,
                               size_t *cnt_J, size_t *cnt_cdf_J);
```

### 10.3. `segment` 内并行采样

一旦 `cnt_J / cnt_cdf_J` 确定，每个 `segment` 都可以独立完成本地采样。对第 `j` 个 `segment`：

1. 其地址范围为 `[seg_j, seg_j + len_j)`；
2. 其概率区间为
$$
[prob\_prefix + cdf_J[j],\ prob\_prefix + cdf_J[j] + mass_J[j])
$$
3. 其结果写入区间为
$$
[cnt\_cdf_J[j],\ cnt\_cdf_J[j] + cnt_J[j])
$$

对该 `segment` 内部，再定义段内累计分布
$$
cdf_{seg}(t) = \sum_{u=0}^{t} |sv[seg_j+u]|^2,\quad t\in[0,len_j)
$$
随后在该段自己的概率区间内生成 `cnt_J[j]` 个样本，并在 `cdf_seg` 上解析得到对应的实地址。由于结果顺序不承载额外语义，允许实现采用 `segment-major` 写出。对 `cuda / mpi_cuda` backend，推荐只对满足 `cnt_J[j] > 0` 的 `segment` 重新构造 `cdf_seg`，而不是为所有 `segment` 长期缓存 `2^I` 级别的段内 CDF。

对应内部 helper 可抽象为：

```cpp
// 并行处理所有 segment 的本地采样，并按 cnt_cdf_J 指定的位置写入 local_results
void sample_segments_local(const sv_t &sv, float_t prob_prefix,
                           const float_t *mass_J, const float_t *cdf_J,
                           const size_t *cnt_J, const size_t *cnt_cdf_J,
                           uint64_t stream_seed, raddr_t *local_results);
```

这里需要强调三点：

1. `results` 的顺序不承载额外语义，因此允许实现采用 “segment-major” 的写出顺序；
2. 第 `j` 个 `segment` 的本地随机流只要由 `(stream_seed, worker_id, segment_id)` 等确定性信息导出即可；规范不要求它必须还原为单一全局随机流的字节级实现细节，只要求分布语义与同 backend 下的可复现性成立。
3. `I` 级采样的正式目标是“只为命中的 segment 支付段内 CDF 构造开销”，而不是为全部 `2^J` 个 `segment` 预留 `2^I` 级长期缓存。

### 10.4. 结果汇总与缓存生命周期

三级方案下，`cuda / mpi_cuda` backend 需要一组随 `sv` 布局稳定存在的测量工作区。对固定的 `(I, J, K)`，以下数组长度都仅由 `J` 决定：

1. `mass_J[0..2^J)`；
2. `cdf_J[0..2^J)`；
3. `cnt_J[0..2^J)`；
4. `cnt_cdf_J[0..2^J)`。

因此，推荐把这组数组作为 `sv` 关联的内部测量 cache 持有；当 `sv.resize()` 导致 `I/J/K` 变化时再一并重配。抽象可写为：

```cpp
class measure_cache_t
{
  public:
    void configure_for_sv(size_t I, size_t J);
    void ensure_result_capacity(size_t cnt);

    float_t *mass_J();
    float_t *cdf_J();
    size_t *cnt_J();
    size_t *cnt_cdf_J();
    raddr_t *local_results();
};
```

其中 `results` 缓冲的容量由 `shots` 决定，不宜只由 `J` 推导。因此建议：

1. `measure_cache_t` 对结果缓冲采用 grow-only capacity 管理；
2. 初始容量可取一个实现默认值（例如 `4096`）；
3. 当 `measure(cnt)` 满足 `cnt > result_capacity` 时执行重分配。

对 `cuda / mpi_cuda` backend，推荐把 `mass_J / cdf_J / cnt_J / cnt_cdf_J / local_results` 放在 `worker` 内存上并与 `sv` 同生命周期管理；`reset()` 不触发重配，`resize()` 在 `I/J/K` 变化时统一重配。这样可以避免每次 `measure()` 的临时申请与释放。

对于最终结果汇总：

- `cuda` backend 不存在跨 `worker` 汇总，`local_results` 即最终 `real_results`；
- `mpi_cuda` backend 中，`local_count = cnt_local` 一般是随 rank 变化的可变长度，因此“等长 collective”不能直接套用：
  - 例如 `ncclAllGather` 这类 collective 要求所有 rank 的发送块长度一致；
  - 若实现希望继续使用此类 collective，则必须先把本地结果 pad 到统一长度。

因此，对 `mpi_cuda` backend，默认推荐的结果汇总语义为：

1. 先在 host 侧交换各 rank 的 `local_count`，得到 `recv_counts / displs`；
2. 再在 worker memory 上执行等价于 variable-length gather 的汇总；
3. 最后把完整 `real_results[0..cnt)` 广播到所有 rank。

在实现层，这一步既可以继续沿用 host memory 的 `gatherv + broadcast`，也可以在 `mpi_cuda` backend 上改为 “host 侧交换大小 + NCCL `send/recv` 组播 gather + NCCL broadcast” 的 device-side 路径；但这些都属于 backend 优化策略，不改变本章规定的语义边界。

### 10.5. 总体流程

按三级方案，测量的整体伪代码可写为：

```cpp
void sample_real_batch(const sv_t &sv, raddr_t *results, size_t cnt,
                       bool use_seed, uint64_t seed)
{
    measure_cache.configure_for_sv(sv.I, sv.J);

    float_t *mass_J = measure_cache.mass_J();
    float_t *cdf_J = measure_cache.cdf_J();
    size_t *cnt_J = measure_cache.cnt_J();
    size_t *cnt_cdf_J = measure_cache.cnt_cdf_J();

    float_t mass_block = 0.0;
    build_segment_mass(sv, mass_J, cdf_J, mass_block);

    prob_scan_t prob_scan = scan_block_prob(mass_block);
    measure_plan_t plan = make_measure_plan(cnt, prob_scan, use_seed, seed);

    measure_cache.ensure_result_capacity(plan.cnt_local);
    raddr_t *local_results = measure_cache.local_results();

    distribute_segment_counts(plan.cnt_local, plan.prob_prefix,
                              mass_J, cdf_J, raddr_e_i(sv.J), plan.stream_seed,
                              cnt_J, cnt_cdf_J);
    sample_segments_local(sv, plan.prob_prefix, mass_J, cdf_J,
                          cnt_J, cnt_cdf_J, plan.stream_seed, local_results);

    allgather_results(local_results, plan.cnt_local, results, cnt);
}
```

上述伪代码中：

1. `build_segment_mass` 先完成 `J` 级的质量统计，并同时产出供 `K` 级使用的 `mass_block`；
2. `scan_block_prob / make_measure_plan / allgather_results` 负责 `worker` 级协同；
3. `distribute_segment_counts / sample_segments_local` 负责 `worker` 内的 `J + I` 两级测量；
4. `measure_cache_t` 负责承载长度由 `J` 决定的稳定工作区，以及按 `shots` 扩容的结果缓冲；
5. `cuda / mpi_cuda` backend 的主要并行性来自：
   - 所有 `segment` 质量的并行构造；
   - 所有 `segment` 样本个数的并行处理；
   - 所有 `segment` 本地采样的并行执行。
