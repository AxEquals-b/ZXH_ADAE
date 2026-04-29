#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${ADAE_IMAGE:-zxh-adae:latest}"
ZXH_RUN_ID="${ZXH_RUN_ID:-latest}"
BASELINE_RUN_ID="${BASELINE_RUN_ID:-latest}"
ABLATION_RUN_ID="${ABLATION_RUN_ID:-latest}"
P_BATCH_RUN_ID="${P_BATCH_RUN_ID:-${ZXH_RUN_ID}}"

mkdir -p "${ROOT_DIR}/output/figures"

docker run --rm \
  --gpus all \
  --ipc=host \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  -e "ZXH_RUN_ID=${ZXH_RUN_ID}" \
  -e "BASELINE_RUN_ID=${BASELINE_RUN_ID}" \
  -e "ABLATION_RUN_ID=${ABLATION_RUN_ID}" \
  -e "P_BATCH_RUN_ID=${P_BATCH_RUN_ID}" \
  -v "${ROOT_DIR}/output:/home/cuquantum/output" \
  "${IMAGE}" bash -lc '
set -euo pipefail
source /home/cuquantum/src/env.sh

python /home/cuquantum/src/scripts/sc_capability_redraw.py
python /home/cuquantum/src/scripts/sc_figure_redraw_v4.py
python /home/cuquantum/src/scripts/sc_representative_ablation_sameframe_redraw.py

python - <<'"'"'PY'"'"'
import csv, json, math, os
from pathlib import Path

root = Path("/home/cuquantum/output/results")
zxh_run = Path(root, "zxh", os.environ.get("ZXH_RUN_ID", "latest"))
cu_run = Path(root, "cuQuantum", os.environ.get("BASELINE_RUN_ID", "latest"))
out = Path("/home/cuquantum/output/figures/speedup_summary.txt")

families = ["near30", "bv", "qft", "qwalk", "vqe_two_local"]

def parse_times(text):
    if not text or not str(text).strip():
        return []
    return [float(x) for x in json.loads(text) if x is not None]

def mean_after_warmup(text):
    xs = parse_times(text)
    if len(xs) > 1:
        xs = xs[1:]
    return sum(xs) / len(xs) if xs else None

def load(path):
    rows = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("status") != "pass":
                continue
            value = mean_after_warmup(row.get("times", ""))
            if value is not None:
                rows[row["circuit"]] = value
    return rows

def geo(values):
    return math.exp(sum(math.log(x) for x in values) / len(values)) if values else float("nan")

lines = []
for family in families:
    zxh = load(zxh_run / f"{family}.csv")
    cuq = load(cu_run / f"{family}.csv")
    common = sorted(set(zxh) & set(cuq))
    ratios = [cuq[name] / zxh[name] for name in common]
    lines.append(f"{family}: ZXH/cuQuantum geometric speedup = {geo(ratios):.6f}x over {len(ratios)} common solved cases")
    if family == "near30":
        common_no_ghz = [name for name in common if not name.startswith("ghz_")]
        ratios_no_ghz = [cuq[name] / zxh[name] for name in common_no_ghz]
        lines.append(f"near30_excluding_ghz: ZXH/cuQuantum geometric speedup = {geo(ratios_no_ghz):.6f}x over {len(ratios_no_ghz)} common solved cases")

out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(out)
print("\n".join(lines))
PY
'
