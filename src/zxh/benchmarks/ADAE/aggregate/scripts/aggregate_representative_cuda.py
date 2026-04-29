#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
ADAE_ROOT = REPO_ROOT / "benchmarks" / "ADAE"
RUN_RESULTS_ROOT = ADAE_ROOT / "results" / "run" / "representative_cuda"
AGGREGATE_RESULTS_ROOT = ADAE_ROOT / "results" / "aggregate" / "representative_cuda"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate representative CUDA benchmark summaries into speedup tables.")
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=None,
        help="Path to a run-stage summary.json. If omitted, --run-id is required.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Run-stage directory name under benchmarks/ADAE/results/run/representative_cuda/.",
    )
    parser.add_argument(
        "--aggregate-id",
        type=str,
        default=None,
        help="Optional aggregate output directory name under benchmarks/ADAE/results/aggregate/representative_cuda/.",
    )
    return parser.parse_args()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _resolve_summary_path(args: argparse.Namespace) -> Path:
    if args.summary_json is not None:
        path = args.summary_json
        if not path.is_absolute():
            path = (REPO_ROOT / path).resolve()
        return path
    if args.run_id is None:
        raise ValueError("Either --summary-json or --run-id must be provided.")
    return (RUN_RESULTS_ROOT / args.run_id / "summary.json").resolve()


def _markdown_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Representative CUDA Aggregate Summary",
        "",
        f"- source_summary_json: `{summary['source_summary_json']}`",
        f"- aggregate_id: `{summary['aggregate_id']}`",
        "",
        "| family | N | cudaq_backend_ms | zxh_backend_ms | backend_speedup | cudaq_end_to_end_ms | zxh_end_to_end_ms | end_to_end_speedup | status |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in summary["rows"]:
        lines.append(
            "| {family} | {N} | {cudaq_backend_total_ms_mean} | {zxh_backend_total_ms_mean} | {backend_speedup_vs_cudaq} | {cudaq_end_to_end_ms_mean} | {zxh_end_to_end_ms_mean} | {end_to_end_speedup_vs_cudaq} | {status} |".format(
                **row
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    summary_path = _resolve_summary_path(args)
    if not summary_path.is_file():
        raise FileNotFoundError(f"Run summary not found: {summary_path}")

    obj = json.loads(summary_path.read_text(encoding="utf-8"))
    rows_in = list(obj.get("rows", []))
    grouped: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in rows_in:
        grouped[(str(row["family"]), int(row["N"]))][str(row["backend"])] = row

    rows_out: list[dict[str, Any]] = []
    for (family, num_qubits), backend_rows in sorted(grouped.items()):
        cudaq_row = backend_rows.get("cudaq")
        zxh_row = backend_rows.get("zxh-cuda")

        cudaq_backend = cudaq_row["backend_total_ms_mean"] if cudaq_row is not None else None
        zxh_backend = zxh_row["backend_total_ms_mean"] if zxh_row is not None else None
        cudaq_e2e = cudaq_row["end_to_end_ms_mean"] if cudaq_row is not None else None
        zxh_e2e = zxh_row["end_to_end_ms_mean"] if zxh_row is not None else None

        backend_speedup = None
        if cudaq_backend and zxh_backend:
            backend_speedup = cudaq_backend / zxh_backend

        end_to_end_speedup = None
        if cudaq_e2e and zxh_e2e:
            end_to_end_speedup = cudaq_e2e / zxh_e2e

        rows_out.append(
            {
                "family": family,
                "N": num_qubits,
                "cudaq_backend_total_ms_mean": "" if cudaq_backend is None else f"{cudaq_backend:.6f}",
                "zxh_backend_total_ms_mean": "" if zxh_backend is None else f"{zxh_backend:.6f}",
                "backend_speedup_vs_cudaq": "" if backend_speedup is None else f"{backend_speedup:.6f}",
                "cudaq_end_to_end_ms_mean": "" if cudaq_e2e is None else f"{cudaq_e2e:.6f}",
                "zxh_end_to_end_ms_mean": "" if zxh_e2e is None else f"{zxh_e2e:.6f}",
                "end_to_end_speedup_vs_cudaq": "" if end_to_end_speedup is None else f"{end_to_end_speedup:.6f}",
                "status": "paired" if cudaq_row is not None and zxh_row is not None else "incomplete",
            }
        )

    aggregate_id = args.aggregate_id or f"representative_cuda_{_timestamp()}"
    out_dir = AGGREGATE_RESULTS_ROOT / aggregate_id
    summary = {
        "aggregate_id": aggregate_id,
        "source_summary_json": _repo_rel(summary_path),
        "rows": rows_out,
    }
    json_path = out_dir / "speedup_summary.json"
    csv_path = out_dir / "speedup_summary.csv"
    md_path = out_dir / "speedup_summary.md"

    _write_json(json_path, summary)
    _write_csv(
        csv_path,
        rows_out,
        [
            "family",
            "N",
            "cudaq_backend_total_ms_mean",
            "zxh_backend_total_ms_mean",
            "backend_speedup_vs_cudaq",
            "cudaq_end_to_end_ms_mean",
            "zxh_end_to_end_ms_mean",
            "end_to_end_speedup_vs_cudaq",
            "status",
        ],
    )
    md_path.write_text(_markdown_report(summary), encoding="utf-8")

    print(f"summary_json={json_path}")
    print(f"summary_csv={csv_path}")
    print(f"summary_md={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
