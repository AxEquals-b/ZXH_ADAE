#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import time
from importlib import metadata
from pathlib import Path
from typing import Any

from qiskit import QuantumCircuit

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
    parser = argparse.ArgumentParser(description="Run prepared representative cases on CUDA-Q/cuQuantum backend.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--warmup", type=int, default=DEFAULT_WARMUP)
    parser.add_argument("--repeats", type=int, default=DEFAULT_REPEATS)
    parser.add_argument("--shots", type=int, default=1)
    parser.add_argument("--time-budget-s", type=float, default=None)
    parser.add_argument("--cudaq-target", type=str, default="nvidia")
    parser.add_argument("--run-id", type=str, default=None)
    return parser.parse_args()


def _load_cudaq_modules(target_name: str):
    import cudaq

    cudaq.set_target(target_name)
    return cudaq


def _compile_canonical_to_cudaq_kernel(circuit: QuantumCircuit, cudaq_mod):
    kernel = cudaq_mod.make_kernel()
    qubits = kernel.qalloc(circuit.num_qubits)
    for inst in circuit.data:
        op = inst.operation
        name = op.name.lower()
        qargs = [circuit.find_bit(qubit).index for qubit in inst.qubits]
        params = [float(param) for param in op.params]

        if name == "barrier":
            continue
        if name == "measure":
            kernel.mz(qubits[qargs[0]])
            continue
        if name == "reset":
            raise NotImplementedError("CUDA-Q canonical runner does not support reset in execution circuits.")
        if name == "x":
            kernel.x(qubits[qargs[0]])
            continue
        if name == "h":
            kernel.h(qubits[qargs[0]])
            continue
        if name == "cx":
            kernel.cx(qubits[qargs[0]], qubits[qargs[1]])
            continue
        if name == "rz":
            kernel.rz(params[0], qubits[qargs[0]])
            continue
        if name == "u":
            kernel.u3(params[0], params[1], params[2], qubits[qargs[0]])
            continue
        if name == "cp":
            kernel.cr1(params[0], qubits[qargs[0]], qubits[qargs[1]])
            continue

        raise ValueError(f"Gate '{name}' is not supported by the canonical CUDA-Q runner.")

    return kernel


def _run_iteration(*, circuit, shots: int, cudaq_mod) -> dict[str, Any]:
    t0 = time.perf_counter()
    kernel = _compile_canonical_to_cudaq_kernel(circuit, cudaq_mod)
    kernel_build_ms = (time.perf_counter() - t0) * 1000.0

    t1 = time.perf_counter()
    result = cudaq_mod.sample(kernel, shots_count=shots)
    execute_ms = (time.perf_counter() - t1) * 1000.0
    observed_outcomes = len(result)

    return {
        "kernel_build_ms": kernel_build_ms,
        "execute_ms": execute_ms,
        "sample_ms": 0.0,
        "backend_total_ms": kernel_build_ms + execute_ms,
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
        "backend": "cudaq",
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
    run_id = args.run_id or f"cudaq_{timestamp()}"
    out_dir = RUNS_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    cudaq_mod = _load_cudaq_modules(args.cudaq_target)

    metadata_obj: dict[str, Any] = {
        "run_id": run_id,
        "manifest_path": repo_rel(manifest_path),
        "selected_backends": ["cudaq"],
        "selected_families": [row["family"] for row in rows],
        "warmup": args.warmup,
        "repeats": args.repeats,
        "shots": args.shots,
        "time_budget_s": args.time_budget_s,
        "per_run_timeout_s": per_run_timeout_s(args.time_budget_s),
        "cudaq_target": args.cudaq_target,
        "input_mode": "canonical_qasm3_strict",
        "python_version": sys.version,
        "qiskit_version": metadata.version("qiskit"),
        "cudaq_version": metadata.version("cudaq"),
    }

    raw_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for case_row in rows:
        family = str(case_row["family"])
        num_qubits = int(case_row["N"])
        qasm_path = resolve_repo_path(str(case_row["canonical_qasm3_path"]))
        if not qasm_path.is_file():
            raise FileNotFoundError(f"Canonical QASM file missing: {qasm_path}")

        _, execution_circuit, shared_metrics = load_canonical_input(qasm_path)
        print(
            f"[case] family={family} N={num_qubits} canonical_gate_count={shared_metrics['canonical_gate_count']} "
            f"execution_gate_count={shared_metrics['execution_gate_count']}",
            flush=True,
        )
        print(f"[run] family={family} backend=cudaq warmup={args.warmup} repeats={args.repeats}", flush=True)

        try:
            for warmup_index in range(args.warmup):
                backend_metrics = _run_iteration(circuit=execution_circuit, shots=args.shots, cudaq_mod=cudaq_mod)
                enforce_per_run_time_budget(
                    family=family,
                    backend="cudaq",
                    phase="warmup",
                    iteration_index=warmup_index,
                    backend_total_ms=float(backend_metrics["backend_total_ms"]),
                    time_budget_s=args.time_budget_s,
                )

            for repeat_index in range(args.repeats):
                backend_metrics = _run_iteration(circuit=execution_circuit, shots=args.shots, cudaq_mod=cudaq_mod)
                enforce_per_run_time_budget(
                    family=family,
                    backend="cudaq",
                    phase="repeat",
                    iteration_index=repeat_index,
                    backend_total_ms=float(backend_metrics["backend_total_ms"]),
                    time_budget_s=args.time_budget_s,
                )
                raw_rows.append(
                    {
                        "family": family,
                        "N": num_qubits,
                        "backend": "cudaq",
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
            print(f"[timeout] family={family} backend=cudaq error={row['error']}", flush=True)
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
            print(f"[error] family={family} backend=cudaq error={row['error']}", flush=True)

    write_run_outputs(out_dir, metadata_obj, raw_rows, errors)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
