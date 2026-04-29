#!/usr/bin/env python3
"""Run OpenQASM circuits with ZXH-Sim using Qiskit as parser.

Modes:
1. Single circuit:
   python examples/python/driver_qasm.py --qasm path/to/foo.qasm
2. Circuit list (default):
   python examples/python/driver_qasm.py --list examples/python/qasm_circuits/circuit_lists.txt
"""

from __future__ import annotations

import argparse
from pathlib import Path
import time

import zxhsim
from zxhsim.qasm import load_circuit, load_qasm, sample_counts


def _load_circuit_list(list_file: Path, qasm_root: Path) -> list[Path]:
    if not list_file.is_file():
        raise FileNotFoundError(f"Circuit list file not found: {list_file}")

    circuits: list[Path] = []
    with list_file.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            qasm_path = qasm_root / line
            if not qasm_path.is_file():
                raise FileNotFoundError(
                    f"{list_file}:{lineno}: qasm file not found: {line} (resolved: {qasm_path})"
                )
            circuits.append(qasm_path)

    if not circuits:
        raise ValueError(f"No circuit entries found in {list_file}")
    return circuits


def _run_one_circuit(
    qasm_file: Path, shots: int, opt_level: int, print_circuit: bool
) -> tuple[dict[str, int], float, float, float]:
    t_total_start = time.perf_counter()
    circuit = load_qasm(qasm_file)
    if print_circuit:
        print(circuit)

    sim = zxhsim.ZXH(circuit.num_qubits)
    t_compile_start = time.perf_counter()
    load_circuit(sim, circuit, optimize_level=opt_level)
    compile_time_s = time.perf_counter() - t_compile_start
    t0 = time.perf_counter()
    sim.execute()
    execute_time_s = time.perf_counter() - t0
    samples = sim.Sampling(shots)
    total_time_s = time.perf_counter() - t_total_start
    return dict(sample_counts(samples)), compile_time_s, execute_time_s, total_time_s


def main() -> None:
    zxhsim.init()
    default_root = Path(__file__).resolve().parent / "qasm_circuits"
    default_list = default_root / "circuit_lists.txt"

    parser = argparse.ArgumentParser(description="Run QASM with ZXH-Sim via Qiskit parser")
    parser.add_argument("--qasm", type=Path, default=None, help="Run a single OpenQASM file")
    parser.add_argument(
        "--list",
        type=Path,
        default=default_list,
        help="Circuit list file; one relative qasm path per line (default: qasm_circuits/circuit_lists.txt)",
    )
    parser.add_argument(
        "--qasm-root",
        type=Path,
        default=default_root,
        help="Root directory used to resolve entries in --list",
    )
    parser.add_argument("--shots", type=int, default=1024, help="Number of shots")
    parser.add_argument(
        "--opt-level",
        type=int,
        default=1,
        choices=[0, 1, 2, 3],
        help="Qiskit transpile optimization level",
    )
    parser.add_argument(
        "--print-circuit",
        action="store_true",
        help="Print loaded circuit before execution",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately when one listed circuit fails",
    )
    args = parser.parse_args()

    if args.shots <= 0:
        raise ValueError("--shots must be positive")

    # Single-file mode preserves previous output behavior.
    if args.qasm is not None:
        if not args.qasm.is_file():
            raise FileNotFoundError(f"QASM file not found: {args.qasm}")
        counts, compile_time_s, execute_time_s, total_time_s = _run_one_circuit(
            args.qasm, args.shots, args.opt_level, args.print_circuit
        )
        for bitstr, cnt in sorted(counts.items()):
            print(f"{bitstr}: {cnt}")
        print(f"compile_time_s: {compile_time_s:.6f}")
        print(f"execute_time_s: {execute_time_s:.6f}")
        print(f"total_time_s: {total_time_s:.6f}")
        return

    # List mode: read default/assigned circuit list.
    qasm_root = args.qasm_root.resolve()
    circuits = _load_circuit_list(args.list, qasm_root)
    total = len(circuits)
    passed = 0
    failed = 0

    for idx, qasm_file in enumerate(circuits, start=1):
        rel = qasm_file.relative_to(qasm_root)
        try:
            counts, compile_time_s, execute_time_s, total_time_s = _run_one_circuit(
                qasm_file, args.shots, args.opt_level, args.print_circuit
            )
            passed += 1
            print(
                f"[{idx}/{total}] [OK] {rel} unique_states={len(counts)} "
                f"compile_time_s={compile_time_s:.6f} "
                f"execute_time_s={execute_time_s:.6f} "
                f"total_time_s={total_time_s:.6f}"
            )
        except Exception as exc:
            failed += 1
            print(f"[{idx}/{total}] [FAIL] {rel}: {exc}")
            if args.stop_on_error:
                raise

    print(f"Summary: total={total}, passed={passed}, failed={failed}")
    if failed > 0:
        raise SystemExit(1)


if __name__ == "__main__":
    try:
        main()
    finally:
        zxhsim.finalize()
