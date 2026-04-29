#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev
from typing import Any

from qiskit import qasm3


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.ADAE.prepare.generators.mqt_workflow.canonical_ir import CANONICAL_QASM_GATES


ADAE_ROOT = REPO_ROOT / "benchmarks" / "ADAE"
RUNS_ROOT = ADAE_ROOT / "results" / "run" / "representative_cuda"
DEFAULT_MANIFEST = ADAE_ROOT / "results" / "prepare" / "workflow" / "03_pass3_canonicalize" / "canonical_manifest.json"
DEFAULT_WARMUP = 4
DEFAULT_REPEATS = 8
DEFAULT_TIME_BUDGET_S = 100.0
PER_RUN_TIMEOUT_MULTIPLIER = 1.5
REPEAT_RSD_WARNING_THRESHOLD = 0.10

SUMMARY_PRIMARY_METRIC_KEY = "end_to_end_ms"


class PerRunTimeoutExceeded(TimeoutError):
    pass


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def resolve_repo_path(path_str: str | Path) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_manifest_rows(path: Path) -> list[dict[str, Any]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    rows = list(obj.get("rows", []))
    if not rows:
        raise RuntimeError(f"No rows found in manifest: {path}")
    return rows


def select_rows(manifest_path: Path, family_filters: list[str], limit: int | None) -> list[dict[str, Any]]:
    rows = load_manifest_rows(manifest_path)
    if family_filters:
        selected = set(family_filters)
        rows = [row for row in rows if str(row["family"]) in selected]
    rows = sorted(rows, key=lambda row: (int(row.get("N", 0)), str(row["family"])))
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        raise RuntimeError("No benchmark cases were selected.")
    return rows


def load_canonical_input(qasm_path: Path) -> tuple[Any, Any, dict[str, Any]]:
    t0 = time.perf_counter()
    circuit = qasm3.load(qasm_path)
    load_ms = (time.perf_counter() - t0) * 1000.0
    canonical_gate_count = len(circuit.data)
    canonical_gate_types = sorted({inst.operation.name.lower() for inst in circuit.data})

    t1 = time.perf_counter()
    invalid_gate_types = sorted(set(canonical_gate_types) - set(CANONICAL_QASM_GATES))
    if invalid_gate_types:
        raise RuntimeError(
            f"Canonical QASM contains gates outside the canonical set: {invalid_gate_types}. "
            f"allowed={list(CANONICAL_QASM_GATES)}"
        )
    execution_circuit = circuit.remove_final_measurements(inplace=False)
    input_prepare_ms = (time.perf_counter() - t1) * 1000.0
    execution_gate_count = len(execution_circuit.data)
    execution_gate_types = sorted({inst.operation.name.lower() for inst in execution_circuit.data})
    return circuit, execution_circuit, {
        "load_qasm_ms": load_ms,
        "input_prepare_ms": input_prepare_ms,
        "canonical_gate_count": canonical_gate_count,
        "canonical_gate_types": canonical_gate_types,
        "execution_gate_count": execution_gate_count,
        "execution_gate_types": execution_gate_types,
    }


def measured_end_to_end_ms(*, execute_ms: float, sample_ms: float) -> float:
    return execute_ms + sample_ms


def per_run_timeout_s(time_budget_s: float | None) -> float | None:
    if time_budget_s is None:
        return None
    if time_budget_s <= 0.0:
        raise ValueError("time_budget_s must be positive when provided.")
    return time_budget_s * PER_RUN_TIMEOUT_MULTIPLIER


def enforce_per_run_time_budget(
    *,
    family: str,
    backend: str,
    phase: str,
    iteration_index: int,
    backend_total_ms: float,
    time_budget_s: float | None,
) -> None:
    timeout_s = per_run_timeout_s(time_budget_s)
    if timeout_s is None:
        return

    timeout_ms = timeout_s * 1000.0
    if backend_total_ms <= timeout_ms:
        return

    raise PerRunTimeoutExceeded(
        f"Per-run timeout exceeded: family={family} backend={backend} phase={phase} "
        f"iteration={iteration_index + 1} backend_total_ms={backend_total_ms:.3f} "
        f"threshold_ms={timeout_ms:.3f} time_budget_s={time_budget_s:.3f} "
        f"multiplier={PER_RUN_TIMEOUT_MULTIPLIER:.1f}"
    )


def relative_stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = mean(values)
    if mu <= 0.0:
        return 0.0
    return stdev(values) / mu


def summary_markdown(summary_rows: list[dict[str, Any]], metadata_obj: dict[str, Any]) -> str:
    lines = [
        "# Representative CUDA Benchmark Summary",
        "",
        f"- run_id: `{metadata_obj['run_id']}`",
        f"- manifest: `{metadata_obj['manifest_path']}`",
        f"- selected_backends: `{metadata_obj['selected_backends']}`",
        f"- selected_families: `{metadata_obj['selected_families']}`",
        f"- warmup: `{metadata_obj['warmup']}`",
        f"- repeats: `{metadata_obj['repeats']}`",
        f"- shots: `{metadata_obj['shots']}`",
        f"- repeat_rsd_warning_threshold_pct: `{metadata_obj['repeat_rsd_warning_threshold_pct']}`",
        "",
        "| family | N | backend | repeats | mean_end_to_end_ms | rsd_end_to_end_pct | warning | status |",
        "| --- | ---: | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in summary_rows:
        lines.append(
            "| {family} | {N} | {backend} | {repeats} | {end_to_end_ms_mean:.3f} | {end_to_end_ms_rsd_pct:.2f} | {warning} | {status} |".format(
                **row
            )
        )
    lines.append("")
    return "\n".join(lines)


def summarize_bucket_status(bucket: list[dict[str, Any]]) -> str:
    statuses = {str(row["status"]) for row in bucket}
    if statuses == {"pass"}:
        return "pass"
    if "timeout" in statuses:
        return "timeout"
    return "error"


def build_summary_rows(raw_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for row in raw_rows:
        key = (str(row["family"]), int(row["N"]), str(row["backend"]))
        grouped.setdefault(key, []).append(row)

    summary_rows: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    for (family, num_qubits, backend), bucket in sorted(grouped.items()):
        passed = [row for row in bucket if row["status"] == "pass"]
        status = summarize_bucket_status(bucket)
        summary_row: dict[str, Any] = {
            "family": family,
            "N": num_qubits,
            "backend": backend,
            "repeats": len(passed),
            "status": status,
        }
        summary_row["kernel_build_ms_mean"] = mean(float(row["kernel_build_ms"]) for row in passed) if passed else 0.0
        summary_row["execute_ms_mean"] = mean(float(row["execute_ms"]) for row in passed) if passed else 0.0
        summary_row["sample_ms_mean"] = mean(float(row["sample_ms"]) for row in passed) if passed else 0.0
        values = [float(row[SUMMARY_PRIMARY_METRIC_KEY]) for row in passed]
        metric_mean = mean(values) if values else 0.0
        metric_rsd_pct = relative_stddev(values) * 100.0
        summary_row[f"{SUMMARY_PRIMARY_METRIC_KEY}_mean"] = metric_mean
        summary_row[f"{SUMMARY_PRIMARY_METRIC_KEY}_rsd_pct"] = metric_rsd_pct
        warning = ""
        if metric_mean > 0.0 and (metric_rsd_pct / 100.0) > REPEAT_RSD_WARNING_THRESHOLD:
            warning = f"{SUMMARY_PRIMARY_METRIC_KEY}={metric_rsd_pct:.2f}%"
        summary_row["warning"] = warning
        summary_rows.append(summary_row)
        if warning:
            warnings.append(
                {
                    "family": family,
                    "N": num_qubits,
                    "backend": backend,
                    "repeats": len(passed),
                    "warning_threshold_pct": REPEAT_RSD_WARNING_THRESHOLD * 100.0,
                    "warning": warning,
                }
            )
    return summary_rows, warnings


def write_run_outputs(out_dir: Path, metadata_obj: dict[str, Any], raw_rows: list[dict[str, Any]], errors: list[dict[str, Any]]) -> None:
    summary_rows, warnings = build_summary_rows(raw_rows)
    metadata_obj = dict(metadata_obj)
    metadata_obj["repeat_rsd_warning_threshold_pct"] = REPEAT_RSD_WARNING_THRESHOLD * 100.0

    raw_json_path = out_dir / "raw_results.json"
    raw_csv_path = out_dir / "raw_results.csv"
    summary_json_path = out_dir / "summary.json"
    summary_csv_path = out_dir / "summary.csv"
    summary_md_path = out_dir / "summary.md"

    write_json(raw_json_path, {"metadata": metadata_obj, "rows": raw_rows})
    write_csv(
        raw_csv_path,
        raw_rows,
        [
            "family",
            "N",
            "backend",
            "repeat_index",
            "qasm_path",
            "load_qasm_ms",
            "input_prepare_ms",
            "canonical_gate_count",
            "canonical_gate_types",
            "execution_gate_count",
            "execution_gate_types",
            "kernel_build_ms",
            "execute_ms",
            "sample_ms",
            "backend_total_ms",
            "end_to_end_ms",
            "observed_outcomes",
            "status",
            "error",
        ],
    )
    write_json(summary_json_path, {"metadata": metadata_obj, "rows": summary_rows, "warnings": warnings, "errors": errors})
    write_csv(
        summary_csv_path,
        summary_rows,
        [
            "family",
            "N",
            "backend",
            "repeats",
            "end_to_end_ms_mean",
            "end_to_end_ms_rsd_pct",
            "kernel_build_ms_mean",
            "execute_ms_mean",
            "sample_ms_mean",
            "warning",
            "status",
        ],
    )
    summary_md_path.write_text(summary_markdown(summary_rows, metadata_obj), encoding="utf-8")

    for warning in warnings:
        print(
            "[warning] family={family} N={N} backend={backend} repeats={repeats} rsd_threshold_pct={warning_threshold_pct:.1f} detail={detail}".format(
                family=warning["family"],
                N=warning["N"],
                backend=warning["backend"],
                repeats=warning["repeats"],
                warning_threshold_pct=warning["warning_threshold_pct"],
                detail=warning["warning"],
            ),
            flush=True,
        )

    for row in summary_rows:
        print(
            "[steady] family={family} N={N} backend={backend} repeats={repeats} end_to_end_rsd_pct={end_to_end_ms_rsd_pct:.2f}".format(
                **row
            ),
            flush=True,
        )

    print(f"raw_json={raw_json_path}", flush=True)
    print(f"raw_csv={raw_csv_path}", flush=True)
    print(f"summary_json={summary_json_path}", flush=True)
    print(f"summary_csv={summary_csv_path}", flush=True)
    print(f"summary_md={summary_md_path}", flush=True)
