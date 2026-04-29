# ADAE Prepare Generator Workflow

This directory contains the reproducible workload-generation pipeline used by the ADAE prepare stage.

By default, all generated artifacts are written under `benchmarks/ADAE/results/prepare/`.

## Environment

The workflow assumes:

- Python 3.10+
- Qiskit 2.x
- A local `mqt-bench` source checkout at `workspace/external/mqt-bench/src`

Required Python packages:

- `qiskit`
- `qiskit-qasm3-import`
- `openqasm3`
- `networkx`

Install the missing QASM 3 dependency with:

```bash
python -m pip install qiskit-qasm3-import
```

`openqasm3` is installed automatically as a dependency of `qiskit-qasm3-import`.

## Prepare Prerequisite

Before running this workflow:

```bash
python benchmarks/ADAE/prepare/scripts/install_python_frontends.py
python benchmarks/ADAE/prepare/scripts/build_zxh_stages.py --backend cuda
```

Pass 4 does not use a system-installed `zxhsim`. It loads `zxhsim.analyzer` from the staged `cuda` package prepared by `build_zxh_stages.py`.

## Workflow

The entry point is:

```bash
python benchmarks/ADAE/prepare/generators/generate_all.py --zxh-backend cuda
```

This runs five passes.

### Pass 1: Scan

Pass 1 enumerates all MQT Bench workload families, keeps the families that have at least one valid instance in the target qubit range, selects the largest valid instance in that range, and materializes one representative case per family as an OpenQASM 3 file.

Outputs:

- `benchmarks/ADAE/results/prepare/workflow/01_pass1_scan/scan.json`
- `benchmarks/ADAE/results/prepare/workflow/01_pass1_scan/scan.csv`
- `benchmarks/ADAE/results/prepare/workflow/01_pass1_scan/scan.md`
- `benchmarks/ADAE/results/prepare/workflow/01_pass1_scan/cases/*.qasm3`

### Pass 2: Filter

Pass 2 scans the OpenQASM 3 files produced by Pass 1, parses each case once as a QASM 3 AST, estimates executable gate counts, applies the static-circuit filter, and prepares the retained workloads for the next structure-analysis stage.

This is intentionally a prefilter. It is not tied to the ZXH gate set, and it does not try to be a compilation-accurate cost model.

For the retained workloads, Pass 2 records:

- `N`
- `depth`
- `case_qasm3_path`

For excluded workloads, only partial metadata is kept.

Outputs:

- `benchmarks/ADAE/results/prepare/workflow/02_pass2_filter/filter.json`
- `benchmarks/ADAE/results/prepare/workflow/02_pass2_filter/filter.csv`
- `benchmarks/ADAE/results/prepare/workflow/02_pass2_filter/filter.md`
- `benchmarks/ADAE/results/prepare/workflow/02_pass2_filter/selected_manifest.json`
- `benchmarks/ADAE/results/prepare/workflow/02_pass2_filter/selected_manifest.csv`

### Pass 3: Canonicalize

Pass 3 copies the retained representative circuits into a raw benchmark directory and also rewrites them into an experiment-side canonical OpenQASM 3 form.

The canonical gate set is:

- `x`, `cx`
- `rz`, `cp`
- `h`, `u`
- `measure`, `reset`, `barrier`

This canonical pass is an experiment component rather than a ZXH library component. ZXH keeps its own lowering path; the two may overlap, but they are intentionally separated in responsibility.

This canonical pass is used for three purposes:

- shared structural analysis,
- apples-to-apples baseline input preparation,
- basis-constrained frontend normalization such as recursive decomposition and generic backend-independent optimization.

Outputs:

- `benchmarks/ADAE/results/prepare/workflow/03_pass3_canonicalize/canonicalize.json`
- `benchmarks/ADAE/results/prepare/workflow/03_pass3_canonicalize/canonicalize.csv`
- `benchmarks/ADAE/results/prepare/workflow/03_pass3_canonicalize/canonicalize.md`
- `benchmarks/ADAE/results/prepare/workflow/03_pass3_canonicalize/canonical_manifest.json`
- `benchmarks/ADAE/results/prepare/workflow/03_pass3_canonicalize/canonical_manifest.csv`
- `benchmarks/ADAE/results/prepare/workloads/mqt_raw/*.qasm3`
- `benchmarks/ADAE/results/prepare/workloads/mqt_canonical/*.qasm3`

### Pass 4: Analyze

Pass 4 replays the retained canonical circuits through `zxhsim.analyzer`, which is loaded from the staged `cuda` package built during prepare. It uses the same Python lowering path as the frontend, but with an analyzer backend instead of the runtime simulator. This analyzer reproduces affine address-map updates and lazy support expansion, then reports structural quantities such as:

- compiled gate counts by class,
- final effective support `M`,
- transport ratio `rho_X`,
- support ratio `rho_M`,
- lazy-expansion ratio `rho_L`.

Outputs:

- `benchmarks/ADAE/results/prepare/workflow/04_pass4_analyze/analysis.json`
- `benchmarks/ADAE/results/prepare/workflow/04_pass4_analyze/analysis.csv`
- `benchmarks/ADAE/results/prepare/workflow/04_pass4_analyze/analysis.md`
- `benchmarks/ADAE/results/prepare/workflow/04_pass4_analyze/representative_candidates.json`
- `benchmarks/ADAE/results/prepare/workflow/04_pass4_analyze/representative_candidates.csv`

### Pass 5: Sweep Families

Pass 5 is intentionally no longer generic. It first validates that the representative selection from Pass 4 matches the hard-coded paper-facing expectation:

- bounded-support: `bv`
- transport-heavy: `vqe_two_local`
- lazy-expansion: `qft`
- adverse full-support: `qwalk`

If this boundary check fails, the pass aborts immediately instead of silently generating a different experiment set.

After validation, the pass materializes sweep workloads for these four families across the same `20..32` range. All families use their benchmark-default parameterization.

Outputs:

- `benchmarks/ADAE/results/prepare/workflow/05_pass5_sweep/sweep.json`
- `benchmarks/ADAE/results/prepare/workflow/05_pass5_sweep/sweep.csv`
- `benchmarks/ADAE/results/prepare/workflow/05_pass5_sweep/sweep.md`
- `benchmarks/ADAE/results/prepare/workflow/05_pass5_sweep/sweep_manifest.json`
- `benchmarks/ADAE/results/prepare/workflow/05_pass5_sweep/sweep_manifest.csv`
- `benchmarks/ADAE/results/prepare/workloads/mqt_sweep_raw/*.qasm3`
- `benchmarks/ADAE/results/prepare/workloads/mqt_sweep_canonical/*.qasm3`

## Important Design Choice

Representative cases are exchanged between passes as OpenQASM 3 files, not as Qiskit-internal binary snapshots. This keeps the workflow inspectable, portable, and easier to reproduce across environments.

For benchmark families whose `create_circuit(...)` signature exposes an explicit `seed` parameter, the workflow passes `seed=10` explicitly. This matches the upstream default behavior whenever the benchmark already defaults to `10`, and among the retained workload families it only changes `graphstate`, whose upstream default is otherwise non-deterministic. This seed-handling detail is kept at the workflow level and is not intended as a paper-level experimental variable.

Gate counting and static-circuit filtering in Pass 2 are based on recursive traversal of the QASM 3 program. Therefore:

- it is suitable for benchmark prefiltering,
- it is reproducible from the generated `.qasm3` files alone,
- it should not be interpreted as the final compiled gate count for the simulator backend.

The structural analysis in Pass 4 is different: it is based on the ZXH frontend's actual lowering path, so the reported `rho_X`, `rho_M`, and `rho_L` are derived from the compiled ZXH gate stream rather than from raw QASM syntax.

## Common Options

```bash
python benchmarks/ADAE/prepare/generators/generate_all.py \
  --n-min 20 \
  --n-max 32 \
  --opt-level 2 \
  --gate-count-budget 1000000 \
  --count-max-definition-depth 32 \
  --zxh-backend cuda
```

Useful flags:

- `--no-size-cache`: probe valid sizes live instead of using the cached `20..32` family-size table.
- `--output-root <path>`: write workflow outputs to a different root directory.
- `--gate-count-budget <int>`: change the Pass 2 prefilter threshold.
- `--count-max-definition-depth <int>`: bound recursive traversal when estimating counts from QASM 3 definitions.
- `--skip-sweep`: skip Pass 5 when only the representative-selection pipeline is needed.
