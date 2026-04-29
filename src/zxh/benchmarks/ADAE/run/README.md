# Run Stage

The run stage executes prepared workloads against the selected simulator backends.

Subprocesses:

- `scripts/run_all.py`
  - current umbrella entrypoint for the run stage
  - runs the prepared cases on the selected backends with family-level subprocess isolation
  - can target either the default representative manifest or an explicit dev manifest via `--manifest`
  - consumes canonical QASM3 directly in strict mode
  - all backends consume the same shared canonical IR, which has already been lowered to the fixed gate set and optimized at prepare time
  - `cudaq` and `zxh-cuda` perform backend-local syntax/API translation from the shared canonical circuit
  - qiskit-backend baselines such as `ddsim` and `qblaze` consume the shared canonical circuit directly through their public `backend.run(...)` interface
  - writes raw timing data and compact summaries under `benchmarks/ADAE/results/run/representative_cuda/`

Expected outputs:

- per-repeat raw timing records
- per-case backend summaries for both `cudaq` and `zxh-cuda`
- repeat-level relative-standard-deviation warnings for the reported end-to-end metric when the measured repeat distribution exceeds 10%

Timing policy:

- The default run-stage measurements keep per-circuit work in scope. This includes canonical-QASM loading, public circuit construction/build calls, and public execution/sample calls exposed by each backend runner.
- The reported end-to-end metric is defined as `execute_ms + sample_ms`. It is the only composite performance metric used for comparison and stability checks.
- Explicit per-circuit compile/build calls remain recorded separately as `kernel_build_ms` for inspection, but they are not folded into the reported end-to-end metric.
- For `ddsim` and `qblaze`, no separate build boundary is exposed, so `kernel_build_ms` is recorded as zero and backend-internal ingest remains inside `execute_ms`.
- One-time environment setup may be reused when the backend documents a public interface for it. In practice, this includes items such as `cudaq.set_target(...)`, DDSIM provider/backend creation, qblaze backend creation, and staged ZXH module loading.
- Repeated-execution reuse is permitted only through documented public interfaces described by the backend's official README and public API. ADAE does not use private hooks, undocumented caches, or reflection-only discoveries to keep simulator state alive across repeats.
- If a backend exposes no documented reusable execution-state interface, ADAE measures repeated runs through its standard public call path for every repeat.
- Any future warm-runtime benchmark mode must apply this same rule uniformly across all compared backends.
- Current implementation status:
  - reuses documented environment-level handles such as module loading, `cudaq.set_target(...)`, and backend/provider objects where applicable
  - does not yet enable a separate warm-runtime mode that keeps documented execution-state objects alive across repeats
  - default run parameters are `warmup=4`, `repeats=8`
  - each per-case summary reports repeat-level relative standard deviation only for `end_to_end_ms`
  - the runner emits a warning when `end_to_end_ms` exceeds `10%` relative standard deviation across repeats

Budget policy:

- `--timeout-s` is a total child-process wall-clock limit for one family/backend subprocess.
- `--time-budget-s` is a single-run budget.
- backend child runners enforce `per-run timeout = time_budget_s * 1.5` on each warmup/repeat iteration and stop the current family/backend once one iteration exceeds that threshold.
- for sweep-style manifests with family names of the form `name_nXX`, `run_all.py` now skips larger `N` for the same backend once a smaller point has already timed out.
- default `time budget` is `100 s`
- `--timeout-s` is now only an explicit hard kill for the whole child subprocess; it is no longer derived from `--time-budget-s`.
- `--host-mem-budget-gib` applies a host-side memory cap to the isolated child process via `RLIMIT_AS`.
- `--gpu-mem-budget-gib` is a runner-side external GPU memory limit for CUDA backends.
- default `memory limit` is `40 GiB`
- `cudaq` and `zxh-cuda` are monitored externally by the launcher through `nvidia-smi`, matched against the isolated child PID.
- if the observed GPU memory exceeds the configured limit, the launcher kills the child process and marks the case as `gpu_mem_limit_exceeded`.

ZXH ablations:

- `run_backend_zxh_cuda.py` accepts `--disable-x` to replace affine `X/CX` absorption with explicit local `X/CX` kernels.
- `run_backend_zxh_cuda.py` accepts `--eager-expand-all` to expand the execution state to `N` bits before replay.
- `run_all.py` forwards these through `--zxh-disable-x` and `--zxh-eager-expand-all`.
