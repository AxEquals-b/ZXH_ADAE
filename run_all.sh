#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${ADAE_IMAGE:-zxh-adae:latest}"
TIMEOUT_S="${TIMEOUT_S:-150}"
REPEATS="${REPEATS:-6}"
SHOTS="${SHOTS:-1}"
ZXH_RUN_ID="${ZXH_RUN_ID:-latest}"
BASELINE_RUN_ID="${BASELINE_RUN_ID:-latest}"
ABLATION_RUN_ID="${ABLATION_RUN_ID:-latest}"
P_BATCH_RUN_ID="${P_BATCH_RUN_ID:-${ZXH_RUN_ID}}"
RUN_BASELINES="${RUN_BASELINES:-1}"
RUN_ZXH="${RUN_ZXH:-1}"
RUN_ABLATIONS="${RUN_ABLATIONS:-1}"
RUN_P_BATCH="${RUN_P_BATCH:-1}"

mkdir -p "${ROOT_DIR}/output/results" "${ROOT_DIR}/output/circuits" "${ROOT_DIR}/output/figures"
# The container may use a different UID than the host user that extracted the artifact.
chmod -R a+rwX "${ROOT_DIR}/output"

docker run --rm \
  --gpus all \
  --ipc=host \
  --ulimit memlock=-1 \
  --ulimit stack=67108864 \
  -e "TIMEOUT_S=${TIMEOUT_S}" \
  -e "REPEATS=${REPEATS}" \
  -e "SHOTS=${SHOTS}" \
  -e "ZXH_RUN_ID=${ZXH_RUN_ID}" \
  -e "BASELINE_RUN_ID=${BASELINE_RUN_ID}" \
  -e "ABLATION_RUN_ID=${ABLATION_RUN_ID}" \
  -e "P_BATCH_RUN_ID=${P_BATCH_RUN_ID}" \
  -e "RUN_BASELINES=${RUN_BASELINES}" \
  -e "RUN_ZXH=${RUN_ZXH}" \
  -e "RUN_ABLATIONS=${RUN_ABLATIONS}" \
  -e "RUN_P_BATCH=${RUN_P_BATCH}" \
  -v "${ROOT_DIR}/output:/home/cuquantum/output" \
  "${IMAGE}" bash -lc '
set -euo pipefail
source /home/cuquantum/src/env.sh

families=(bv qft qwalk vqe_two_local)

run_near30() {
  local backend="$1"
  local run_id="$2"
  python /home/cuquantum/src/scripts/run_near30.py \
    --backend "${backend}" \
    --run-id "${run_id}" \
    --timeout-s "${TIMEOUT_S}" \
    --repeats "${REPEATS}" \
    --shots "${SHOTS}"
}

run_sweeps() {
  local backend="$1"
  local run_id="$2"
  for family in "${families[@]}"; do
    python /home/cuquantum/src/scripts/run_sweep.py \
      --backend "${backend}" \
      --family "${family}" \
      --run-id "${run_id}" \
      --timeout-s "${TIMEOUT_S}" \
      --repeats "${REPEATS}" \
      --shots "${SHOTS}"
  done
}

if [[ "${RUN_BASELINES}" == "1" ]]; then
  for backend in cuQuantum ddsim qblaze; do
    run_near30 "${backend}" "${BASELINE_RUN_ID}"
    run_sweeps "${backend}" "${BASELINE_RUN_ID}"
  done
fi

if [[ "${RUN_ZXH}" == "1" ]]; then
  run_near30 zxh "${ZXH_RUN_ID}"
  run_sweeps zxh "${ZXH_RUN_ID}"
fi

if [[ "${RUN_P_BATCH}" == "1" ]]; then
  python /home/cuquantum/src/scripts/run_p_batch.py \
    --backend zxh \
    --run-id "${P_BATCH_RUN_ID}" \
    --timeout-s "${TIMEOUT_S}" \
    --repeats "${REPEATS}"
fi

if [[ "${RUN_ABLATIONS}" == "1" ]]; then
  for backend in zxh-nox zxh-exp; do
    run_sweeps "${backend}" "${ABLATION_RUN_ID}"
  done
fi
'
