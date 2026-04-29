#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from run_common import DEFAULT_CIRCUITS_ROOT, DEFAULT_RESULTS_ROOT, default_run_id, run_suite
from suite_registry import all_sweep_families, sweep_suite_name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one sweep family for one backend.")
    parser.add_argument("--backend", required=True, type=str)
    parser.add_argument("--family", required=True, choices=all_sweep_families())
    parser.add_argument("--circuits-root", type=Path, default=DEFAULT_CIRCUITS_ROOT)
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--timeout-s", type=float, default=150.0)
    parser.add_argument("--repeats", type=int, default=6)
    parser.add_argument("--shots", type=int, default=1)
    parser.add_argument("--run-id", type=str, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return run_suite(
        script_name="run_sweep.py",
        suite_name=sweep_suite_name(args.family),
        result_name=args.family,
        backend=args.backend,
        circuits_root=args.circuits_root,
        results_root=args.results_root,
        timeout_s=args.timeout_s,
        repeats=args.repeats,
        small_n_repeats=12,
        small_n_threshold=25,
        skip_larger_n_after_timeout=True,
        shots=args.shots,
        run_id=args.run_id or default_run_id(args.backend),
    )


if __name__ == "__main__":
    raise SystemExit(main())
