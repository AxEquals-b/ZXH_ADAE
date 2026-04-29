#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import statistics
import sys
from typing import Any

REPORTS_DIR = Path(__file__).resolve().parent
BENCH_ROOT = REPORTS_DIR.parent
if str(BENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCH_ROOT))

from manifest import load_manifest

_METRIC_KEYS = [
    "compile_time_ms",
    "execute_time_ms",
    "sample_time_ms",
    "total_time_ms",
]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"count": 0, "mean": 0.0, "stdev": 0.0, "min": 0.0, "max": 0.0}
    return {
        "count": float(len(values)),
        "mean": statistics.mean(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def _aggregate(report: dict[str, Any]) -> dict[str, Any]:
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for result in report.get("results", []):
        if result.get("phase") != "measure":
            continue
        if result.get("status") != "pass":
            continue
        key = (str(result["backend"]), str(result["workload_id"]))
        group = groups.setdefault(
            key,
            {
                "backend": result["backend"],
                "workload_id": result["workload_id"],
                "family_id": result.get("family_id", ""),
                "num_qubits": result.get("num_qubits", 0),
                "params": result.get("params", {}),
                "metrics_samples": {metric: [] for metric in _METRIC_KEYS},
            },
        )
        metrics = result.get("metrics_ms", {})
        for metric in _METRIC_KEYS:
            if metric in metrics:
                group["metrics_samples"][metric].append(float(metrics[metric]))

    aggregated_groups: list[dict[str, Any]] = []
    for (_, _), group in sorted(groups.items()):
        metrics_summary = {
            metric: _stats(values) for metric, values in group.pop("metrics_samples").items()
        }
        group["metrics_ms"] = metrics_summary
        aggregated_groups.append(group)

    return {
        "suite_id": report.get("suite_id", ""),
        "source_report": report.get("output_dir", ""),
        "env_id": report.get("env_id", ""),
        "groups": aggregated_groups,
        "summary": {
            "group_count": len(aggregated_groups),
            "measured_result_count": len(
                [
                    item
                    for item in report.get("results", [])
                    if item.get("phase") == "measure" and item.get("status") == "pass"
                ]
            ),
        },
    }


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: Path, aggregate: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "backend",
        "workload_id",
        "family_id",
        "num_qubits",
        "compile_time_ms_mean",
        "compile_time_ms_stdev",
        "execute_time_ms_mean",
        "execute_time_ms_stdev",
        "sample_time_ms_mean",
        "sample_time_ms_stdev",
        "total_time_ms_mean",
        "total_time_ms_stdev",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for group in aggregate.get("groups", []):
            metrics = group.get("metrics_ms", {})
            writer.writerow(
                {
                    "backend": group.get("backend", ""),
                    "workload_id": group.get("workload_id", ""),
                    "family_id": group.get("family_id", ""),
                    "num_qubits": group.get("num_qubits", 0),
                    "compile_time_ms_mean": metrics.get("compile_time_ms", {}).get("mean", 0.0),
                    "compile_time_ms_stdev": metrics.get("compile_time_ms", {}).get("stdev", 0.0),
                    "execute_time_ms_mean": metrics.get("execute_time_ms", {}).get("mean", 0.0),
                    "execute_time_ms_stdev": metrics.get("execute_time_ms", {}).get("stdev", 0.0),
                    "sample_time_ms_mean": metrics.get("sample_time_ms", {}).get("mean", 0.0),
                    "sample_time_ms_stdev": metrics.get("sample_time_ms", {}).get("stdev", 0.0),
                    "total_time_ms_mean": metrics.get("total_time_ms", {}).get("mean", 0.0),
                    "total_time_ms_stdev": metrics.get("total_time_ms", {}).get("stdev", 0.0),
                }
            )


def main() -> int:
    parser = argparse.ArgumentParser(description="Aggregate ZXH-Sim benchmark raw results")
    parser.add_argument("--suite", type=str, required=True, help="Suite id or suite yaml path")
    args = parser.parse_args()

    suite_arg = Path(args.suite)
    if suite_arg.suffix:
        suite_path = suite_arg if suite_arg.is_absolute() else (Path.cwd() / suite_arg).resolve()
    else:
        suite_path = (BENCH_ROOT / "suites" / f"{args.suite}.yaml").resolve()
    suite = load_manifest(suite_path)
    manifest = load_manifest(BENCH_ROOT / "manifest.yaml")
    output_root = Path(str(manifest.get("defaults", {}).get("output_root", "build/benchmarks")))
    if not output_root.is_absolute():
        output_root = (BENCH_ROOT.parent / output_root).resolve()
    input_path = output_root / str(suite.get("suite_id", suite_path.stem)) / "raw.json"
    report = _load_json(input_path)
    aggregate = _aggregate(report)

    json_out = input_path.with_name("aggregate.json")
    csv_out = input_path.with_name("aggregate.csv")
    _write_json(json_out, aggregate)
    _write_csv(csv_out, aggregate)
    print(json_out)
    print(csv_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
