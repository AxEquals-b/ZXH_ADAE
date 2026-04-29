#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[4]
ADAE_ROOT = REPO_ROOT / "benchmarks" / "ADAE"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the current ADAE aggregate stage.")
    parser.add_argument("--summary-json", type=str, default=None)
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--aggregate-id", type=str, default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    cmd = [
        sys.executable,
        str(ADAE_ROOT / "aggregate" / "scripts" / "aggregate_representative_cuda.py"),
    ]
    if args.summary_json is not None:
        cmd.extend(["--summary-json", args.summary_json])
    if args.run_id is not None:
        cmd.extend(["--run-id", args.run_id])
    if args.aggregate_id is not None:
        cmd.extend(["--aggregate-id", args.aggregate_id])
    proc = subprocess.run(cmd, cwd=REPO_ROOT, check=False)
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
