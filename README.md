# ZXH-Sim ADAE Artifact

This repository contains the artifact harness for ZXH-Sim. It builds a Docker image from the NVIDIA cuQuantum Appliance base image, embeds `src/` as the software overlay, runs the MQT Bench based experiments, and regenerates the paper figures from CSV outputs.

## Artifact Contents

- `src/zxh/`: vendored ZXH-Sim source snapshot.
- `src/scripts/`: benchmark runners, backend registry, circuit generator, and plotting scripts.
- `src/suites/`: CSV definitions for the near-30 suite and the four sweep families.
- `prepare.sh`: builds the ZXH Python overlay and the Docker image.
- `run_all.sh`: runs all experiments needed by the artifact figures and CSV tables.
- `aggregate.sh`: regenerates the figures and prints ZXH/cuQuantum geometric speedups.
- `output/`: runtime output directory mounted into the container at `/home/cuquantum/output`.

## Hardware and Software Requirements

- Linux host with Docker and NVIDIA Container Toolkit.
- NVIDIA GPU with enough memory for near-30 dense state-vector simulation. The reference runs were collected on NVIDIA A100 PCIe 40GB GPUs.
- Access to `nvcr.io/nvidia/cuquantum-appliance:25.11-x86_64`.
- Network access may be required by Docker to pull the base image. The artifact itself uses the vendored `src/pydeps` overlay and the vendored `src/zxh` source snapshot.

We do not redistribute a pre-built Docker image for this artifact because the NVIDIA cuQuantum Appliance base image is distributed through NVIDIA NGC under NVIDIA's container license terms. Instead, this repository provides only the source overlay and a `Dockerfile` that layers `src/` on top of the cuQuantum Appliance image. Reproducers must obtain access to the base image through their own NVIDIA NGC account and accept the applicable NVIDIA terms before building the artifact image.

To obtain the cuQuantum Appliance base image, create or use an NVIDIA NGC account, sign in to the NGC catalog, open the cuQuantum Appliance container page, accept any required terms, and pull the image used by this artifact:

```bash
docker login nvcr.io
docker pull nvcr.io/nvidia/cuquantum-appliance:25.11-x86_64
```

The official NGC catalog entry is https://catalog.ngc.nvidia.com/orgs/nvidia/containers/cuquantum-appliance, and NVIDIA's cuQuantum Appliance documentation is https://docs.nvidia.com/cuda/cuquantum/26.01.0/appliance/overview.html. The documentation also lists the host prerequisites and shows the generic pull/run pattern for `nvcr.io/nvidia/cuquantum-appliance:25.11-${march}`.

## Quick Start

```bash
./prepare.sh
./run_all.sh
./aggregate.sh
```

The default Docker image tag is `zxh-adae:latest`. Override it with:

```bash
ADAE_IMAGE=my-zxh-artifact:latest ./prepare.sh
ADAE_IMAGE=my-zxh-artifact:latest ./run_all.sh
ADAE_IMAGE=my-zxh-artifact:latest ./aggregate.sh
```

## Step 1: Prepare the Image

```bash
./prepare.sh
```

This script first rebuilds the ZXH-Sim Python overlay into `src/pydeps` by invoking `install_zxh.sh`. It then builds a Docker image using `Dockerfile`. The Docker image copies `src/` into `/home/cuquantum/src`; at runtime only `output/` is mounted, so the source overlay used by a run is the one embedded in the prepared image.

The scripts automatically relax permissions on the bind-mounted `src/pydeps` and `output/` directories so that the cuQuantum Appliance container can write to them even if the release archive was extracted by a different host UID.

Useful environment variables:

- `CUQUANTUM_IMAGE`: base image, default `nvcr.io/nvidia/cuquantum-appliance:25.11-x86_64`.
- `ADAE_IMAGE`: artifact image tag, default `zxh-adae:latest`.

## Step 2: Run Experiments

```bash
./run_all.sh
```

The script runs:

- `near30` for `cuQuantum`, `ddsim`, `qblaze`, and `zxh`.
- Four sweeps, `bv`, `qft`, `qwalk`, and `vqe_two_local`, for the same four backends.
- The ZXH-Sim diagonal `p/cp` batch microbenchmark.
- The ZXH-Sim ablations `zxh-nox` and `zxh-exp` on the four sweep families.

By default, all experiment groups write to the run id `latest`. Re-running the artifact without changing run ids overwrites the previous CSV files under `output/results/<backend>/latest/`.

Override the run ids if you want to keep multiple result sets side by side.

Outputs are written to:

- `output/circuits/`: QASM3 circuit logs generated during each run.
- `output/results/<backend>/<run_id>/*.csv`: raw timing CSV files.
- `output/results/runs.log`: append-only run log.

The default statistics policy is six repeats per case. Aggregation removes the first repeat as warmup and averages the remaining samples.

Useful environment variables:

- `TIMEOUT_S`: per-case runner silence timeout, default `150`.
- `REPEATS`: repeats per case, default `6`.
- `SHOTS`: backend shots, default `1`.
- `BASELINE_RUN_ID`: run id for `cuQuantum`, `ddsim`, `qblaze`, default `latest`.
- `ZXH_RUN_ID`: run id for `zxh`, default `latest`.
- `ABLATION_RUN_ID`: run id for `zxh-nox` and `zxh-exp`, default `latest`.
- `RUN_BASELINES=0`, `RUN_ZXH=0`, `RUN_P_BATCH=0`, or `RUN_ABLATIONS=0` can skip selected experiment groups.

Example partial run:

```bash
RUN_BASELINES=0 RUN_ABLATIONS=0 RUN_P_BATCH=0 ./run_all.sh
```

## Step 3: Aggregate and Plot

```bash
./aggregate.sh
```

This regenerates four figure files under `output/figures/`:

- `capability_near30_sc.png`
- `representative_families_sc_v4.png`
- `representative_families_ablation_sameframe_sc.png`
- `kernel_diag_batch_sc_v4.png`

It also writes `output/figures/speedup_summary.txt` and prints the ZXH/cuQuantum geometric speedups for `near30` and the four sweep families. The main near-30 paper number is computed on common solved cases after excluding the trivial `ghz` outlier.

## Expected Reference Outcome

On the reference A100 PCIe 40GB system, the current result set gives:

- Near-30 capability: ZXH-Sim `29/30`, cuQuantum `29/30`, qblaze `26/30`, DDSIM `18/30`.
- Near-30 ZXH/cuQuantum geometric speedup: `10.18x` on all common solved cases.
- Near-30 ZXH/cuQuantum geometric speedup excluding `ghz`: `8.16x`.

Small numerical differences are expected across GPU driver versions and system load. The qualitative checks are that ZXH-Sim matches cuQuantum coverage on near-30, remains faster on the common solved subset, and that the ablation and kernel figures show the expected transport, lazy-expansion, and diagonal-batching effects.

## Reproducibility Notes

- `src/env.sh` fixes `PYTHONHASHSEED=10` and places `src/pydeps` and `src/bin` first in the Python and executable search paths.
- The runners use Qiskit with `seed_transpiler=10` and keep lowered circuits in memory for execution; QASM3 files are emitted as logs.
- Result CSV files store raw timing arrays in the `times` column. Post-processing, not the runner, removes warmup samples.
- Timeout rows are retained in CSV files and counted as unsolved in coverage plots.
