#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

_CAPTURE_KEYS = [
    "CXX",
    "MPICXX",
    "CUDACXX",
    "CUDAARCHS",
    "CUDAFLAGS",
    "CUDA_PATH",
    "CUB_ROOT",
    "CMAKE_PREFIX_PATH",
    "OMP_NUM_THREADS",
    "CUDA_VISIBLE_DEVICES",
    "CMAKE_EXECUTABLE",
    "SLURM_JOB_ID",
    "SLURM_JOB_NODELIST",
    "SLURM_NNODES",
    "SLURM_NTASKS",
    "SLURM_NTASKS_PER_NODE",
    "SLURM_STEP_ID",
    "SLURM_PROCID",
    "SLURM_LOCALID",
]


def _git_output(*args: str) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def capture_env() -> dict[str, Any]:
    tracked_env = {key: os.environ[key] for key in _CAPTURE_KEYS if key in os.environ}
    env_data: dict[str, Any] = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "system": platform.system(),
        "machine": platform.machine(),
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "repo_root": str(REPO_ROOT),
        "git_commit": _git_output("rev-parse", "HEAD"),
        "git_branch": _git_output("rev-parse", "--abbrev-ref", "HEAD"),
        "git_dirty": bool(_git_output("status", "--porcelain")),
        "tracked_env": tracked_env,
    }
    digest = hashlib.sha256(
        json.dumps(env_data, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    env_data["env_id"] = digest[:16]
    return env_data


def write_env(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Capture benchmark environment metadata")
    parser.add_argument("--json-out", type=Path, required=True, help="Output JSON path")
    args = parser.parse_args()

    write_env(args.json_out, capture_env())
    print(args.json_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
