#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

from run_common import (
    DEFAULT_RESULTS_ROOT,
    append_run_log,
    default_run_id,
    make_result_row,
    monitor_peak_usage,
    monitor_runner_protocol,
    write_csv,
)


LOW_BUCKET_BITS = 8
PATTERN_REPEATS = 4
DEFAULT_DIAG_IR_WORD_CAP = 6144
DEFAULT_N = 30
DEFAULT_THETA = 0.03125
SRC_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SRC_ROOT.parent
DEFAULT_CIRCUITS_ROOT = PROJECT_ROOT / "output" / "circuits"
DEFAULT_GATE_KINDS = ["p-low", "p-high", "cp-hh", "cp-hl", "cp-ll"]
DEFAULT_P_BATCH_SIZES = [1, 2, 4, 8, 16, 32, 64, 128]
DEFAULT_CP_BATCH_SIZES = [1, 2, 4, 8, 16, 32, 64, 128]
RUNNER_PREFIX = "runner: "


class Case:
    def __init__(self, gate_kind: str, batch_size: int) -> None:
        self.gate_kind = gate_kind
        self.batch_size = batch_size

    def circuit_name(self, n: int) -> str:
        if self.gate_kind == "empty":
            return f"p_batch_n{n}_empty_b0"
        return f"p_batch_n{n}_{self.gate_kind}_b{self.batch_size}"

    def circuit_dir_name(self) -> str:
        if self.gate_kind == "empty":
            return "p_batch_empty"
        return f"p_batch_{self.gate_kind.replace('-', '_')}"


def parse_csv_ints(text: str) -> list[int]:
    values: list[int] = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        value = int(part)
        if value < 0:
            raise ValueError("batch sizes must be non-negative")
        values.append(value)
    if not values:
        raise ValueError("at least one batch size is required")
    return sorted(dict.fromkeys(values))


def parse_gate_kinds(text: str) -> list[str]:
    allowed = set(DEFAULT_GATE_KINDS)
    values = [part.strip() for part in text.split(",") if part.strip()]
    if not values:
        raise ValueError("at least one gate kind is required")
    unsupported = sorted(set(values) - allowed)
    if unsupported:
        raise ValueError(f"unsupported gate kind(s): {unsupported}; supported={sorted(allowed)}")
    return values


def build_cases(gate_kinds: list[str], p_batch_sizes: list[int], cp_batch_sizes: list[int]) -> list[Case]:
    cases = [Case("empty", 0)]
    for gate_kind in gate_kinds:
        batch_sizes = p_batch_sizes if gate_kind.startswith("p-") else cp_batch_sizes
        for batch_size in batch_sizes:
            if batch_size == 0:
                continue
            cases.append(Case(gate_kind, batch_size))
    return cases


def pick_p_qubit(gate_kind: str, index: int, n: int) -> int:
    low_count = min(n, LOW_BUCKET_BITS)
    high_count = n - low_count
    if gate_kind == "p-low":
        if low_count == 0:
            raise ValueError("p-low requires n >= 1")
        return index % low_count
    if gate_kind == "p-high":
        if high_count <= 0:
            raise ValueError("p-high requires n > 8")
        return low_count + (index % high_count)
    raise ValueError(f"unsupported p gate kind: {gate_kind}")


def pick_cp_pair(gate_kind: str, index: int, n: int) -> tuple[int, int]:
    if n <= LOW_BUCKET_BITS:
        raise ValueError("cp microbenchmark requires n > 8 so that high-bucket qubits exist")
    low_count = min(n, LOW_BUCKET_BITS)
    high_count = n - low_count
    if gate_kind == "cp-ll":
        return index % low_count, (index + 1) % low_count
    if gate_kind == "cp-hh":
        return low_count + (index % high_count), low_count + ((index + 1) % high_count)
    if gate_kind == "cp-hl":
        return index % low_count, low_count + (index % high_count)
    raise ValueError(f"unsupported cp gate kind: {gate_kind}")


def build_circuit(*, n: int, gate_kind: str, batch_size: int, theta: float):
    from qiskit import QuantumCircuit

    circuit_name = Case(gate_kind, batch_size).circuit_name(n).replace("-", "_")
    circuit = QuantumCircuit(n, name=circuit_name)
    if gate_kind == "empty":
        if batch_size != 0:
            raise ValueError("empty p_batch case requires batch_size=0")
        return circuit

    for _ in range(PATTERN_REPEATS):
        circuit.barrier()
        if gate_kind.startswith("p-"):
            for index in range(batch_size):
                circuit.p(theta, pick_p_qubit(gate_kind, index, n))
            continue
        for index in range(batch_size):
            control, target = pick_cp_pair(gate_kind, index, n)
            circuit.cp(theta, control, target)
    return circuit


def export_circuit_qasm3(*, circuit: Any, circuits_root: Path, backend: str, case: Case, n: int) -> Path:
    from qiskit import qasm3

    out_dir = circuits_root / case.circuit_dir_name() / backend
    out_dir.mkdir(parents=True, exist_ok=True)
    qasm_path = out_dir / f"{case.circuit_name(n)}.qasm3"
    with qasm_path.open("w", encoding="utf-8") as f:
        qasm3.dump(circuit, f)
    return qasm_path


def build_sim(zxhsim: Any, *, circuit: Any, n: int) -> Any:
    from zxhsim import load_circuit_transpiled

    sim = zxhsim.ZXH(n, eager_expand_all=True)
    load_circuit_transpiled(sim, circuit)
    return sim

def run_execute_s(sim: Any) -> float:
    started_at = time.perf_counter()
    sim.execute()
    return time.perf_counter() - started_at


def emit_worker_message(payload: dict[str, Any]) -> None:
    print(f"{RUNNER_PREFIX}{json.dumps(payload)}", flush=True)


def run_worker(args: argparse.Namespace) -> int:
    os.environ["ZXHSIM_DIAG_IR_WORD_CAP"] = str(args.diag_ir_word_cap)
    case = Case(args.gate_kind, args.batch_size)
    circuit_name = case.circuit_name(args.n)
    try:
        import zxhsim  # type: ignore

        zxhsim.init()
        try:
            emit_worker_message(
                {
                    "kind": "ready",
                    "circuit": circuit_name,
                    "n": args.n,
                    "gate_kind": args.gate_kind,
                    "batch_size": args.batch_size,
                    "diag_ir_word_cap": args.diag_ir_word_cap,
                    "repeats": args.repeats,
                    "pattern_repeats": PATTERN_REPEATS,
                    "mode": "qiskit_eager_empty_full_raw",
                }
            )
            circuit = build_circuit(
                n=args.n,
                gate_kind=args.gate_kind,
                batch_size=args.batch_size,
                theta=args.theta,
            )
            export_circuit_qasm3(
                circuit=circuit,
                circuits_root=args.circuits_root,
                backend=args.backend,
                case=case,
                n=args.n,
            )
            sim = build_sim(zxhsim, circuit=circuit, n=args.n)

            times_s: list[float] = []
            for run_index in range(args.repeats):
                execute_s = run_execute_s(sim)
                times_s.append(execute_s)
                emit_worker_message(
                    {
                        "kind": "progress",
                        "circuit": circuit_name,
                        "phase": "run",
                        "index": run_index + 1,
                        "total": args.repeats,
                        "time": execute_s,
                    }
                )

            emit_worker_message(
                {
                    "kind": "result",
                    "circuit": circuit_name,
                    "status": "pass",
                    "times": times_s,
                    "sample_times": [None for _ in times_s],
                }
            )
            return 0
        finally:
            zxhsim.finalize()
    except Exception as exc:
        emit_worker_message(
            {
                "kind": "result",
                "circuit": circuit_name,
                "status": "error",
                "times": [],
                "sample_times": [],
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        return 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ZXH P/CP diagonal batch microbenchmark with the ADAE CSV format.")
    parser.add_argument("--backend", type=str, default="zxh", help="Result namespace; the installed zxhsim backend is used.")
    parser.add_argument("--results-root", type=Path, default=DEFAULT_RESULTS_ROOT)
    parser.add_argument("--circuits-root", type=Path, default=DEFAULT_CIRCUITS_ROOT)
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--timeout-s", type=float, default=900.0)
    parser.add_argument("--n", type=int, default=DEFAULT_N)
    parser.add_argument("--theta", type=float, default=DEFAULT_THETA)
    parser.add_argument("--diag-ir-word-cap", type=int, default=DEFAULT_DIAG_IR_WORD_CAP)
    parser.add_argument("--repeats", type=int, default=6)
    parser.add_argument("--gate-kinds", type=str, default=",".join(DEFAULT_GATE_KINDS))
    parser.add_argument("--p-batch-sizes", type=str, default=",".join(str(value) for value in DEFAULT_P_BATCH_SIZES))
    parser.add_argument("--cp-batch-sizes", type=str, default=",".join(str(value) for value in DEFAULT_CP_BATCH_SIZES))
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--gate-kind", type=str, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--batch-size", type=int, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.n <= 0:
        raise ValueError("n must be positive")
    if args.diag_ir_word_cap <= 0 or args.diag_ir_word_cap > DEFAULT_DIAG_IR_WORD_CAP:
        raise ValueError(f"diag-ir-word-cap must be in [1, {DEFAULT_DIAG_IR_WORD_CAP}]")
    if args.repeats <= 0:
        raise ValueError("repeats must be positive")
    if args.worker:
        if args.gate_kind is None or args.batch_size is None:
            raise ValueError("worker mode requires --gate-kind and --batch-size")
        if args.gate_kind != "empty":
            parse_gate_kinds(args.gate_kind)
        elif args.batch_size != 0:
            raise ValueError("empty worker case requires --batch-size 0")
    return args


def run_parent(args: argparse.Namespace) -> int:
    gate_kinds = parse_gate_kinds(args.gate_kinds)
    p_batch_sizes = parse_csv_ints(args.p_batch_sizes)
    cp_batch_sizes = parse_csv_ints(args.cp_batch_sizes)
    cases = build_cases(gate_kinds, p_batch_sizes, cp_batch_sizes)
    run_id = args.run_id or default_run_id(args.backend)
    result_name = "p_batch"
    suite_name = "p_batch"
    out_path = args.results_root / args.backend / run_id / f"{result_name}.csv"
    worker_script = Path(__file__).resolve()

    results: list[dict[str, str]] = []
    failures = 0
    started_at = time.perf_counter()

    for case in cases:
        circuit = case.circuit_name(args.n)
        cmd = [
            sys.executable,
            str(worker_script),
            "--worker",
            "--backend",
            args.backend,
            "--n",
            str(args.n),
            "--theta",
            str(args.theta),
            "--diag-ir-word-cap",
            str(args.diag_ir_word_cap),
            "--circuits-root",
            str(args.circuits_root),
            "--repeats",
            str(args.repeats),
            "--gate-kind",
            case.gate_kind,
            "--batch-size",
            str(case.batch_size),
        ]
        env = os.environ.copy()
        env["ZXHSIM_DIAG_IR_WORD_CAP"] = str(args.diag_ir_word_cap)
        proc = subprocess.Popen(
            cmd,
            text=True,
            bufsize=1,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        peaks = {"max_rss_mb": 0.0, "max_gpu_mem_mb": 0.0}
        stop_event = threading.Event()
        monitor_thread = threading.Thread(
            target=monitor_peak_usage,
            args=(proc.pid, stop_event, peaks),
            daemon=True,
        )
        monitor_thread.start()
        try:
            status, times_value, sample_times_value, detail = monitor_runner_protocol(
                proc=proc,
                timeout_s=args.timeout_s,
            )
        finally:
            stop_event.set()
            monitor_thread.join()

        if status != "pass":
            failures += 1
            results.append(
                make_result_row(
                    circuit,
                    times_value=None,
                    sample_times_value=None,
                    status=status,
                    peaks=peaks,
                )
            )
            print(
                f"[{status}] backend={args.backend} suite={suite_name} circuit={circuit} "
                f"repeats={args.repeats} detail={detail} "
                f"max_rss_mb={peaks['max_rss_mb']:.3f} max_gpu_mem_mb={peaks['max_gpu_mem_mb']:.3f}",
                flush=True,
            )
            continue

        results.append(
            make_result_row(
                circuit,
                times_value=times_value,
                sample_times_value=sample_times_value,
                status="pass",
                peaks=peaks,
            )
        )
        print(
            f"[pass] backend={args.backend} suite={suite_name} circuit={circuit} "
            f"repeats={args.repeats} num_samples={len(times_value or [])} "
            f"max_rss_mb={peaks['max_rss_mb']:.3f} max_gpu_mem_mb={peaks['max_gpu_mem_mb']:.3f}",
            flush=True,
        )

    write_csv(out_path, results)
    elapsed_s = time.perf_counter() - started_at
    append_run_log(
        results_root=args.results_root,
        script_name="run_p_batch.py",
        run_id=run_id,
        backend=args.backend,
        suite_name=suite_name,
        result_name=result_name,
        elapsed_s=elapsed_s,
        failures=failures,
        out_path=out_path,
        repeat_desc=(
            f"default={args.repeats};mode=qiskit_eager_empty_full_raw;pattern_repeats={PATTERN_REPEATS};"
            f"n={args.n};theta={args.theta};"
            f"diag_ir_word_cap={args.diag_ir_word_cap};gate_kinds={','.join(gate_kinds)};"
            f"p_batch_sizes={','.join(str(v) for v in p_batch_sizes)};"
            f"cp_batch_sizes={','.join(str(v) for v in cp_batch_sizes)}"
        ),
    )
    print(f"results_csv={out_path}", flush=True)
    print(f"wall_time_s={elapsed_s:.6f}", flush=True)
    return 1 if failures else 0


def main() -> int:
    args = parse_args()
    if args.worker:
        return run_worker(args)
    return run_parent(args)


if __name__ == "__main__":
    raise SystemExit(main())
