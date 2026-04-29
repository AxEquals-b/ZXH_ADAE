#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from importlib import metadata
from pathlib import Path
from typing import Any

try:
    from .runner_common import (
        DEFAULT_MANIFEST,
        DEFAULT_REPEATS,
        DEFAULT_WARMUP,
        PerRunTimeoutExceeded,
        RUNS_ROOT,
        enforce_per_run_time_budget,
        load_canonical_input,
        measured_end_to_end_ms,
        per_run_timeout_s,
        repo_rel,
        resolve_repo_path,
        select_rows,
        timestamp,
        write_run_outputs,
    )
except ImportError:  # pragma: no cover
    from runner_common import (
        DEFAULT_MANIFEST,
        DEFAULT_REPEATS,
        DEFAULT_WARMUP,
        PerRunTimeoutExceeded,
        RUNS_ROOT,
        enforce_per_run_time_budget,
        load_canonical_input,
        measured_end_to_end_ms,
        per_run_timeout_s,
        repo_rel,
        resolve_repo_path,
        select_rows,
        timestamp,
        write_run_outputs,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run prepared representative cases on qblaze backend.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--shots", type=int, default=1)
    parser.add_argument("--time-budget-s", type=float, default=None)
    parser.add_argument("--run-id", type=str, default=None)
    return parser.parse_args()


def _load_qblaze_backend():
    from qblaze.qiskit import Backend

    return Backend()


def _run_iteration(*, circuit, shots: int, qblaze_backend) -> dict[str, Any]:
    t0 = time.perf_counter()
    result = qblaze_backend.run(circuit, shots=shots).result()
    execute_ms = (time.perf_counter() - t0) * 1000.0
    observed_outcomes = len(result.get_counts())
    return {
        "kernel_build_ms": 0.0,
        "execute_ms": execute_ms,
        "sample_ms": 0.0,
        "backend_total_ms": execute_ms,
        "observed_outcomes": observed_outcomes,
    }


def _error_row(
    *,
    family: str,
    num_qubits: int,
    qasm_path: Path,
    shared_metrics: dict[str, Any],
    error: str,
    status: str = "error",
) -> dict[str, Any]:
    return {
        "family": family,
        "N": num_qubits,
        "backend": "qblaze",
        "repeat_index": -1,
        "qasm_path": repo_rel(qasm_path),
        "load_qasm_ms": shared_metrics["load_qasm_ms"],
        "input_prepare_ms": shared_metrics["input_prepare_ms"],
        "canonical_gate_count": shared_metrics["canonical_gate_count"],
        "canonical_gate_types": ";".join(shared_metrics["canonical_gate_types"]),
        "execution_gate_count": shared_metrics["execution_gate_count"],
        "execution_gate_types": ";".join(shared_metrics["execution_gate_types"]),
        "kernel_build_ms": 0.0,
        "execute_ms": 0.0,
        "sample_ms": 0.0,
        "backend_total_ms": 0.0,
        "end_to_end_ms": 0.0,
        "observed_outcomes": 0,
        "status": status,
        "error": error,
    }


def main() -> int:
    args = _parse_args()
    manifest_path = resolve_repo_path(args.manifest)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    rows = select_rows(manifest_path, args.family, args.limit)
    run_id = args.run_id or f"qblaze_{timestamp()}"
    out_dir = RUNS_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    qblaze_backend = _load_qblaze_backend()

    metadata_obj: dict[str, Any] = {
        "run_id": run_id,
        "manifest_path": repo_rel(manifest_path),
        "selected_backends": ["qblaze"],
        "selected_families": [row["family"] for row in rows],
        "warmup": args.warmup,
        "repeats": args.repeats,
        "shots": args.shots,
        "time_budget_s": args.time_budget_s,
        "per_run_timeout_s": per_run_timeout_s(args.time_budget_s),
        "input_mode": "canonical_qasm3_strict",
        "compile_api": "none",
        "python_version": sys.version,
        "qiskit_version": metadata.version("qiskit"),
        "qblaze_version": metadata.version("qblaze"),
    }

    raw_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for case_row in rows:
        family = str(case_row["family"])
        num_qubits = int(case_row["N"])
        qasm_path = resolve_repo_path(str(case_row["canonical_qasm3_path"]))
        if not qasm_path.is_file():
            raise FileNotFoundError(f"Canonical QASM file missing: {qasm_path}")

        canonical_circuit, _, shared_metrics = load_canonical_input(qasm_path)
        print(
            f"[case] family={family} N={num_qubits} canonical_gate_count={shared_metrics['canonical_gate_count']} "
            f"execution_gate_count={shared_metrics['execution_gate_count']}",
            flush=True,
        )
        print(f"[run] family={family} backend=qblaze warmup={args.warmup} repeats={args.repeats}", flush=True)

        try:
            for warmup_index in range(args.warmup):
                backend_metrics = _run_iteration(circuit=canonical_circuit, shots=args.shots, qblaze_backend=qblaze_backend)
                enforce_per_run_time_budget(
                    family=family,
                    backend="qblaze",
                    phase="warmup",
                    iteration_index=warmup_index,
                    backend_total_ms=float(backend_metrics["backend_total_ms"]),
                    time_budget_s=args.time_budget_s,
                )

            for repeat_index in range(args.repeats):
                backend_metrics = _run_iteration(
                    circuit=canonical_circuit,
                    shots=args.shots,
                    qblaze_backend=qblaze_backend,
                )
                enforce_per_run_time_budget(
                    family=family,
                    backend="qblaze",
                    phase="repeat",
                    iteration_index=repeat_index,
                    backend_total_ms=float(backend_metrics["backend_total_ms"]),
                    time_budget_s=args.time_budget_s,
                )
                raw_rows.append(
                    {
                        "family": family,
                        "N": num_qubits,
                        "backend": "qblaze",
                        "repeat_index": repeat_index,
                        "qasm_path": repo_rel(qasm_path),
                        "load_qasm_ms": shared_metrics["load_qasm_ms"],
                        "input_prepare_ms": shared_metrics["input_prepare_ms"],
                        "canonical_gate_count": shared_metrics["canonical_gate_count"],
                        "canonical_gate_types": ";".join(shared_metrics["canonical_gate_types"]),
                        "execution_gate_count": shared_metrics["execution_gate_count"],
                        "execution_gate_types": ";".join(shared_metrics["execution_gate_types"]),
                        "kernel_build_ms": backend_metrics["kernel_build_ms"],
                        "execute_ms": backend_metrics["execute_ms"],
                        "sample_ms": backend_metrics["sample_ms"],
                        "backend_total_ms": backend_metrics["backend_total_ms"],
                        "end_to_end_ms": measured_end_to_end_ms(
                            execute_ms=backend_metrics["execute_ms"],
                            sample_ms=backend_metrics["sample_ms"],
                        ),
                        "observed_outcomes": backend_metrics["observed_outcomes"],
                        "status": "pass",
                        "error": "",
                    }
                )
        except PerRunTimeoutExceeded as exc:
            row = _error_row(
                family=family,
                num_qubits=num_qubits,
                qasm_path=qasm_path,
                shared_metrics=shared_metrics,
                error=str(exc),
                status="timeout",
            )
            raw_rows.append(row)
            errors.append(row)
            print(f"[timeout] family={family} backend=qblaze error={row['error']}", flush=True)
        except Exception as exc:
            row = _error_row(
                family=family,
                num_qubits=num_qubits,
                qasm_path=qasm_path,
                shared_metrics=shared_metrics,
                error=f"{type(exc).__name__}: {exc}",
            )
            raw_rows.append(row)
            errors.append(row)
            print(f"[error] family={family} backend=qblaze error={row['error']}", flush=True)

    write_run_outputs(out_dir, metadata_obj, raw_rows, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
