#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
IMAGE="${ADAE_IMAGE:-zxh-adae:latest}"
BASE_IMAGE="${CUQUANTUM_IMAGE:-nvcr.io/nvidia/cuquantum-appliance:25.11-x86_64}"

cd "${ROOT_DIR}"
mkdir -p output/results output/circuits output/figures

./install_zxh.sh

docker build \
  --build-arg "BASE_IMAGE=${BASE_IMAGE}" \
  -t "${IMAGE}" \
  "${ROOT_DIR}"

cat <<MSG
Prepared ${IMAGE}.
Run experiments with: ./run_all.sh
Aggregate results with: ./aggregate.sh
MSG
