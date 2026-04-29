#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from statistics import mean, stdev
import sys
import time
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
BENCH_ROOT = THIS_DIR.parent
REPO_ROOT = BENCH_ROOT.parent
TOOLS_DIR = REPO_ROOT / "tools"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(BENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCH_ROOT))
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from env_capture import capture_env, write_env
from stage import activate_python_stage


DIAG_IR_WORD_CAP_HARD_MAX = 6144
LOW_BUCKET_BITS = 8
COMPLEX_BYTES = 8
READ_WRITE_FACTOR = 2
DEFAULT_DIAGONAL_BATCH_SIZES = [0, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 3072, 4096, 6144]
BUCKET_ORDER: list[tuple[str, int]] = [
    ("p_l", 2),
    ("p_h", 2),
    ("p_x", 2),
    ("cp_ll", 3),
    ("cp_hh", 3),
    ("cp_hl", 3),
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Diagonal-window microbenchmark for ZXH-Sim. "
            "The benchmark uses direct ZXH API construction to avoid compile-time canonicalization, "
            "and isolates diagonal cost by subtracting a shared H^N header-only baseline."
        )
    )
    parser.add_argument("--backend", type=str, default="cuda", choices=["single", "omp", "cuda", "mpi", "mpi_omp", "mpi_cuda"])
    parser.add_argument("--n", type=int, default=30)
    parser.add_argument(
        "--gate-kind",
        type=str,
        default="rz",
        choices=["p", "p-low", "p-high", "rz", "rz-low", "rz-high", "cp-ll", "cp-hh", "cp-hl"],
        help=(
            "Logical diagonal gate family placed into one execute()-time diagonal window. "
            "`p/rz` cycle over all qubits, `p-low/high` and `rz-low/high` isolate P low/high buckets."
        ),
    )
    parser.add_argument(
        "--diagonal-batch-sizes",
        "--batch-sizes",
        dest="diagonal_batch_sizes",
        type=str,
        default=",".join(str(x) for x in DEFAULT_DIAGONAL_BATCH_SIZES),
        help="Comma-separated diagonal gate counts accumulated into one diagonal window.",
    )
    parser.add_argument(
        "--diag-ir-word-cap",
        type=int,
        default=DIAG_IR_WORD_CAP_HARD_MAX,
        help=(
            "Effective diagonal IR word cap used by the CUDA runtime chunk builder. "
            f"Must be in [1, {DIAG_IR_WORD_CAP_HARD_MAX}] and defaults to the hardware/runtime max."
        ),
    )
    parser.add_argument("--theta", type=float, default=0.03125)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Default: build/benchmarks/diag_batch_microbench_<backend>_<gate_kind>_n<n>_cap<cap>",
    )
    parser.add_argument("--stop-on-error", action="store_true")
    return parser.parse_args()


def _parse_batch_sizes(text: str) -> list[int]:
    out: list[int] = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        value = int(chunk)
        if value < 0:
            raise ValueError("diagonal batch sizes must be non-negative")
        out.append(value)
    if not out:
        raise ValueError("at least one diagonal batch size is required")
    return sorted(dict.fromkeys(out))


def _default_output_dir(backend: str, gate_kind: str, n: int, diag_ir_word_cap: int) -> Path:
    return (REPO_ROOT / "build" / "benchmarks" / f"diag_batch_microbench_{backend}_{gate_kind}_n{n}_cap{diag_ir_word_cap}").resolve()


def _relative_stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = mean(values)
    if mu <= 0.0:
        return 0.0
    return stdev(values) / mu


def _gate_words_per_desc(gate_kind: str) -> int:
    return 2 if gate_kind.startswith("rz") or gate_kind.startswith("p") else 3


def _state_vector_bytes(n: int) -> int:
    return (1 << n) * COMPLEX_BYTES


def _format_optional(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.6f}"


def _validate_diag_ir_word_cap(args: argparse.Namespace) -> None:
    if args.diag_ir_word_cap < 1 or args.diag_ir_word_cap > DIAG_IR_WORD_CAP_HARD_MAX:
        raise ValueError(f"diag-ir-word-cap must be in [1, {DIAG_IR_WORD_CAP_HARD_MAX}]")
    if args.backend not in {"cuda", "mpi_cuda"} and args.diag_ir_word_cap != DIAG_IR_WORD_CAP_HARD_MAX:
        raise ValueError("diag-ir-word-cap override is only supported on cuda/mpi_cuda backends")
    if args.diag_ir_word_cap < _gate_words_per_desc(args.gate_kind):
        raise ValueError("diag-ir-word-cap is too small to hold even one diagonal descriptor")


def _pick_cp_pair(gate_kind: str, idx: int, n: int) -> tuple[int, int]:
    if n <= LOW_BUCKET_BITS:
        raise ValueError("cp microbenchmark requires n > 8 so that high-bucket qubits exist")
    low_count = min(n, LOW_BUCKET_BITS)
    high_count = n - low_count
    if gate_kind == "cp-ll":
        control = idx % low_count
        target = (idx + 1) % low_count
        return control, target
    if gate_kind == "cp-hh":
        control = low_count + (idx % high_count)
        target = low_count + ((idx + 1) % high_count)
        return control, target
    if gate_kind == "cp-hl":
        control = idx % low_count
        target = low_count + (idx % high_count)
        return control, target
    raise ValueError(f"unsupported cp gate kind: {gate_kind}")


def _pick_p_like_qubit(gate_kind: str, idx: int, n: int) -> int:
    low_count = min(n, LOW_BUCKET_BITS)
    high_count = n - low_count
    if gate_kind in {"p", "rz"}:
        return idx % n
    if gate_kind in {"p-low", "rz-low"}:
        if low_count == 0:
            raise ValueError("p-low/rz-low requires n >= 1")
        return idx % low_count
    if gate_kind in {"p-high", "rz-high"}:
        if high_count <= 0:
            raise ValueError("p-high/rz-high requires n > 8")
        return low_count + (idx % high_count)
    raise ValueError(f"unsupported p-like gate kind: {gate_kind}")


def _build_sim(zxhsim, *, n: int, gate_kind: str, batch_size: int, theta: float):
    sim = zxhsim.ZXH(n)
    for q in range(n):
        sim.H(q)
    if gate_kind.startswith("p"):
        for idx in range(batch_size):
            sim.P(_pick_p_like_qubit(gate_kind, idx, n), theta)
        return sim
    if gate_kind.startswith("rz"):
        for idx in range(batch_size):
            sim.Rz(_pick_p_like_qubit(gate_kind, idx, n), theta)
        return sim
    for idx in range(batch_size):
        control, target = _pick_cp_pair(gate_kind, idx, n)
        sim.CP(control, target, theta)
    return sim


def _run_execute_ms_from_sim(sim) -> float:
    t0 = time.perf_counter()
    sim.execute()
    return (time.perf_counter() - t0) * 1000.0


def _measure_symmetric_pair_ms(header_sim, full_sim) -> dict[str, float]:
    header_before_ms = _run_execute_ms_from_sim(header_sim)
    full_after_header_ms = _run_execute_ms_from_sim(full_sim)
    full_before_header_ms = _run_execute_ms_from_sim(full_sim)
    header_after_ms = _run_execute_ms_from_sim(header_sim)

    header_execute_ms = 0.5 * (header_before_ms + header_after_ms)
    full_execute_ms = 0.5 * (full_after_header_ms + full_before_header_ms)
    diag_forward_ms = full_after_header_ms - header_before_ms
    diag_reverse_ms = full_before_header_ms - header_after_ms
    diag_execute_ms = max(0.0, 0.5 * (diag_forward_ms + diag_reverse_ms))

    return {
        "header_before_ms": header_before_ms,
        "full_after_header_ms": full_after_header_ms,
        "full_before_header_ms": full_before_header_ms,
        "header_after_ms": header_after_ms,
        "header_execute_ms": header_execute_ms,
        "full_execute_ms": full_execute_ms,
        "diag_forward_ms": diag_forward_ms,
        "diag_reverse_ms": diag_reverse_ms,
        "diag_execute_ms": diag_execute_ms,
    }


def _empty_bucket_counts() -> dict[str, int]:
    return {name: 0 for name, _ in BUCKET_ORDER}


def _expected_bucket_counts(gate_kind: str, batch_size: int, n: int) -> dict[str, int]:
    counts = _empty_bucket_counts()
    if batch_size <= 0:
        return counts

    if gate_kind in {"p", "rz"}:
        low_count = min(n, LOW_BUCKET_BITS)
        full_cycles, rem = divmod(batch_size, n)
        counts["p_l"] = full_cycles * low_count + min(rem, low_count)
        counts["p_h"] = batch_size - counts["p_l"]
        return counts
    if gate_kind in {"p-low", "rz-low"}:
        counts["p_l"] = batch_size
        return counts
    if gate_kind in {"p-high", "rz-high"}:
        if n <= LOW_BUCKET_BITS:
            raise ValueError("p-high/rz-high requires n > 8")
        counts["p_h"] = batch_size
        return counts
    if gate_kind == "cp-ll":
        counts["cp_ll"] = batch_size
        return counts
    if gate_kind == "cp-hh":
        counts["cp_hh"] = batch_size
        return counts
    if gate_kind == "cp-hl":
        counts["cp_hl"] = batch_size
        return counts
    raise ValueError(f"unsupported gate kind: {gate_kind}")


def _expected_total_words(bucket_counts: dict[str, int]) -> int:
    total = 0
    for name, words_per_desc in BUCKET_ORDER:
        total += bucket_counts[name] * words_per_desc
    return total


def _expected_chunk_count(bucket_counts: dict[str, int], diag_ir_word_cap: int) -> int:
    remaining = dict(bucket_counts)
    if not any(remaining.values()):
        return 0

    chunk_count = 0
    while any(remaining.values()):
        used_words = 0
        appended = False
        for name, words_per_desc in BUCKET_ORDER:
            while remaining[name] > 0 and used_words + words_per_desc <= diag_ir_word_cap:
                remaining[name] -= 1
                used_words += words_per_desc
                appended = True
        if not appended:
            raise ValueError("diag-ir-word-cap is too small for the current bucket mixture")
        chunk_count += 1
    return chunk_count


def _bucket_profile(bucket_counts: dict[str, int]) -> str:
    parts = [f"{name}={bucket_counts[name]}" for name, _ in BUCKET_ORDER if bucket_counts[name] > 0]
    return ",".join(parts) if parts else "empty"


def _summary_markdown(metadata: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# Diagonal Batch Microbenchmark",
        "",
        f"- backend: `{metadata['backend']}`",
        f"- n: `{metadata['n']}`",
        f"- nprocs: `{metadata['nprocs']}`",
        f"- gate_kind: `{metadata['gate_kind']}`",
        f"- theta: `{metadata['theta']}`",
        f"- warmup: `{metadata['warmup']}`",
        f"- repeats: `{metadata['repeats']}`",
        f"- direct_api: `{metadata['direct_api']}`",
        f"- diag_ir_word_cap: `{metadata['diag_ir_word_cap']}`",
        f"- diag_ir_word_cap_hard_max: `{metadata['diag_ir_word_cap_hard_max']}`",
        f"- local_state_vector_bytes: `{metadata['local_state_vector_bytes']}`",
        f"- complex_bytes: `{metadata['complex_bytes']}`",
        f"- rw_factor: `{metadata['rw_factor']}`",
        "",
        "| batch_size | chunks | total_words | bucket_profile | diag_ms | time_per_gate_us | bandwidth_gib_s | status |",
        "| ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['batch_size']} | {row['expected_chunk_count']} | {row['expected_total_words']} | "
            f"`{row['bucket_profile']}` | {_format_optional(row.get('diag_execute_ms_mean'))} | "
            f"{_format_optional(row.get('time_per_diagonal_gate_us'))} | "
            f"{_format_optional(row.get('effective_bandwidth_gib_s'))} | "
            f"{row['status']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    _validate_diag_ir_word_cap(args)
    batch_sizes = _parse_batch_sizes(args.diagonal_batch_sizes)
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else _default_output_dir(args.backend, args.gate_kind, args.n, args.diag_ir_word_cap)
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    if args.backend in {"cuda", "mpi_cuda"}:
        os.environ["ZXHSIM_DIAG_IR_WORD_CAP"] = str(args.diag_ir_word_cap)

    env_data = capture_env()
    write_env(output_dir / "env.json", env_data)

    activate_python_stage(REPO_ROOT, args.backend)
    import zxhsim  # type: ignore

    raw_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    zxhsim.init()
    try:
        nprocs = int(zxhsim.nprocs())
        global_state_bytes = _state_vector_bytes(args.n)
        local_state_bytes = global_state_bytes // max(1, nprocs)
        metadata: dict[str, Any] = {
            "backend": args.backend,
            "n": args.n,
            "nprocs": nprocs,
            "gate_kind": args.gate_kind,
            "theta": args.theta,
            "warmup": args.warmup,
            "repeats": args.repeats,
            "diagonal_batch_sizes": batch_sizes,
            "direct_api": True,
            "header_definition": "H applied to every qubit once, followed by one diagonal window",
            "diag_ir_word_cap": args.diag_ir_word_cap,
        "diag_ir_word_cap_hard_max": DIAG_IR_WORD_CAP_HARD_MAX,
        "complex_bytes": COMPLEX_BYTES,
        "rw_factor": READ_WRITE_FACTOR,
        "global_state_vector_bytes": global_state_bytes,
        "local_state_vector_bytes": local_state_bytes,
        "measurement_mode": "symmetric_pair_hf_fh",
        "bandwidth_definition": "expected_chunk_count * local_state_vector_bytes * rw_factor / diag_execute_time",
        "time_per_gate_definition": "diag_execute_ms_mean / batch_size",
        "note": (
            "This benchmark bypasses compile-time canonicalization by constructing the circuit through the direct ZXH API. "
            "Execute-time optimizations remain active: the H^N header is still handled by the current U3 path, and diagonal gates "
            "are still bucketed and chunked by the runtime CUDA diagonal implementation. Each sample uses a symmetric "
            "H->F->F->H measurement pattern to cancel first-vs-second execute order bias."
        ),
    }
        chunk_bytes = local_state_bytes * READ_WRITE_FACTOR

        for batch_size in batch_sizes:
            header_ms_samples: list[float] = []
            full_ms_samples: list[float] = []
            diag_ms_samples: list[float] = []
            diag_forward_ms_samples: list[float] = []
            diag_reverse_ms_samples: list[float] = []
            bucket_counts = _expected_bucket_counts(args.gate_kind, batch_size, args.n)
            expected_total_words = _expected_total_words(bucket_counts)
            expected_chunks = _expected_chunk_count(bucket_counts, args.diag_ir_word_cap)
            bucket_profile = _bucket_profile(bucket_counts)

            status = "pass"
            error = ""

            try:
                header_sim = _build_sim(zxhsim, n=args.n, gate_kind=args.gate_kind, batch_size=0, theta=args.theta)
                full_sim = _build_sim(zxhsim, n=args.n, gate_kind=args.gate_kind, batch_size=batch_size, theta=args.theta)
                total_runs = args.warmup + args.repeats
                for run_index in range(total_runs):
                    phase = "warmup" if run_index < args.warmup else "measure"
                    sample = _measure_symmetric_pair_ms(header_sim, full_sim)
                    header_ms = sample["header_execute_ms"]
                    full_ms = sample["full_execute_ms"]
                    diag_ms = 0.0 if batch_size == 0 else sample["diag_execute_ms"]

                    raw_row = {
                        "backend": args.backend,
                        "n": args.n,
                        "nprocs": nprocs,
                        "gate_kind": args.gate_kind,
                        "theta": args.theta,
                        "diag_ir_word_cap": args.diag_ir_word_cap,
                        "batch_size": batch_size,
                        "phase": phase,
                        "run_index": run_index if phase == "warmup" else run_index - args.warmup,
                        "header_before_ms": sample["header_before_ms"],
                        "full_after_header_ms": sample["full_after_header_ms"],
                        "full_before_header_ms": sample["full_before_header_ms"],
                        "header_after_ms": sample["header_after_ms"],
                        "header_execute_ms": header_ms,
                        "full_execute_ms": full_ms,
                        "diag_forward_ms": sample["diag_forward_ms"],
                        "diag_reverse_ms": sample["diag_reverse_ms"],
                        "diag_execute_ms": diag_ms,
                        "expected_total_words": expected_total_words,
                        "expected_chunk_count": expected_chunks,
                        "local_state_vector_bytes": local_state_bytes,
                        "chunk_bytes": chunk_bytes,
                        "total_logical_rw_bytes": chunk_bytes * expected_chunks,
                        "bucket_p_l": bucket_counts["p_l"],
                        "bucket_p_h": bucket_counts["p_h"],
                        "bucket_p_x": bucket_counts["p_x"],
                        "bucket_cp_ll": bucket_counts["cp_ll"],
                        "bucket_cp_hh": bucket_counts["cp_hh"],
                        "bucket_cp_hl": bucket_counts["cp_hl"],
                        "bucket_profile": bucket_profile,
                        "status": "pass",
                        "error": "",
                    }
                    raw_rows.append(raw_row)

                    if phase == "measure":
                        header_ms_samples.append(header_ms)
                        full_ms_samples.append(full_ms)
                        diag_ms_samples.append(diag_ms)
                        diag_forward_ms_samples.append(sample["diag_forward_ms"])
                        diag_reverse_ms_samples.append(sample["diag_reverse_ms"])

                time_per_gate_us = None
                effective_bandwidth_gib_s = None
                if batch_size > 0 and diag_ms_samples:
                    diag_mean_ms = mean(diag_ms_samples)
                    if diag_mean_ms > 0.0:
                        time_per_gate_us = (diag_mean_ms * 1000.0) / batch_size
                        effective_bandwidth_gib_s = ((chunk_bytes * expected_chunks) / (diag_mean_ms / 1000.0)) / (1024**3)

                summary_rows.append(
                    {
                        "backend": args.backend,
                        "n": args.n,
                        "nprocs": nprocs,
                        "gate_kind": args.gate_kind,
                        "theta": args.theta,
                        "diag_ir_word_cap": args.diag_ir_word_cap,
                        "batch_size": batch_size,
                        "expected_words_per_gate": _gate_words_per_desc(args.gate_kind),
                        "expected_total_words": expected_total_words,
                        "expected_chunk_count": expected_chunks,
                        "global_state_vector_bytes": global_state_bytes,
                        "local_state_vector_bytes": local_state_bytes,
                        "chunk_bytes": chunk_bytes,
                        "total_logical_rw_bytes": chunk_bytes * expected_chunks,
                        "bucket_p_l": bucket_counts["p_l"],
                        "bucket_p_h": bucket_counts["p_h"],
                        "bucket_p_x": bucket_counts["p_x"],
                        "bucket_cp_ll": bucket_counts["cp_ll"],
                        "bucket_cp_hh": bucket_counts["cp_hh"],
                        "bucket_cp_hl": bucket_counts["cp_hl"],
                        "bucket_profile": bucket_profile,
                        "header_execute_ms_mean": mean(header_ms_samples) if header_ms_samples else None,
                        "header_execute_ms_stdev": stdev(header_ms_samples) if len(header_ms_samples) >= 2 else 0.0,
                        "full_execute_ms_mean": mean(full_ms_samples) if full_ms_samples else None,
                        "full_execute_ms_stdev": stdev(full_ms_samples) if len(full_ms_samples) >= 2 else 0.0,
                        "diag_execute_ms_mean": mean(diag_ms_samples) if diag_ms_samples else None,
                        "diag_execute_ms_stdev": stdev(diag_ms_samples) if len(diag_ms_samples) >= 2 else 0.0,
                        "diag_execute_ms_rsd_pct": _relative_stddev(diag_ms_samples) * 100.0 if diag_ms_samples else 0.0,
                        "diag_forward_ms_mean": mean(diag_forward_ms_samples) if diag_forward_ms_samples else None,
                        "diag_reverse_ms_mean": mean(diag_reverse_ms_samples) if diag_reverse_ms_samples else None,
                        "time_per_diagonal_gate_us": time_per_gate_us,
                        "effective_bandwidth_gib_s": effective_bandwidth_gib_s,
                        "status": status,
                        "error": error,
                    }
                )
            except Exception as exc:
                status = "error"
                error = f"{type(exc).__name__}: {exc}"
                summary_rows.append(
                    {
                        "backend": args.backend,
                        "n": args.n,
                        "nprocs": nprocs,
                        "gate_kind": args.gate_kind,
                        "theta": args.theta,
                        "diag_ir_word_cap": args.diag_ir_word_cap,
                        "batch_size": batch_size,
                        "expected_words_per_gate": _gate_words_per_desc(args.gate_kind),
                        "expected_total_words": expected_total_words,
                        "expected_chunk_count": expected_chunks,
                        "global_state_vector_bytes": global_state_bytes,
                        "local_state_vector_bytes": local_state_bytes,
                        "chunk_bytes": chunk_bytes,
                        "total_logical_rw_bytes": chunk_bytes * expected_chunks,
                        "bucket_p_l": bucket_counts["p_l"],
                        "bucket_p_h": bucket_counts["p_h"],
                        "bucket_p_x": bucket_counts["p_x"],
                        "bucket_cp_ll": bucket_counts["cp_ll"],
                        "bucket_cp_hh": bucket_counts["cp_hh"],
                        "bucket_cp_hl": bucket_counts["cp_hl"],
                        "bucket_profile": bucket_profile,
                        "header_execute_ms_mean": None,
                        "header_execute_ms_stdev": 0.0,
                        "full_execute_ms_mean": None,
                        "full_execute_ms_stdev": 0.0,
                        "diag_execute_ms_mean": None,
                        "diag_execute_ms_stdev": 0.0,
                        "diag_execute_ms_rsd_pct": 0.0,
                        "diag_forward_ms_mean": None,
                        "diag_reverse_ms_mean": None,
                        "time_per_diagonal_gate_us": None,
                        "effective_bandwidth_gib_s": None,
                        "status": status,
                        "error": error,
                    }
                )
                errors.append({"batch_size": batch_size, "status": status, "error": error})
                print(f"[ERROR] batch_size={batch_size} cap={args.diag_ir_word_cap}: {error}", flush=True)
                if args.stop_on_error:
                    break
                continue

            diag_mean_text = "n/a"
            bw_text = "n/a"
            if summary_rows[-1]["diag_execute_ms_mean"] is not None:
                diag_mean_text = f"{summary_rows[-1]['diag_execute_ms_mean']:.6f}"
            if summary_rows[-1]["effective_bandwidth_gib_s"] is not None:
                bw_text = f"{summary_rows[-1]['effective_bandwidth_gib_s']:.6f}"
            print(
                f"[PASS] batch_size={batch_size} cap={args.diag_ir_word_cap} chunks={expected_chunks} "
                f"bucket={bucket_profile} diag_ms={diag_mean_text} bw_gib_s={bw_text}",
                flush=True,
            )
    finally:
        zxhsim.finalize()

    raw_report = {
        "metadata": metadata,
        "env_id": env_data["env_id"],
        "rows": raw_rows,
        "errors": errors,
    }
    summary_report = {
        "metadata": metadata,
        "env_id": env_data["env_id"],
        "rows": summary_rows,
        "errors": errors,
    }

    (output_dir / "raw.json").write_text(json.dumps(raw_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "summary.json").write_text(json.dumps(summary_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    raw_fieldnames = [
        "backend",
        "n",
        "nprocs",
        "gate_kind",
        "theta",
        "diag_ir_word_cap",
        "batch_size",
        "phase",
        "run_index",
        "header_before_ms",
        "full_after_header_ms",
        "full_before_header_ms",
        "header_after_ms",
        "header_execute_ms",
        "full_execute_ms",
        "diag_forward_ms",
        "diag_reverse_ms",
        "diag_execute_ms",
        "expected_total_words",
        "expected_chunk_count",
        "local_state_vector_bytes",
        "chunk_bytes",
        "total_logical_rw_bytes",
        "bucket_p_l",
        "bucket_p_h",
        "bucket_p_x",
        "bucket_cp_ll",
        "bucket_cp_hh",
        "bucket_cp_hl",
        "bucket_profile",
        "status",
        "error",
    ]
    summary_fieldnames = [
        "backend",
        "n",
        "nprocs",
        "gate_kind",
        "theta",
        "diag_ir_word_cap",
        "batch_size",
        "expected_words_per_gate",
        "expected_total_words",
        "expected_chunk_count",
        "global_state_vector_bytes",
        "local_state_vector_bytes",
        "chunk_bytes",
        "total_logical_rw_bytes",
        "bucket_p_l",
        "bucket_p_h",
        "bucket_p_x",
        "bucket_cp_ll",
        "bucket_cp_hh",
        "bucket_cp_hl",
        "bucket_profile",
        "header_execute_ms_mean",
        "header_execute_ms_stdev",
        "full_execute_ms_mean",
        "full_execute_ms_stdev",
        "diag_execute_ms_mean",
        "diag_execute_ms_stdev",
        "diag_execute_ms_rsd_pct",
        "diag_forward_ms_mean",
        "diag_reverse_ms_mean",
        "time_per_diagonal_gate_us",
        "effective_bandwidth_gib_s",
        "status",
        "error",
    ]

    def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    _write_csv(output_dir / "raw.csv", raw_rows, raw_fieldnames)
    _write_csv(output_dir / "summary.csv", summary_rows, summary_fieldnames)
    (output_dir / "summary.md").write_text(_summary_markdown(metadata, summary_rows) + "\n", encoding="utf-8")

    print(f"summary_json={output_dir / 'summary.json'}")
    print(f"summary_csv={output_dir / 'summary.csv'}")
    print(f"summary_md={output_dir / 'summary.md'}")
    print(f"env_json={output_dir / 'env.json'}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
