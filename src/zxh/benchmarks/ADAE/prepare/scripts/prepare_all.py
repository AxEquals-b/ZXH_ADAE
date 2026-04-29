#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
ADAE_ROOT = REPO_ROOT / "benchmarks" / "ADAE"
PREPARE_RESULTS_ROOT = ADAE_ROOT / "results" / "prepare"
PIPELINE_ROOT = PREPARE_RESULTS_ROOT / "pipelines"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ADAE prepare stage end to end.")
    parser.add_argument("--run-id", type=str, default=None, help="Optional prepare pipeline run id.")
    parser.add_argument("--n-min", type=int, default=20)
    parser.add_argument("--n-max", type=int, default=32)
    parser.add_argument("--opt-level", type=int, choices=range(4), default=2)
    parser.add_argument("--representative-max-n", type=int, default=30)
    parser.add_argument("--dev-max-n", type=int, default=24)
    parser.add_argument("--gate-count-budget", type=int, default=1_000_000)
    parser.add_argument("--count-max-definition-depth", type=int, default=32)
    parser.add_argument("--skip-sweep", action="store_true")
    parser.add_argument(
        "--include-mpi-cuda",
        action="store_true",
        help="Also build the mpi_cuda stage during prepare. The default only builds cuda.",
    )
    return parser.parse_args()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _run_step(name: str, cmd: list[str], log_dir: Path) -> dict[str, Any]:
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    log_path = log_dir / f"{name}.log"
    log_path.write_text(
        f"$ {' '.join(cmd)}\nreturncode={proc.returncode}\n\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}\n",
        encoding="utf-8",
    )
    return {
        "name": name,
        "command": cmd,
        "returncode": proc.returncode,
        "status": "pass" if proc.returncode == 0 else "failed",
        "log_path": str(log_path),
    }


def _summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# ADAE Prepare Pipeline Summary",
        "",
        f"- run_id: `{summary['run_id']}`",
        "",
        "| step | status | log_path |",
        "| --- | --- | --- |",
    ]
    for row in summary["rows"]:
        lines.append(f"| {row['name']} | {row['status']} | {row['log_path']} |")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    run_id = args.run_id or f"prepare_{_timestamp()}"
    out_dir = PIPELINE_ROOT / run_id
    log_dir = out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    rows = []

    rows.append(
        _run_step(
            "install_python_frontends",
            [sys.executable, str(ADAE_ROOT / "prepare" / "scripts" / "install_python_frontends.py")],
            log_dir,
        )
    )

    build_cmd = [
        sys.executable,
        str(ADAE_ROOT / "prepare" / "scripts" / "build_zxh_stages.py"),
        "--backend",
        "cuda",
    ]
    if args.include_mpi_cuda:
        build_cmd.extend(["--backend", "mpi_cuda"])
    rows.append(_run_step("build_zxh_stages", build_cmd, log_dir))

    generate_cmd = [
        sys.executable,
        str(ADAE_ROOT / "prepare" / "generators" / "generate_all.py"),
        "--n-min",
        str(args.n_min),
        "--n-max",
        str(args.n_max),
        "--opt-level",
        str(args.opt_level),
        "--representative-max-n",
        str(args.representative_max_n),
        "--dev-max-n",
        str(args.dev_max_n),
        "--gate-count-budget",
        str(args.gate_count_budget),
        "--count-max-definition-depth",
        str(args.count_max_definition_depth),
        "--zxh-backend",
        "cuda",
    ]
    if args.skip_sweep:
        generate_cmd.append("--skip-sweep")
    rows.append(_run_step("generate_workloads", generate_cmd, log_dir))

    summary = {
        "run_id": run_id,
        "rows": rows,
    }
    summary_json = out_dir / "prepare_summary.json"
    summary_md = out_dir / "prepare_summary.md"
    _write_json(summary_json, summary)
    summary_md.write_text(_summary_markdown(summary), encoding="utf-8")

    print(f"summary_json={summary_json}")
    print(f"summary_md={summary_md}")
    failures = [row for row in rows if row["status"] != "pass"]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
