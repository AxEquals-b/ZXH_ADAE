#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="${SCRIPT_DIR}/src"
ZXH_SRC="${SRC_DIR}/zxh"
PYDEPS_DIR="${SRC_DIR}/pydeps"
IMAGE="${CUQUANTUM_IMAGE:-nvcr.io/nvidia/cuquantum-appliance:25.11-x86_64}"
CMAKE_DIR="${CMAKE_DIR:-/staff/astra/tools/cmake}"
PIP_INDEX_URL="${PIP_INDEX_URL:-https://pypi.org/simple}"
PIP_RETRIES="${PIP_RETRIES:-5}"
PIP_DEFAULT_TIMEOUT="${PIP_DEFAULT_TIMEOUT:-30}"

if [[ ! -d "${ZXH_SRC}" ]]; then
	echo "missing zxh source copy: ${ZXH_SRC}" >&2
	exit 1
fi

if [[ ! -d "${PYDEPS_DIR}" ]]; then
	echo "missing pydeps directory: ${PYDEPS_DIR}" >&2
	exit 1
fi

# The cuQuantum Appliance container runs as its internal cuquantum user.
# Make the bind-mounted overlay writable even when a release zip was
# extracted by a different host UID.
chmod -R a+rwX "${PYDEPS_DIR}"

docker_args=(
	--rm
	--gpus all
	--ipc=host
	--ulimit memlock=-1
	--ulimit stack=67108864
	-e "PIP_INDEX_URL=${PIP_INDEX_URL}"
	-e "PIP_RETRIES=${PIP_RETRIES}"
	-e "PIP_DEFAULT_TIMEOUT=${PIP_DEFAULT_TIMEOUT}"
	-e "ZXHSIM_BACKEND=cuda"
	-v "${SRC_DIR}:/home/cuquantum/src"
)

if [[ -n "${PIP_EXTRA_INDEX_URL:-}" ]]; then
	docker_args+=(-e "PIP_EXTRA_INDEX_URL=${PIP_EXTRA_INDEX_URL}")
fi

if [[ -n "${PIP_TRUSTED_HOST:-}" ]]; then
	docker_args+=(-e "PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST}")
fi

if [[ -d "${CMAKE_DIR}" ]]; then
	docker_args+=(-v "${CMAKE_DIR}:/home/cuquantum/cmake:ro")
fi

docker run "${docker_args[@]}" "${IMAGE}" bash -lc '
set -euo pipefail

source /home/cuquantum/src/env.sh

if [[ -d /home/cuquantum/cmake/bin ]]; then
	export PATH="/home/cuquantum/cmake/bin:${PATH}"
fi

export PIP_DISABLE_PIP_VERSION_CHECK=1

python - <<'"'"'PY'"'"'
import shutil
import sys

if shutil.which("cmake") is None:
    print("missing build prerequisite: cmake executable", file=sys.stderr)
    sys.exit(1)
PY

python -m pip install \
	--no-deps \
	--upgrade \
	--force-reinstall \
	--target /home/cuquantum/src/pydeps \
	/home/cuquantum/src/zxh

python - <<'"'"'PY'"'"'
import zxhsim

print("zxhsim:", zxhsim.__file__)
print("_core:", zxhsim._core.__file__)
print("init_doc:", zxhsim.ZXH.__init__.__doc__)

zxhsim.init()
try:
    sim = zxhsim.ZXH(1, disable_x=False, eager_expand_all=False)
    print("num_qubits:", sim.num_qubits())
finally:
    zxhsim.finalize()
PY
'
