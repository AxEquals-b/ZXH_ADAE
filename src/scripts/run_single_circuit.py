#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from backend_registry import make_backend
from circuit_generator import DEFAULT_OUTPUT_ROOT, generate_case


RUNNER_PREFIX = "runner: "


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one circuit on one backend with repeated samples.")
    parser.add_argument("--backend", required=True, type=str)
    parser.add_argument("--suite", required=True, type=str)
    parser.add_argument("--family", required=True, type=str)
    parser.add_argument("--num-qubits", required=True, type=int)
    parser.add_argument("--circuits-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--repeats", type=int, default=6)
    parser.add_argument("--shots", type=int, default=1)
    return parser.parse_args()


def extract_sample_time(result) -> float | None:
    experiments = getattr(result, "results", None)
    if not experiments:
        return None

    metadata = getattr(experiments[0], "metadata", None)
    if isinstance(metadata, dict) and "sample_time" in metadata:
        return float(metadata["sample_time"])

    to_dict = getattr(result, "to_dict", None)
    if to_dict is not None:
        try:
            payload = to_dict()
            result_rows = payload.get("results", [])
            if result_rows:
                metadata = result_rows[0].get("metadata", {})
                if "sample_time" in metadata:
                    return float(metadata["sample_time"])
        except Exception:
            return None

    return None


def run_once(*, backend, circuit, shots: int) -> tuple[float, float | None]:
    t0 = time.perf_counter()
    job = backend.run(circuit, shots=shots)
    result = job.result()
    return time.perf_counter() - t0, extract_sample_time(result)


def emit_runner_message(payload: dict[str, Any]) -> None:
    print(f"{RUNNER_PREFIX}{json.dumps(payload)}", flush=True)


def main() -> int:
    args = parse_args()
    circuit_name = f"{args.family}_n{args.num_qubits}"

    try:
        backend = make_backend(args.backend)
        generated = generate_case(
            suite_name=args.suite,
            family=args.family,
            num_qubits=args.num_qubits,
            backend_name=args.backend,
            backend=backend,
            output_root=args.circuits_root,
        )
        circuit = generated.circuit
        emit_runner_message(
            {
                "kind": "ready",
                "circuit": circuit_name,
                "repeats": args.repeats,
                "shots": args.shots,
                "metadata": generated.manifest_row,
                "generation_timings": generated.timings,
            }
        )

        times_s: list[float] = []
        sample_times_s: list[float | None] = []
        for index in range(args.repeats):
            elapsed_s, sample_time_s = run_once(backend=backend, circuit=circuit, shots=args.shots)
            times_s.append(elapsed_s)
            sample_times_s.append(sample_time_s)
            emit_runner_message(
                {
                    "kind": "progress",
                    "circuit": circuit_name,
                    "phase": "run",
                    "index": index + 1,
                    "total": args.repeats,
                    "time": elapsed_s,
                    "sample_time": sample_time_s,
                }
            )

        emit_runner_message(
            {
                "kind": "result",
                "circuit": circuit_name,
                "status": "pass",
                "times": times_s,
                "sample_times": sample_times_s,
            }
        )
        return 0
    except Exception as exc:
        emit_runner_message(
            {
                "kind": "result",
                "circuit": circuit_name,
                "status": "error",
                "time": None,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
