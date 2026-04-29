#!/usr/bin/bash

set -euo pipefail

SRC_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

umask 000

export PYTHONHASHSEED=10

export PYTHONPATH="${SRC_DIR}/pydeps${PYTHONPATH:+:${PYTHONPATH}}"
export PATH="${SRC_DIR}/bin:${PATH}"
