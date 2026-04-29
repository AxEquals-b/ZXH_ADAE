# Prepare Stage

The prepare stage materializes all reproducible inputs needed by later ADAE runs.

Subprocesses:

- `scripts/install_python_frontends.py`
  - installs or refreshes the baseline Python frontends: `cudaq`, `mqt.ddsim`, `qblaze`
  - writes human-readable install logs and version snapshots under `benchmarks/ADAE/results/prepare/env/`
- `scripts/build_zxh_stages.py`
  - builds the staged ZXH Python package used by both prepare-time `analyze` and later run scripts
  - required backend: `cuda`
  - optional backend: `mpi_cuda`
  - writes build summaries under `benchmarks/ADAE/results/prepare/builds/`
- `generators/generate_all.py`
  - runs the five-pass workload-generation and structure-analysis workflow
  - materializes the fixed 29-family representative set at a configurable main size cap and also emits a smaller dev manifest for quick regression checks
  - pass 4 always loads `zxhsim.analyzer` from the staged `cuda` package rather than from the system Python environment
  - writes workflow manifests under `benchmarks/ADAE/results/prepare/workflow/`
  - writes generated QASM workloads under `benchmarks/ADAE/results/prepare/workloads/`
- `scripts/prepare_all.py`
  - optional umbrella entrypoint that executes the three prepare subprocesses above in order
  - writes a pipeline summary under `benchmarks/ADAE/results/prepare/pipelines/`

Expected outputs:

- a frontend install snapshot
- a successful staged `cuda` build
- a complete representative manifest and analysis summary
