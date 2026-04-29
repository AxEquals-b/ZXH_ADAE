# ADAE Benchmark Environment

This directory contains the paper-facing benchmark environment used for the ADAE workflow.

The workflow is organized into three clean stages:

1. `prepare/`
   - installs baseline Python frontends
   - builds the staged ZXH Python package
   - generates, filters, canonicalizes, and analyzes benchmark workloads
   - expected outputs:
     - `benchmarks/ADAE/results/prepare/env/`: frontend install logs and version snapshots
     - `benchmarks/ADAE/results/prepare/builds/`: staged ZXH build summaries
     - `benchmarks/ADAE/results/prepare/workflow/`: five-pass workflow manifests and reports
     - `benchmarks/ADAE/results/prepare/workloads/`: raw and canonical QASM assets
2. `run/`
   - runs prepared workloads against the selected simulator backends
   - consumes canonical QASM3 directly; the shared canonical IR is already lowered to the fixed gate set and optimized during `prepare/`
   - `cudaq` and `zxh-cuda` apply backend-local syntax/API translation, while `ddsim` and `qblaze` consume the canonical circuit through their standard public `run(...)` path
   - expected outputs:
     - `benchmarks/ADAE/results/run/representative_cuda/`: raw timing records and per-case summaries
3. `aggregate/`
   - reduces run-stage outputs into paper-facing tables
   - expected outputs:
     - `benchmarks/ADAE/results/aggregate/representative_cuda/`: paired speedup summaries
     - `benchmarks/ADAE/figures/`: later figure exports derived from aggregate outputs

Supporting directories:

- `results/`: phase-partitioned artifacts produced by the three stages above.
- `figures/`: exported figures. This directory is reserved for aggregate-stage outputs.

Typical usage:

```bash
python benchmarks/ADAE/prepare/scripts/prepare_all.py --opt-level 2 --representative-max-n 30 --dev-max-n 24
python benchmarks/ADAE/run/scripts/run_all.py
python benchmarks/ADAE/aggregate/scripts/aggregate_all.py --run-id <run_id>
```

Timing methodology:

- ADAE treats circuit construction, public compilation/build calls, and public execution/sample calls as benchmarked overheads. These are part of the user-visible execution path of each backend and are therefore kept in-scope unless a metric explicitly states otherwise.
- ADAE defines the reported end-to-end metric as `execute_ms + sample_ms`.
- When a backend exposes a documented public compile boundary, ADAE records that cost separately as `kernel_build_ms` and excludes it from the reported end-to-end metric. Backends without such a boundary keep their internal ingest/lowering cost inside `execute_ms`.
- ADAE does not count one-time process-global setup costs as per-repeat execution time when the backend exposes a documented public runtime handle for them. Examples include target selection, backend/provider construction, and similar environment-level setup.
- Reuse across repeated executions is allowed only when the reuse mechanism is part of the backend's documented public interface, as described by the official README and public API. Undocumented internals, reflection-only discoveries, and private hooks are out of scope.
- If a backend does not provide a documented reusable execution-state interface, ADAE falls back to its standard public execution path for every repeat.
- When a warm-runtime experiment is introduced, it must follow the same rule for every backend: public, documented reuse may be used; undocumented reuse may not.
- The default run-stage policy uses `warmup=4` and `repeats=8`.
- The run-stage summary records repeat-level relative standard deviation only for the reported end-to-end metric and emits a warning when that value exceeds `10%`.
- The run-stage launcher distinguishes a total subprocess wall-clock limit (`--timeout-s`) from a per-run budget (`--time-budget-s`). When the latter is used, ADAE converts it to a child timeout by multiplying with `warmup + repeats`. The default per-run time budget is `100 s`.
- Optional budget guards are available at launch time:
  - host memory via `--host-mem-budget-gib`, enforced on the isolated child process
  - runner-side external GPU memory monitoring via `--gpu-mem-budget-gib`, with a default limit of `40 GiB` for CUDA backends

Stage-specific entrypoints:

- prepare:
  - `python benchmarks/ADAE/prepare/scripts/install_python_frontends.py`
  - `python benchmarks/ADAE/prepare/scripts/build_zxh_stages.py --backend cuda`
  - `python benchmarks/ADAE/prepare/generators/generate_all.py --zxh-backend cuda`
- run:
  - `python benchmarks/ADAE/run/scripts/run_all.py`
- aggregate:
  - `python benchmarks/ADAE/aggregate/scripts/aggregate_representative_cuda.py --run-id <run_id>`
