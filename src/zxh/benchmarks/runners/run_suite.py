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

from backend_registry import backend_map
from env_capture import capture_env, write_env
from manifest import load_manifest
from stage import activate_python_stage

RESULT_PREFIX = "ZXHSIM_BENCHMARK_RESULT="
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
        return BENCH_ROOT / "manifest.yaml"
    path = Path(raw)
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def _suite_path_from_args(raw: str) -> Path:
    path = Path(raw)
    if path.suffix:
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        return path
    return (BENCH_ROOT / "suites" / f"{raw}.yaml").resolve()


def _resolve_repo_path(base_dir: Path, raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    repo_candidate = (REPO_ROOT / path).resolve()
    if repo_candidate.exists():
        return repo_candidate
    return (base_dir / path).resolve()


def _resolve_output_root(raw: str) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def _workload_map(manifest: dict) -> dict[str, dict[str, Any]]:
    return {str(item["id"]): item for item in manifest.get("workloads", [])}


def _selected_backend(suite: dict, explicit_backends: list[str]) -> str:
    if explicit_backends:
        raise ValueError("benchmark runner no longer accepts command-line backend override")
    if "backend" not in suite:
        raise ValueError("benchmark suite must declare a single `backend` field")
    return str(suite["backend"])


def _selected_workloads(suite: dict, explicit_workloads: list[str]) -> list[str]:
    if explicit_workloads:
        raise ValueError("benchmark runner no longer accepts command-line workload override")
    return [str(item) for item in suite.get("workloads", [])]


def _task_id(backend: str, workload_id: str, phase: str, run_index: int) -> str:
    return f"{backend}__{workload_id}__{phase}__{run_index:03d}"


def _is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0


def _launcher_tokens(runtime: dict[str, Any]) -> list[str]:
    launcher = runtime.get("launcher")
    if isinstance(launcher, list) and launcher:
        return [str(item) for item in launcher]
    if isinstance(launcher, str) and launcher.strip():
        return shlex.split(launcher)

    return ["mpirun"]


def _deployment_cfg(suite: dict[str, Any], backend: str) -> dict[str, int] | None:
    deployment = suite.get("deployment")
    if deployment is None:
        return None
    if not isinstance(deployment, dict):
        raise ValueError("benchmark suite `deployment` must be a mapping")
    if backend not in {"mpi", "mpi_omp", "mpi_cuda"}:
        raise ValueError("benchmark suite `deployment` is only valid for MPI backends")

    if "nnodes" not in deployment or "ntasks_per_node" not in deployment:
        raise ValueError("benchmark suite `deployment` must declare `nnodes` and `ntasks_per_node`")

    nnodes = int(deployment["nnodes"])
    ntasks_per_node = int(deployment["ntasks_per_node"])
    if nnodes < 1 or ntasks_per_node < 1:
        raise ValueError("benchmark suite `deployment` requires positive `nnodes` and `ntasks_per_node`")

    nprocs = nnodes * ntasks_per_node
    if not _is_power_of_two(nprocs):
        raise ValueError("benchmark suite deployment requires nnodes * ntasks_per_node to be a power of two")

    return {
        "nnodes": nnodes,
        "ntasks_per_node": ntasks_per_node,
        "nprocs": nprocs,
    }


def _default_runtime_env(backend: str, deployment: dict[str, int] | None) -> dict[str, str]:
    env = os.environ.copy()
    if deployment is None and backend in {"cuda", "mpi_cuda"} and not env.get("CUDA_VISIBLE_DEVICES"):
        env["CUDA_VISIBLE_DEVICES"] = "0"
    return env


def _launcher_prefix(
    backend_cfg: dict[str, Any],
    backend: str,
    deployment: dict[str, int] | None,
) -> list[str]:
    if deployment is not None:
        cmd = [
            "srun",
            "-N",
            str(deployment["nnodes"]),
            "-n",
            str(deployment["nprocs"]),
            f"--ntasks-per-node={deployment['ntasks_per_node']}",
        ]
        if backend == "mpi_cuda":
            cmd.append("--gpus-per-task=1")
        return cmd

    runtime = backend_cfg.get("runtime", {})
    nprocs = runtime.get("nprocs")
    if nprocs is None:
        return []

    launcher = _launcher_tokens(runtime)
    return launcher + ["-n", str(nprocs)]


def _build_worker_command(
    manifest_path: Path,
    suite_path: Path,
    backend_cfg: dict[str, Any],
    backend: str,
    deployment: dict[str, int] | None,
    workload_id: str,
    shots: int,
    opt_level: int,
    phase: str,
    run_index: int,
) -> list[str]:
    cmd = [
        sys.executable,
        str(THIS_DIR / "run_suite.py"),
        "--worker",
        "--manifest",
        str(manifest_path),
        "--suite",
        str(suite_path),
        "--backend",
        backend,
        "--workload-id",
        workload_id,
        "--shots",
        str(shots),
        "--opt-level",
        str(opt_level),
        "--phase",
        phase,
        "--run-index",
        str(run_index),
    ]
    return _launcher_prefix(backend_cfg, backend, deployment) + cmd


def _parse_worker_result(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        if line.startswith(RESULT_PREFIX):
            return json.loads(line[len(RESULT_PREFIX) :])
    raise ValueError("worker did not emit structured result")


def _load_backend_modules(backend: str) -> tuple[Any, Any]:
    activate_python_stage(REPO_ROOT, backend)
    zxhsim = importlib.import_module("zxhsim")
    qasm = importlib.import_module("zxhsim.qasm")
    return zxhsim, qasm


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run_worker_task(
    manifest_path: Path,
    suite_path: Path,
    backend_cfg: dict[str, Any],
    backend: str,
    deployment: dict[str, int] | None,
    workload_id: str,
    shots: int,
    opt_level: int,
    timeout_s: int,
    phase: str,
    run_index: int,
    task_id: str,
    log_dir: Path,
) -> dict[str, Any]:
    cmd = _build_worker_command(
        manifest_path=manifest_path,
        suite_path=suite_path,
        backend_cfg=backend_cfg,
        backend=backend,
        deployment=deployment,
        workload_id=workload_id,
        shots=shots,
        opt_level=opt_level,
        phase=phase,
        run_index=run_index,
    )
    started_at = time.perf_counter()
    env = _default_runtime_env(backend, deployment)
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
        log_path = log_dir / f"{task_id}.log"
        _write_text(
            log_path,
            f"$ {' '.join(cmd)}\nreturncode=timeout\n\n--- stdout ---\n{exc.stdout or ''}\n--- stderr ---\n{exc.stderr or ''}\n",
        )
        return {
            "task_id": task_id,
            "backend": backend,
            "workload_id": workload_id,
            "phase": phase,
            "run_index": run_index,
            "status": "timeout",
            "runner_time_s": time.perf_counter() - started_at,
            "timeout_s": timeout_s,
            "log_path": str(log_path),
        }
    except OSError as exc:
        log_path = log_dir / f"{task_id}.log"
        _write_text(
            log_path,
            f"$ {' '.join(cmd)}\nreturncode=oserror\n\n--- error ---\n{exc}\n",
        )
        return {
            "task_id": task_id,
            "backend": backend,
            "workload_id": workload_id,
            "phase": phase,
            "run_index": run_index,
            "status": "error",
            "error": str(exc),
            "runner_time_s": time.perf_counter() - started_at,
            "log_path": str(log_path),
        }

    log_path = log_dir / f"{task_id}.log"
    _write_text(
        log_path,
        f"$ {' '.join(cmd)}\nreturncode={proc.returncode}\n\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}\n",
    )

    try:
        result = _parse_worker_result(proc.stdout)
    except Exception:
        return {
            "task_id": task_id,
            "backend": backend,
            "workload_id": workload_id,
            "phase": phase,
            "run_index": run_index,
            "status": "error",
            "error": "worker did not emit structured result",
            "returncode": proc.returncode,
            "runner_time_s": time.perf_counter() - started_at,
            "log_path": str(log_path),
        }

    result["task_id"] = task_id
    result["runner_time_s"] = time.perf_counter() - started_at
    result["returncode"] = proc.returncode
    result["log_path"] = str(log_path)
    if proc.returncode != 0 and result.get("status") == "pass":
        result["status"] = "error"
        result["error"] = f"worker exited with code {proc.returncode}"
    if proc.stderr:
        result["stderr"] = proc.stderr
    return result


def _execute_worker(
    manifest_path: Path,
    suite_path: Path,
    backend: str,
    workload_id: str,
    shots: int,
    opt_level: int,
    phase: str,
    run_index: int,
) -> dict[str, Any]:
    manifest = load_manifest(manifest_path)
    workloads = _workload_map(manifest)
    if workload_id not in workloads:
        raise KeyError(f"unknown workload id: {workload_id}")

    workload = workloads[workload_id]
    source = workload.get("source", {})
    if str(source.get("kind", "")) != "static_qasm":
        raise NotImplementedError("benchmark MVP currently only supports static_qasm workloads")

    qasm_path = _resolve_repo_path(manifest_path.parent, str(source["path"]))
    try:
        zxhsim, qasm = _load_backend_modules(backend)
    except Exception as exc:
        result = {
            "backend": backend,
            "workload_id": workload_id,
            "phase": phase,
            "run_index": run_index,
            "status": "error",
            "error": str(exc),
        }
        print(f"{RESULT_PREFIX}{json.dumps(result, ensure_ascii=False, sort_keys=True)}", flush=True)
        return 1

    zxhsim.init()
    rank = zxhsim.rank() if hasattr(zxhsim, "rank") else 0
    try:
        t_total_start = time.perf_counter()

        t_load_start = time.perf_counter()
        circuit = qasm.load_qasm(qasm_path)
        load_time_s = time.perf_counter() - t_load_start

        sim = zxhsim.ZXH(circuit.num_qubits)

        t_compile_start = time.perf_counter()
        qasm.load_circuit(sim, circuit, optimize_level=opt_level)
        compile_time_s = time.perf_counter() - t_compile_start

        t_execute_start = time.perf_counter()
        sim.execute()
        execute_time_s = time.perf_counter() - t_execute_start

        t_sample_start = time.perf_counter()
        samples = sim.Sampling(shots)
        sample_time_s = time.perf_counter() - t_sample_start

        result = {
            "backend": backend,
            "workload_id": workload_id,
            "family_id": str(workload.get("family_id", "")),
            "phase": phase,
            "run_index": run_index,
            "status": "pass",
            "shots": shots,
            "opt_level": opt_level,
            "qasm_path": str(qasm_path),
            "num_qubits": circuit.num_qubits,
            "params": workload.get("params", {}),
            "sample_count": len(samples),
            "metrics_ms": {
                "load_time_ms": load_time_s * 1000.0,
                "compile_time_ms": compile_time_s * 1000.0,
                "execute_time_ms": execute_time_s * 1000.0,
                "sample_time_ms": sample_time_s * 1000.0,
                "total_time_ms": (time.perf_counter() - t_total_start) * 1000.0,
            },
        }
    except Exception as exc:
        if rank == 0:
            result = {
                "backend": backend,
                "workload_id": workload_id,
                "phase": phase,
                "run_index": run_index,
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


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="ZXH-Sim benchmark suite runner")
    parser.add_argument("--suite", type=str, required=True, help="Suite id or suite yaml path")
    parser.add_argument("--manifest", type=str, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--backend", action="append", default=[], help=argparse.SUPPRESS)
    parser.add_argument("--workload-id", action="append", default=[], help=argparse.SUPPRESS)
    parser.add_argument("--output-dir", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--shots", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--warmup", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--repeats", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--timeout-s", type=int, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--opt-level", type=int, default=None, choices=[0, 1, 2, 3], help=argparse.SUPPRESS)
    parser.add_argument("--stop-on-error", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--phase", type=str, default="measure", help=argparse.SUPPRESS)
    parser.add_argument("--run-index", type=int, default=0, help=argparse.SUPPRESS)
    args = parser.parse_args()

    manifest_path = _manifest_path_from_args(args.manifest)
    suite_path = _suite_path_from_args(args.suite)

    if args.worker:
        return _execute_worker(
            manifest_path=manifest_path,
            suite_path=suite_path,
            backend=args.backend[0] if isinstance(args.backend, list) else str(args.backend),
            workload_id=args.workload_id[0] if isinstance(args.workload_id, list) else str(args.workload_id),
            shots=int(args.shots),
            opt_level=int(args.opt_level),
            phase=args.phase,
            run_index=int(args.run_index),
        )

    manifest = load_manifest(manifest_path)
    suite = load_manifest(suite_path)
    backends = backend_map()
    workloads = _workload_map(manifest)
    defaults = manifest.get("defaults", {})

    suite_id = str(suite.get("suite_id", suite_path.stem))
    selected_backend = _selected_backend(suite, args.backend)
    selected_workloads = _selected_workloads(suite, args.workload_id)
    if selected_backend not in backends:
        raise KeyError(f"unknown backend in selection: {selected_backend}")
    missing_workloads = [workload_id for workload_id in selected_workloads if workload_id not in workloads]
    if missing_workloads:
        raise KeyError(f"unknown workloads in selection: {missing_workloads}")

    deployment = _deployment_cfg(suite, selected_backend)

    if deployment is None and selected_backend in {"cuda", "mpi_cuda"} and not os.environ.get("CUDA_VISIBLE_DEVICES"):
        os.environ["CUDA_VISIBLE_DEVICES"] = "0"

    if any(
        value is not None
        for value in [args.shots, args.warmup, args.repeats, args.timeout_s, args.opt_level, args.output_dir]
    ) or args.stop_on_error:
        raise ValueError("benchmark runner no longer accepts command-line config override")

    shots = int(suite.get("shots", defaults.get("shots", 256)))
    warmup = int(suite.get("warmup", defaults.get("warmup", 0)))
    repeats = int(suite.get("repeats", defaults.get("repeats", 1)))
    timeout_s = int(suite.get("timeout_s", defaults.get("timeout_s", 20)))
    opt_level = int(suite.get("opt_level", defaults.get("opt_level", 1)))
    stop_on_error = bool(suite.get("stop_on_error", defaults.get("stop_on_error", False)))

    output_root = _resolve_output_root(str(defaults.get("output_root", "build/benchmarks")))
    output_dir = (output_root / suite_id).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    log_dir = output_dir / "logs"
    env_data = capture_env()
    if deployment is not None:
        env_data["suite_deployment"] = deployment
    write_env(output_dir / "env.json", env_data)

    results: list[dict[str, Any]] = []
    passed = 0
    failed = 0
    errored = 0
    timed_out = 0

    total_tasks = len(selected_workloads) * (warmup + repeats)
    task_counter = 0
    backend_cfg = backends[selected_backend]
    for workload_id in selected_workloads:
        for run_index in range(warmup):
            phase = "warmup"
            task_counter += 1
            task_id = _task_id(selected_backend, workload_id, phase, run_index)
            result = _run_worker_task(
                manifest_path=manifest_path,
                suite_path=suite_path,
                backend_cfg=backend_cfg,
                backend=selected_backend,
                deployment=deployment,
                workload_id=workload_id,
                shots=shots,
                opt_level=opt_level,
                timeout_s=timeout_s,
                phase=phase,
                run_index=run_index,
                task_id=task_id,
                log_dir=log_dir,
            )
            result["env_id"] = env_data["env_id"]
            results.append(result)
            status = result["status"]
            if status == "pass":
                print(f"[{task_counter}/{total_tasks}] {_yellow('[WARMUP]')} {selected_backend} {workload_id}")
            else:
                print(f"[{task_counter}/{total_tasks}] {_red('[ERROR]')} {selected_backend} {workload_id}: {result.get('error', status)}")
                if stop_on_error:
                    break
        else:
            for run_index in range(repeats):
                phase = "measure"
                task_counter += 1
                task_id = _task_id(selected_backend, workload_id, phase, run_index)
                result = _run_worker_task(
                    manifest_path=manifest_path,
                    suite_path=suite_path,
                    backend_cfg=backend_cfg,
                    backend=selected_backend,
                    deployment=deployment,
                    workload_id=workload_id,
                    shots=shots,
                    opt_level=opt_level,
                    timeout_s=timeout_s,
                    phase=phase,
                    run_index=run_index,
                    task_id=task_id,
                    log_dir=log_dir,
                )
                result["env_id"] = env_data["env_id"]
                results.append(result)
                status = result["status"]
                metric_text = ""
                metrics = result.get("metrics_ms", {})
                if isinstance(metrics, dict) and metrics:
                    metric_text = (
                        f" compile_ms={metrics.get('compile_time_ms', 0.0):.3f}"
                        f" execute_ms={metrics.get('execute_time_ms', 0.0):.3f}"
                        f" sample_ms={metrics.get('sample_time_ms', 0.0):.3f}"
                        f" total_ms={metrics.get('total_time_ms', 0.0):.3f}"
                    )
                if status == "pass":
                    passed += 1
                    print(f"[{task_counter}/{total_tasks}] {_green('[PASS]')} {selected_backend} {workload_id}{metric_text}")
                elif status == "timeout":
                    timed_out += 1
                    print(f"[{task_counter}/{total_tasks}] {_yellow('[TIMEOUT]')} {selected_backend} {workload_id}: timeout_s={timeout_s}")
                    if stop_on_error:
                        break
                else:
                    if status == "fail":
                        failed += 1
                    else:
                        errored += 1
                    print(f"[{task_counter}/{total_tasks}] {_red('[ERROR]')} {selected_backend} {workload_id}: {result.get('error', status)}")
                    if stop_on_error:
                        break
            else:
                continue
            break
        break

    summary = {
        "total_tasks": len(results),
        "warmup_tasks": len([r for r in results if r.get("phase") == "warmup"]),
        "measured_tasks": len([r for r in results if r.get("phase") == "measure"]),
        "measured_passed": passed,
        "failed": failed,
        "errored": errored,
        "timed_out": timed_out,
    }
    report = {
        "suite_id": suite_id,
        "manifest_path": str(manifest_path),
        "suite_path": str(suite_path),
        "output_dir": str(output_dir),
        "env_path": str(output_dir / "env.json"),
        "env_id": env_data["env_id"],
        "config": {
            "backend": selected_backend,
            "deployment": deployment,
            "workloads": selected_workloads,
            "shots": shots,
            "warmup": warmup,
            "repeats": repeats,
            "timeout_s": timeout_s,
            "opt_level": opt_level,
        },
        "results": results,
        "summary": summary,
    }
    report_path = output_dir / "raw.json"
    _write_json(report_path, report)
    print(
        "Summary: "
        f"total_tasks={summary['total_tasks']}, "
        f"warmup_tasks={summary['warmup_tasks']}, "
        f"measured_tasks={summary['measured_tasks']}, "
        f"measured_passed={passed}, "
        f"failed={failed}, errored={errored}, timed_out={timed_out}"
    )
    print(f"Raw report: {report_path}")
    print(f"Env report: {output_dir / 'env.json'}")

    return 0 if failed == 0 and errored == 0 and timed_out == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
