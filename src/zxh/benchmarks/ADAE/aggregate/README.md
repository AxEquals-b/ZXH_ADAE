# Aggregate Stage

The aggregate stage reduces run-stage outputs into paper-facing tables and figure-ready summaries.

Subprocesses:

- `scripts/aggregate_representative_cuda.py`
  - reads a run-stage `summary.json`
  - pairs `cudaq` and `zxh-cuda` rows case by case
  - emits speedup tables under `benchmarks/ADAE/results/aggregate/representative_cuda/`
- `scripts/aggregate_all.py`
  - current umbrella entrypoint for the aggregate stage

Expected outputs:

- backend-only speedup tables
- end-to-end speedup tables
- markdown summaries suitable for later plotting and figure generation
