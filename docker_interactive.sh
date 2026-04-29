#!/usr/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

docker run --rm -it \
	--gpus all \
	--ipc=host \
	--ulimit memlock=-1 \
	--ulimit stack=67108864 \
	-v "${SCRIPT_DIR}/output:/home/cuquantum/output" \
	-v "${SCRIPT_DIR}/src:/home/cuquantum/src" \
	nvcr.io/nvidia/cuquantum-appliance:25.11-x86_64
