#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
from typing import Any

THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent.parent
TOOLS_DIR = REPO_ROOT / "tools"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from backend_registry import backend_map
from manifest import load_manifest
from oracles import evaluate_oracle
from shared_stage import activate_shared_python_stage

RESULT_PREFIX = "ZXHSIM_CASE_RESULT="


_COLOR_ENABLED = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb"
_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_RESET = "\033[0m"


def _colorize(text: str, color: str) -> str:
    if not _COLOR_ENABLED:
        return text
    return f"{color}{text}{_RESET}"


def _green(text: str) -> str:
    return _colorize(text, _GREEN)


def _red(text: str) -> str:
    return _colorize(text, _RED)


def _yellow(text: str) -> str:
    return _colorize(text, _YELLOW)


def _manifest_path_from_args(raw: str | None) -> Path:
    if raw is None:
        return THIS_DIR / "manifest.yaml"
    path = Path(raw)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def _resolve_case_path(manifest_path: Path, case_relpath: str) -> Path:
    path = Path(case_relpath)
    if path.is_absolute():
        return path
    repo_candidate = (REPO_ROOT / path).resolve()
    if repo_candidate.exists():
        return repo_candidate
    return (manifest_path.parent / path).resolve()


def _worker_case_id(case_ids: list[str]) -> str:
    if len(case_ids) != 1:
        raise ValueError("worker mode requires exactly one --case-id")
    return case_ids[0]


def _case_map(manifest: dict) -> dict[str, dict]:
    return {str(item["id"]): item for item in manifest.get("cases", [])}


def _selected_case_ids(manifest: dict, backend: str, explicit_case_ids: list[str]) -> list[str]:
    if explicit_case_ids:
        return explicit_case_ids
    selected: list[str] = []
    for item in manifest.get("smoke_cases", []):
        if backend in item.get("backends", []):
            selected.append(str(item["case_id"]))
    return selected


def _launcher_tokens(runtime: dict) -> list[str]:
    launcher = runtime.get("launcher")
    if isinstance(launcher, list) and launcher:
        return [str(item) for item in launcher]
    if isinstance(launcher, str) and launcher.strip():
        return shlex.split(launcher)
    return ["mpirun"]


def _default_runtime_env(backend: str) -> dict[str, str]:
    env = os.environ.copy()
    if backend in {"cuda", "mpi_cuda"} and not env.get("CUDA_VISIBLE_DEVICES"):
        env["CUDA_VISIBLE_DEVICES"] = "0"
    return env


def _build_worker_command(
    backend_cfg: dict, manifest_path: Path, backend: str, case_id: str, shots: int, opt_level: int
) -> list[str]:
    cmd = [
        sys.executable,
        str(THIS_DIR / "run_suite.py"),
        "--worker",
        "--manifest",
        str(manifest_path),
        "--backend",
        backend,
        "--case-id",
        case_id,
        "--shots",
        str(shots),
        "--opt-level",
        str(opt_level),
    ]

    runtime = backend_cfg.get("runtime", {})
    nprocs = runtime.get("nprocs")
    if backend in {"mpi", "mpi_cuda"} and nprocs is not None:
        launcher = _launcher_tokens(runtime)
        cmd = launcher + ["-n", str(nprocs)] + cmd
    return cmd


def _parse_worker_result(stdout: str) -> dict:
    for line in reversed(stdout.splitlines()):
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX) :])
    raise ValueError("worker did not emit structured result")


def _run_worker_case(
    backend_cfg: dict,
    manifest_path: Path,
    backend: str,
    case_id: str,
    shots: int,
    opt_level: int,
    timeout_s: int,
) -> dict:
    cmd = _build_worker_command(backend_cfg, manifest_path, backend, case_id, shots, opt_level)
    env = _default_runtime_env(backend)
    started_at = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            timeout=timeout_s,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "backend": backend,
            "case_id": case_id,
            "status": "timeout",
            "runner_time_s": time.perf_counter() - started_at,
            "timeout_s": timeout_s,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "",
        }

    try:
        result = _parse_worker_result(proc.stdout)
    except Exception:
        return {
            "backend": backend,
            "case_id": case_id,
            "status": "error",
            "runner_time_s": time.perf_counter() - started_at,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "error": "worker did not emit structured result",
        }

    result["runner_time_s"] = time.perf_counter() - started_at
    result["returncode"] = proc.returncode
    if proc.stderr:
        result["stderr"] = proc.stderr
    if proc.returncode != 0 and result.get("status") == "pass":
        result["status"] = "error"
        result["error"] = f"worker exited with code {proc.returncode}"
    return result


def _load_backend_modules(backend: str) -> tuple[Any, Any]:
    activate_shared_python_stage(REPO_ROOT, backend)
    zxhsim = importlib.import_module("zxhsim")
    qasm = importlib.import_module("zxhsim.qasm")
    return zxhsim, qasm


def _execute_case_worker(manifest_path: Path, backend: str, case_id: str, shots: int, opt_level: int) -> dict:
    manifest = load_manifest(manifest_path)
    cases = _case_map(manifest)
    if case_id not in cases:
        raise KeyError(f"unknown case id: {case_id}")

    case = cases[case_id]
    qasm_path = _resolve_case_path(manifest_path, str(case["qasm"]))
    zxhsim, qasm = _load_backend_modules(backend)

    t_total_start = time.perf_counter()
    circuit = qasm.load_qasm(qasm_path)
    sim = zxhsim.ZXH(circuit.num_qubits)

    t_compile_start = time.perf_counter()
    qasm.load_circuit(sim, circuit, optimize_level=opt_level)
    compile_time_s = time.perf_counter() - t_compile_start

    t_execute_start = time.perf_counter()
    sim.execute()
    execute_time_s = time.perf_counter() - t_execute_start

    samples = sim.Sampling(shots)
    counts = dict(qasm.sample_counts(samples))
    oracle_ok, oracle_detail = evaluate_oracle(counts, shots, case["oracle"])
    seed_repro_ok = True
    seed_repro_detail = None
    if "seed_repro" in case:
        seed_repro_ok, seed_repro_detail = _evaluate_seed_repro(sim, qasm, case["seed_repro"])

    result = {
        "backend": backend,
        "case_id": case_id,
        "status": "pass" if (oracle_ok and seed_repro_ok) else "fail",
        "oracle_type": case["oracle"]["type"],
        "shots": shots,
        "counts": counts,
        "timings_s": {
            "compile": compile_time_s,
            "execute": execute_time_s,
            "total": time.perf_counter() - t_total_start,
        },
        "oracle_detail": oracle_detail,
    }
    if seed_repro_detail is not None:
        result["seed_repro"] = seed_repro_detail
    return result


def _sample_bitstrings_with_seed(sim: Any, qasm: Any, shots: int, seed: int) -> list[str]:
    sim.set_seed(seed)
    return [qasm.bitrow_to_str(row) for row in sim.Sampling(shots)]


def _evaluate_seed_repro(sim: Any, qasm: Any, cfg: dict) -> tuple[bool, dict]:
    seed = int(cfg["seed"])
    shots = int(cfg.get("shots", 64))
    repeats = int(cfg.get("repeats", 2))
    if shots <= 0:
        raise ValueError("seed_repro shots must be positive")
    if repeats < 2:
        raise ValueError("seed_repro repeats must be at least 2")

    sequences: list[list[str]] = []
    for _ in range(repeats):
        sequences.append(_sample_bitstrings_with_seed(sim, qasm, shots, seed))

    baseline = sequences[0]
    mismatch_index = None
    for idx in range(1, repeats):
        if sequences[idx] != baseline:
            mismatch_index = idx
            break

    detail = {
        "seed": seed,
        "shots": shots,
        "repeats": repeats,
        "passed": mismatch_index is None,
    }
    if mismatch_index is not None:
        detail["baseline_head"] = baseline[:8]
        detail["mismatch_repeat"] = mismatch_index
        detail["mismatch_head"] = sequences[mismatch_index][:8]
    return mismatch_index is None, detail


def _worker_main(args: argparse.Namespace) -> int:
    manifest_path = _manifest_path_from_args(args.manifest)
    case_id = _worker_case_id(args.case_id)
    try:
        zxhsim, _ = _load_backend_modules(args.backend)
    except Exception as exc:
        result = {
            "backend": args.backend,
            "case_id": case_id,
            "status": "error",
            "error": str(exc),
        }
        print(f"{RESULT_PREFIX}{json.dumps(result, ensure_ascii=False, sort_keys=True)}", flush=True)
        return 1

    zxhsim.init()
    rank = zxhsim.rank() if hasattr(zxhsim, "rank") else 0
    try:
        result = _execute_case_worker(
            manifest_path=manifest_path,
            backend=args.backend,
            case_id=case_id,
            shots=args.shots,
            opt_level=args.opt_level,
        )
    except Exception as exc:
        if rank == 0:
            result = {
                "backend": args.backend,
                "case_id": case_id,
                "status": "error",
                "error": str(exc),
            }
            print(f"{RESULT_PREFIX}{json.dumps(result, ensure_ascii=False, sort_keys=True)}", flush=True)
        return 1
    finally:
        zxhsim.finalize()

    if rank == 0:
        print(f"{RESULT_PREFIX}{json.dumps(result, ensure_ascii=False, sort_keys=True)}", flush=True)
    return 0


def _write_json_report(path: Path, report: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="ZXH-Sim integration smoke runner")
    parser.add_argument("--manifest", type=str, default=None, help="Path to manifest.yaml")
    parser.add_argument("--backend", type=str, required=True, help="Backend name in shared backend registry")
    parser.add_argument("--case-id", action="append", default=[], help="Run only selected case id(s)")
    parser.add_argument("--shots", type=int, default=None, help="Override default shots")
    parser.add_argument("--timeout-s", type=int, default=None, help="Override per-case timeout")
    parser.add_argument(
        "--opt-level", type=int, default=1, choices=[0, 1, 2, 3], help="Qiskit transpile optimization level"
    )
    parser.add_argument("--stop-on-error", action="store_true", help="Stop on first failing case")
    parser.add_argument("--json-out", type=Path, default=None, help="Write structured report to JSON")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.worker:
        return _worker_main(args)

    manifest_path = _manifest_path_from_args(args.manifest)
    manifest = load_manifest(manifest_path)
    backends = backend_map()
    cases = _case_map(manifest)

    if args.backend not in backends:
        raise KeyError(f"unknown backend: {args.backend}")

    selected_case_ids = _selected_case_ids(manifest, args.backend, args.case_id)
    if not selected_case_ids:
        raise ValueError(f"no cases selected for backend {args.backend}")

    missing_case_ids = [case_id for case_id in selected_case_ids if case_id not in cases]
    if missing_case_ids:
        raise KeyError(f"unknown case ids in selection: {missing_case_ids}")

    defaults = manifest.get("defaults", {})
    shots = int(args.shots if args.shots is not None else defaults.get("shots", 1024))
    timeout_s = int(args.timeout_s if args.timeout_s is not None else defaults.get("timeout_s", 20))
    stop_on_error = bool(args.stop_on_error or defaults.get("stop_on_error", False))

    results: list[dict] = []
    passed = 0
    failed = 0
    errored = 0
    timed_out = 0

    backend_cfg = backends[args.backend]
    total = len(selected_case_ids)
    for idx, case_id in enumerate(selected_case_ids, start=1):
        result = _run_worker_case(
            backend_cfg=backend_cfg,
            manifest_path=manifest_path,
            backend=args.backend,
            case_id=case_id,
            shots=shots,
            opt_level=args.opt_level,
            timeout_s=timeout_s,
        )
        results.append(result)

        status = result["status"]
        timings = result.get("timings_s", {})
        timing_text = ""
        if isinstance(timings, dict) and timings:
            timing_text = (
                f" compile_time_s={timings.get('compile', 0.0):.6f}"
                f" execute_time_s={timings.get('execute', 0.0):.6f}"
                f" total_time_s={timings.get('total', 0.0):.6f}"
            )

        if status == "pass":
            passed += 1
            print(f"[{idx}/{total}] {_green('[PASS]')} {case_id}{timing_text}")
            continue
        if status == "fail":
            failed += 1
            print(
                f"[{idx}/{total}] {_red('[FAIL]')} {case_id}: "
                f"{json.dumps(result.get('oracle_detail', {}), ensure_ascii=False, sort_keys=True)}"
            )
        elif status == "timeout":
            timed_out += 1
            print(f"[{idx}/{total}] {_yellow('[TIMEOUT]')} {case_id}: timeout_s={result['timeout_s']}")
        else:
            errored += 1
            print(f"[{idx}/{total}] {_red('[ERROR]')} {case_id}: {result.get('error', 'unknown error')}")

        if stop_on_error:
            break

    report = {
        "backend": args.backend,
        "shots": shots,
        "timeout_s": timeout_s,
        "results": results,
        "summary": {
            "total": len(results),
            "passed": passed,
            "failed": failed,
            "errored": errored,
            "timed_out": timed_out,
        },
    }
    print(
        "Summary: "
        f"total={report['summary']['total']}, "
        f"passed={passed}, failed={failed}, errored={errored}, timed_out={timed_out}"
    )

    if args.json_out is not None:
        _write_json_report(args.json_out, report)

    return 0 if failed == 0 and errored == 0 and timed_out == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
