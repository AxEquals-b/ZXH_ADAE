#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from importlib import metadata
from pathlib import Path
from statistics import mean
from typing import Any

from qiskit import qasm3


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from benchmarks.stage import activate_python_stage
from benchmarks.ADAE.prepare.generators.mqt_workflow.canonical_ir import CANONICAL_QASM_GATES


ADAE_ROOT = REPO_ROOT / "benchmarks" / "ADAE"
RESULTS_ROOT = ADAE_ROOT / "results"
RUNS_ROOT = RESULTS_ROOT / "run" / "representative_cuda"
DEFAULT_MANIFEST = RESULTS_ROOT / "prepare" / "workflow" / "03_pass3_canonicalize" / "canonical_manifest.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the 29 ADAE representative workloads on cuQuantum, ZXH, DDSIM, and qblaze."
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Path to the canonical representative manifest.",
    )
    parser.add_argument(
        "--backend",
        action="append",
        choices=["cudaq", "zxh-cuda", "ddsim", "qblaze"],
        default=[],
        help="Backend to run. Repeat this flag to select multiple backends. Default: cuQuantum + ZXH.",
    )
    parser.add_argument(
        "--family",
        action="append",
        default=[],
        help="Only run the selected family names. Repeat this flag to select multiple families.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only run the first N selected cases. Useful for incremental testing.",
    )
    parser.add_argument("--warmup", type=int, default=4, help="Warmup iterations per case/backend.")
    parser.add_argument("--repeats", type=int, default=8, help="Measured iterations per case/backend.")
    parser.add_argument(
        "--shots",
        type=int,
        default=1,
        help="Shot count used for both cudaq.sample(...) and ZXH Sampling(...).",
    )
    parser.add_argument(
        "--cudaq-target",
        type=str,
        default="nvidia",
        help="CUDA-Q target name. Default: nvidia.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional output directory name under benchmarks/ADAE/results/run/representative_cuda/.",
    )
    parser.add_argument(
        "--stop-on-error",
        action="store_true",
        help="Stop immediately when a backend/case run fails.",
    )
    return parser.parse_args()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


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


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def _load_manifest_rows(path: Path) -> list[dict[str, Any]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    rows = list(obj.get("rows", []))
    if not rows:
        raise RuntimeError(f"No rows found in manifest: {path}")
    return rows


def _purge_modules(prefix: str) -> None:
    doomed = [name for name in sys.modules if name == prefix or name.startswith(prefix + ".")]
    for name in doomed:
        del sys.modules[name]


def _load_zxh_cuda_modules():
    stage_dir = activate_python_stage(REPO_ROOT, "cuda")
    _purge_modules("zxhsim")
    zxhsim = importlib.import_module("zxhsim")
    qasm_mod = importlib.import_module("zxhsim.qasm")
    return stage_dir, zxhsim, qasm_mod


def _load_cudaq_modules(target_name: str):
    import cudaq

    cudaq.set_target(target_name)
    return cudaq


def _load_ddsim_backend():
    import mqt.ddsim as ddsim

    provider = ddsim.DDSIMProvider()
    return provider.get_backend("qasm_simulator")


def _load_qblaze_backend():
    from qblaze.qiskit import Backend

    return Backend()


def _load_canonical_input(qasm_path: Path) -> tuple[Any, Any, dict[str, Any]]:
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


def _compile_canonical_to_cudaq_kernel(circuit, cudaq_mod):
    # Syntax adaptation only: canonical QASM is translated gate-by-gate into
    # the CUDA-Q kernel API without any extra transpile or basis lowering.
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
            kernel.r1(params[0], qubits[qargs[0]], qubits[qargs[1]])
            continue

        raise ValueError(f"Gate '{name}' is not supported by the canonical CUDA-Q runner.")

    return kernel


def _run_cudaq_once(*, circuit, shots: int, cudaq_mod) -> dict[str, Any]:
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


def _run_zxh_once(*, circuit, shots: int, zxhsim_mod, qasm_mod) -> dict[str, Any]:
    zxhsim_mod.init()
    try:
        sim = zxhsim_mod.ZXH(circuit.num_qubits)

        t0 = time.perf_counter()
        qasm_mod.load_circuit_transpiled(sim, circuit)
        compile_ms = (time.perf_counter() - t0) * 1000.0

        t1 = time.perf_counter()
        sim.execute()
        execute_ms = (time.perf_counter() - t1) * 1000.0

        t2 = time.perf_counter()
        samples = sim.Sampling(shots)
        sample_ms = (time.perf_counter() - t2) * 1000.0
        observed_outcomes = len(samples)
    finally:
        zxhsim_mod.finalize()

    return {
        "kernel_build_ms": compile_ms,
        "execute_ms": execute_ms,
        "sample_ms": sample_ms,
        "backend_total_ms": compile_ms + execute_ms + sample_ms,
        "observed_outcomes": observed_outcomes,
    }


def _run_ddsim_once(*, circuit, shots: int, ddsim_backend) -> dict[str, Any]:
    t0 = time.perf_counter()
    result = ddsim_backend.run(circuit, shots=shots).result()
    execute_ms = (time.perf_counter() - t0) * 1000.0
    observed_outcomes = len(result.get_counts())
    return {
        "kernel_build_ms": 0.0,
        "execute_ms": execute_ms,
        "sample_ms": 0.0,
        "backend_total_ms": execute_ms,
        "observed_outcomes": observed_outcomes,
    }


def _run_qblaze_once(*, circuit, shots: int, qblaze_backend) -> dict[str, Any]:
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


def _measured_end_to_end_ms(*, execute_ms: float, sample_ms: float) -> float:
    return execute_ms + sample_ms


def _summary_markdown(summary_rows: list[dict[str, Any]], metadata_obj: dict[str, Any]) -> str:
    lines = [
        "# Representative CUDA Benchmark Summary",
        "",
        f"- run_id: `{metadata_obj['run_id']}`",
        f"- manifest: `{metadata_obj['manifest_path']}`",
        f"- selected_backends: `{metadata_obj['selected_backends']}`",
        f"- warmup: `{metadata_obj['warmup']}`",
        f"- repeats: `{metadata_obj['repeats']}`",
        f"- shots: `{metadata_obj['shots']}`",
        f"- input_mode: `{metadata_obj['input_mode']}`",
        f"- canonical_gate_set: `{metadata_obj['canonical_gate_set']}`",
        "",
        "| family | N | backend | repeats | mean_end_to_end_ms | status |",
        "| --- | ---: | --- | ---: | ---: | --- |",
    ]
    for row in summary_rows:
        lines.append(
            "| {family} | {N} | {backend} | {repeats} | {end_to_end_ms_mean:.3f} | {status} |".format(
                **row
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    if not os.environ.get("CUDA_VISIBLE_DEVICES"):
        os.environ["CUDA_VISIBLE_DEVICES"] = "0"

    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = (REPO_ROOT / manifest_path).resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(
            f"Manifest not found: {manifest_path}. Run `python benchmarks/ADAE/prepare/generators/generate_all.py` first "
            "or pass --manifest explicitly."
        )

    rows = _load_manifest_rows(manifest_path)
    if args.family:
        selected = set(args.family)
        rows = [row for row in rows if str(row["family"]) in selected]
    rows = sorted(rows, key=lambda row: (int(row.get("N", 0)), str(row["family"])))
    if args.limit is not None:
        rows = rows[: args.limit]
    if not rows:
        raise RuntimeError("No benchmark cases were selected.")

    backends = args.backend or ["cudaq", "zxh-cuda"]
    run_id = args.run_id or f"representative_cuda_{_timestamp()}"
    out_dir = RUNS_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata_obj: dict[str, Any] = {
        "run_id": run_id,
        "manifest_path": _repo_rel(manifest_path),
        "selected_backends": backends,
        "selected_families": [row["family"] for row in rows],
        "warmup": args.warmup,
        "repeats": args.repeats,
        "shots": args.shots,
        "cudaq_target": args.cudaq_target,
        "input_mode": "canonical_qasm3_strict",
        "canonical_gate_set": list(CANONICAL_QASM_GATES),
        "python_version": sys.version,
        "qiskit_version": metadata.version("qiskit"),
    }
    try:
        metadata_obj["cudaq_version"] = metadata.version("cudaq")
    except metadata.PackageNotFoundError:
        pass
    try:
        metadata_obj["mqt_ddsim_version"] = metadata.version("mqt.ddsim")
    except metadata.PackageNotFoundError:
        pass
    try:
        metadata_obj["qblaze_version"] = metadata.version("qblaze")
    except metadata.PackageNotFoundError:
        pass

    cudaq_mod = None
    if "cudaq" in backends:
        cudaq_mod = _load_cudaq_modules(args.cudaq_target)

    zxhsim_mod = None
    zxh_qasm_mod = None
    if "zxh-cuda" in backends:
        stage_dir, zxhsim_mod, zxh_qasm_mod = _load_zxh_cuda_modules()
        metadata_obj["zxh_cuda_stage_dir"] = _repo_rel(stage_dir)

    ddsim_backend = None
    if "ddsim" in backends:
        ddsim_backend = _load_ddsim_backend()

    qblaze_backend = None
    if "qblaze" in backends:
        qblaze_backend = _load_qblaze_backend()

    raw_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for case_row in rows:
        family = str(case_row["family"])
        num_qubits = int(case_row["N"])
        qasm_path = _resolve_repo_path(str(case_row["canonical_qasm3_path"]))
        if not qasm_path.is_file():
            raise FileNotFoundError(f"Canonical QASM file missing: {qasm_path}")

        canonical_circuit, execution_circuit, shared_metrics = _load_canonical_input(qasm_path)
        print(
            f"[case] family={family} N={num_qubits} canonical_gate_count={shared_metrics['canonical_gate_count']} "
            f"execution_gate_count={shared_metrics['execution_gate_count']}"
        )

        for backend in backends:
            print(f"[run] family={family} backend={backend} warmup={args.warmup} repeats={args.repeats}")
            runner = None
            runner_kwargs: dict[str, Any] = {}
            if backend == "cudaq":
                runner = _run_cudaq_once
                runner_kwargs = {
                    "cudaq_mod": cudaq_mod,
                }
            elif backend == "zxh-cuda":
                runner = _run_zxh_once
                runner_kwargs = {
                    "zxhsim_mod": zxhsim_mod,
                    "qasm_mod": zxh_qasm_mod,
                }
            elif backend == "ddsim":
                runner = _run_ddsim_once
                runner_kwargs = {
                    "ddsim_backend": ddsim_backend,
                }
            elif backend == "qblaze":
                runner = _run_qblaze_once
                runner_kwargs = {
                    "qblaze_backend": qblaze_backend,
                }
            else:  # pragma: no cover
                raise ValueError(f"Unsupported backend: {backend}")

            try:
                backend_circuit = execution_circuit if backend in {"cudaq", "zxh-cuda"} else canonical_circuit

                for _ in range(args.warmup):
                    runner(circuit=backend_circuit, shots=args.shots, **runner_kwargs)

                for repeat_index in range(args.repeats):
                    backend_metrics = runner(circuit=backend_circuit, shots=args.shots, **runner_kwargs)
                    raw_rows.append(
                        {
                            "family": family,
                            "N": num_qubits,
                            "backend": backend,
                            "repeat_index": repeat_index,
                            "qasm_path": _repo_rel(qasm_path),
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
                            "end_to_end_ms": _measured_end_to_end_ms(
                                execute_ms=backend_metrics["execute_ms"],
                                sample_ms=backend_metrics["sample_ms"],
                            ),
                            "observed_outcomes": backend_metrics["observed_outcomes"],
                            "status": "pass",
                            "error": "",
                        }
                    )
            except Exception as exc:
                error_row = {
                    "family": family,
                    "N": num_qubits,
                    "backend": backend,
                    "repeat_index": -1,
                    "qasm_path": _repo_rel(qasm_path),
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
                    "status": "error",
                    "error": f"{type(exc).__name__}: {exc}",
                }
                raw_rows.append(error_row)
                errors.append(error_row)
                print(f"[error] family={family} backend={backend} error={error_row['error']}")
                if args.stop_on_error:
                    break
        if errors and args.stop_on_error:
            break

    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    for row in raw_rows:
        grouped[(row["family"], int(row["N"]), row["backend"])].append(row)

    summary_rows: list[dict[str, Any]] = []
    for (family, num_qubits, backend), bucket in sorted(grouped.items()):
        passed = [row for row in bucket if row["status"] == "pass"]
        status = "pass" if len(passed) == len(bucket) else "error"
        summary_rows.append(
            {
                "family": family,
                "N": num_qubits,
                "backend": backend,
                "repeats": len(passed),
                "end_to_end_ms_mean": mean(row["end_to_end_ms"] for row in passed) if passed else 0.0,
                "kernel_build_ms_mean": mean(row["kernel_build_ms"] for row in passed) if passed else 0.0,
                "execute_ms_mean": mean(row["execute_ms"] for row in passed) if passed else 0.0,
                "sample_ms_mean": mean(row["sample_ms"] for row in passed) if passed else 0.0,
                "status": status,
            }
        )

    raw_json_path = out_dir / "raw_results.json"
    raw_csv_path = out_dir / "raw_results.csv"
    summary_json_path = out_dir / "summary.json"
    summary_csv_path = out_dir / "summary.csv"
    summary_md_path = out_dir / "summary.md"

    _write_json(
        raw_json_path,
        {
            "metadata": metadata_obj,
            "rows": raw_rows,
        },
    )
    _write_csv(
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
    _write_json(
        summary_json_path,
        {
            "metadata": metadata_obj,
            "rows": summary_rows,
            "errors": errors,
        },
    )
    _write_csv(
        summary_csv_path,
        summary_rows,
        [
            "family",
            "N",
            "backend",
            "repeats",
            "end_to_end_ms_mean",
            "kernel_build_ms_mean",
            "execute_ms_mean",
            "sample_ms_mean",
            "status",
        ],
    )
    summary_md_path.write_text(_summary_markdown(summary_rows, metadata_obj), encoding="utf-8")

    print(f"raw_json={raw_json_path}")
    print(f"raw_csv={raw_csv_path}")
    print(f"summary_json={summary_json_path}")
    print(f"summary_csv={summary_csv_path}")
    print(f"summary_md={summary_md_path}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
