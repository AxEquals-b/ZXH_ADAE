#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean, stdev
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ADAE_ROOT = REPO_ROOT / "benchmarks" / "ADAE"
RUN_RESULTS_ROOT = ADAE_ROOT / "results" / "run" / "representative_cuda"
DEFAULT_MANIFEST = (
    ADAE_ROOT / "results" / "prepare" / "workflow" / "03_pass3_canonicalize" / "canonical_manifest.json"
)
REPEAT_RSD_WARNING_THRESHOLD = 0.10
GPU_MEMORY_MONITOR_BACKENDS = {"cudaq", "zxh-cuda"}
GPU_MEMORY_POLL_INTERVAL_S = 0.2

BACKEND_RUNNER_SCRIPTS = {
    "cudaq": ADAE_ROOT / "run" / "scripts" / "run_backend_cudaq.py",
    "zxh-cuda": ADAE_ROOT / "run" / "scripts" / "run_backend_zxh_cuda.py",
    "ddsim": ADAE_ROOT / "run" / "scripts" / "run_backend_ddsim.py",
    "qblaze": ADAE_ROOT / "run" / "scripts" / "run_backend_qblaze.py",
}

SWEEP_CASE_RE = re.compile(r"^(?P<base>.+)_n(?P<n>\d+)$")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ADAE run stage with family-level process isolation.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--warmup", type=int, default=4)
    parser.add_argument("--repeats", type=int, default=8)
    parser.add_argument("--shots", type=int, default=1)
    parser.add_argument("--cudaq-target", type=str, default="nvidia")
    parser.add_argument("--run-id", type=str, default=None)
    parser.add_argument("--stop-on-error", action="store_true")
    parser.add_argument(
        "--timeout-s",
        type=float,
        default=None,
        help="Optional hard wall-clock timeout in seconds for each isolated family/backend child process.",
    )
    parser.add_argument(
        "--time-budget-s",
        type=float,
        default=100.0,
        help="Per-run budget in seconds. Child backend runners stop the current family/backend once a single warmup/repeat iteration exceeds 1.5x this budget. Default: 100.",
    )
    parser.add_argument(
        "--host-mem-budget-gib",
        type=float,
        default=None,
        help="Optional host memory budget in GiB enforced on the isolated child process via RLIMIT_AS.",
    )
    parser.add_argument(
        "--gpu-mem-budget-gib",
        type=float,
        default=40.0,
        help="GPU memory limit in GiB enforced by runner-side external monitoring for CUDA backends. Default: 40.",
    )
    parser.add_argument(
        "--resume-existing",
        action="store_true",
        help="Skip child tasks whose summary.json already exists under the selected run directory.",
    )
    parser.add_argument(
        "--zxh-disable-x",
        action="store_true",
        help="Enable the ZXH ablation that executes X/CX explicitly instead of absorbing them into A/b.",
    )
    parser.add_argument(
        "--zxh-eager-expand-all",
        action="store_true",
        help="Enable the ZXH ablation that eagerly expands the state to N bits before execution.",
    )
    parser.add_argument(
        "--backend",
        action="append",
        choices=["cudaq", "zxh-cuda", "ddsim", "qblaze"],
        default=[],
        help="Backend to run. Repeat this flag to select multiple backends. Default: cuQuantum + ZXH.",
    )
    return parser.parse_args()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _parse_sweep_case(family: str) -> tuple[str, int] | None:
    match = SWEEP_CASE_RE.match(family)
    if match is None:
        return None
    return match.group("base"), int(match.group("n"))


def _record_timeout_cutoff(timeout_cutoff_by_backend: dict[tuple[str, str], int], sweep_key: tuple[str, str] | None, sweep_n: int | None) -> None:
    if sweep_key is None or sweep_n is None:
        return
    previous = timeout_cutoff_by_backend.get(sweep_key)
    if previous is None or sweep_n < previous:
        timeout_cutoff_by_backend[sweep_key] = sweep_n


def _resolve_repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def _repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


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


def _summary_markdown(summary_rows: list[dict[str, Any]], metadata_obj: dict[str, Any]) -> str:
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
        f"- timeout_s: `{metadata_obj['timeout_s']}`",
        f"- time_budget_s: `{metadata_obj['time_budget_s']}`",
        f"- effective_child_timeout_s: `{metadata_obj['effective_child_timeout_s']}`",
        f"- host_mem_budget_bytes: `{metadata_obj['host_mem_budget_bytes']}`",
        f"- gpu_mem_budget_bytes: `{metadata_obj['gpu_mem_budget_bytes']}`",
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


def _load_manifest_rows(path: Path) -> list[dict[str, Any]]:
    obj = json.loads(path.read_text(encoding="utf-8"))
    rows = list(obj.get("rows", []))
    if not rows:
        raise RuntimeError(f"No rows found in manifest: {path}")
    return rows


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _gib_to_bytes(value: float | None) -> int | None:
    if value is None:
        return None
    if value <= 0.0:
        raise ValueError("Budget values must be positive when provided.")
    return int(value * (1024**3))


def _derive_effective_timeout_s(*, timeout_s: float | None) -> float | None:
    return timeout_s


def _make_preexec_fn(host_mem_budget_bytes: int | None):
    if host_mem_budget_bytes is None:
        return None

    def _apply_limits() -> None:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (host_mem_budget_bytes, host_mem_budget_bytes))

    return _apply_limits


def _query_pid_gpu_memory_mib(pid: int) -> int:
    proc = subprocess.run(
        [
            "nvidia-smi",
            "--query-compute-apps=pid,used_gpu_memory",
            "--format=csv,noheader,nounits",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"nvidia-smi failed: returncode={proc.returncode} stderr={proc.stderr.strip()}")

    total_mib = 0
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        left, right = [part.strip() for part in line.split(",", maxsplit=1)]
        if int(left) == pid:
            total_mib += int(right)
    return total_mib


def _run_child_process(
    *,
    cmd: list[str],
    cwd: Path,
    timeout_s: float | None,
    preexec_fn,
    monitor_gpu: bool,
    gpu_mem_limit_bytes: int | None,
) -> dict[str, Any]:
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=None,
        stderr=None,
        text=True,
        preexec_fn=preexec_fn,
    )
    t0 = time.perf_counter()
    peak_gpu_mib = 0

    while True:
        returncode = proc.poll()

        if monitor_gpu:
            try:
                current_gpu_mib = _query_pid_gpu_memory_mib(proc.pid)
                peak_gpu_mib = max(peak_gpu_mib, current_gpu_mib)
                current_gpu_bytes = current_gpu_mib * 1024 * 1024
                if gpu_mem_limit_bytes is not None and current_gpu_bytes > gpu_mem_limit_bytes:
                    proc.kill()
                    proc.wait()
                    return {
                        "returncode": -9,
                        "status": "gpu_mem_limit_exceeded",
                        "elapsed_s": time.perf_counter() - t0,
                        "peak_gpu_mib": peak_gpu_mib,
                    }
            except Exception as exc:
                proc.kill()
                proc.wait()
                return {
                    "returncode": -1,
                    "status": "gpu_mem_monitor_error",
                    "elapsed_s": time.perf_counter() - t0,
                    "peak_gpu_mib": peak_gpu_mib,
                    "gpu_memory_monitor_error": f"{type(exc).__name__}: {exc}",
                }

        if returncode is not None:
            return {
                "returncode": int(returncode),
                "status": "finished",
                "elapsed_s": time.perf_counter() - t0,
                "peak_gpu_mib": peak_gpu_mib,
                "gpu_memory_monitor_error": "",
            }

        if timeout_s is not None and (time.perf_counter() - t0) >= timeout_s:
            proc.kill()
            proc.wait()
            return {
                "returncode": -9,
                "status": "timeout",
                "elapsed_s": time.perf_counter() - t0,
                "peak_gpu_mib": peak_gpu_mib,
                "gpu_memory_monitor_error": "",
            }

        time.sleep(GPU_MEMORY_POLL_INTERVAL_S if monitor_gpu else 0.1)


def _relative_stddev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mu = mean(values)
    if mu <= 0.0:
        return 0.0
    return stdev(values) / mu


def _build_summary_rows(raw_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    for row in raw_rows:
        key = (str(row["family"]), int(row["N"]), str(row["backend"]))
        grouped.setdefault(key, []).append(row)

    out: list[dict[str, Any]] = []
    for (family, num_qubits, backend), bucket in sorted(grouped.items()):
        passed = [candidate for candidate in bucket if candidate["status"] == "pass"]
        statuses = {str(candidate["status"]) for candidate in bucket}
        values = [float(candidate["end_to_end_ms"]) for candidate in passed]
        end_to_end_ms_mean = mean(values) if values else 0.0
        end_to_end_ms_rsd_pct = _relative_stddev(values) * 100.0
        warning = ""
        if values and (end_to_end_ms_rsd_pct / 100.0) > REPEAT_RSD_WARNING_THRESHOLD:
            warning = f"end_to_end_ms={end_to_end_ms_rsd_pct:.2f}%"
        out.append(
            {
                "family": family,
                "N": num_qubits,
                "backend": backend,
                "repeats": len(passed),
                "end_to_end_ms_mean": end_to_end_ms_mean,
                "end_to_end_ms_rsd_pct": end_to_end_ms_rsd_pct,
                "kernel_build_ms_mean": mean(float(candidate["kernel_build_ms"]) for candidate in passed) if passed else 0.0,
                "execute_ms_mean": mean(float(candidate["execute_ms"]) for candidate in passed) if passed else 0.0,
                "sample_ms_mean": mean(float(candidate["sample_ms"]) for candidate in passed) if passed else 0.0,
                "warning": warning,
                "status": ("pass" if statuses == {"pass"} else ("timeout" if "timeout" in statuses else "error")),
            }
        )
    return out


def _empty_error_row(*, row: dict[str, Any], family: str, backend: str, error: str, status: str = "error") -> dict[str, Any]:
    return {
        "family": family,
        "N": int(row.get("N", 0)),
        "backend": backend,
        "repeat_index": -1,
        "qasm_path": str(row.get("canonical_qasm3_path", "")),
        "load_qasm_ms": 0.0,
        "input_prepare_ms": 0.0,
        "canonical_gate_count": int(row.get("canonical_gate_count", 0) or 0),
        "canonical_gate_types": ";".join(row.get("canonical_gate_types", [])),
        "execution_gate_count": int(row.get("canonical_gate_count", 0) or 0),
        "execution_gate_types": ";".join(row.get("canonical_gate_types", [])),
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
    manifest_path = _resolve_repo_path(args.manifest)
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    rows = _load_manifest_rows(manifest_path)
    if args.family:
        selected = set(args.family)
        rows = [row for row in rows if str(row["family"]) in selected]
    rows = sorted(rows, key=lambda row: (int(row.get("N", 0)), str(row["family"])))
    if args.limit is not None:
        rows = rows[: args.limit]
    if not rows:
        raise RuntimeError("No benchmark cases were selected.")

    run_id = args.run_id or f"representative_cuda_{_timestamp()}"
    out_dir = RUN_RESULTS_ROOT / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    backends = args.backend or ["cudaq", "zxh-cuda"]
    host_mem_budget_bytes = _gib_to_bytes(args.host_mem_budget_gib)
    gpu_mem_budget_bytes = _gib_to_bytes(args.gpu_mem_budget_gib)
    effective_child_timeout_s = _derive_effective_timeout_s(
        timeout_s=args.timeout_s,
    )
    child_preexec_fn = _make_preexec_fn(host_mem_budget_bytes)

    raw_rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    child_runs: list[dict[str, Any]] = []
    timeout_cutoff_by_backend: dict[tuple[str, str], int] = {}

    for index, row in enumerate(rows, start=1):
        family = str(row["family"])
        sweep_case = _parse_sweep_case(family)
        family_had_error = False
        for backend in backends:
            sweep_key: tuple[str, str] | None = None
            sweep_n: int | None = None
            if sweep_case is not None:
                sweep_base, sweep_n = sweep_case
                sweep_key = (sweep_base, backend)
                timeout_cutoff_n = timeout_cutoff_by_backend.get(sweep_key)
                if timeout_cutoff_n is not None and sweep_n > timeout_cutoff_n:
                    skip_msg = (
                        f"Skipped because smaller sweep point already timed out: "
                        f"base_family={sweep_base} backend={backend} timeout_cutoff_n={timeout_cutoff_n}"
                    )
                    error_row = _empty_error_row(
                        row=row,
                        family=family,
                        backend=backend,
                        error=skip_msg,
                        status="timeout",
                    )
                    raw_rows.append(error_row)
                    errors.append(error_row)
                    child_runs.append(
                        {
                            "family": family,
                            "backend": backend,
                            "child_run_id": "",
                            "returncode": 0,
                            "summary_json": "",
                            "raw_json": "",
                            "status": "skipped_after_timeout",
                            "skip_reason": skip_msg,
                        }
                    )
                    print(
                        f"[case {index}/{len(rows)}] skip family={family} backend={backend} reason=larger_than_timeout_cutoff cutoff_n={timeout_cutoff_n}",
                        flush=True,
                    )
                    continue
            child_run_id = f"{run_id}/per_case/{index:02d}_{family}/{backend}"
            runner_script = BACKEND_RUNNER_SCRIPTS.get(backend)
            if runner_script is None:
                raise ValueError(f"No runner script registered for backend: {backend}")
            cmd = [
                sys.executable,
                "-u",
                str(runner_script),
                "--manifest",
                str(manifest_path),
                "--family",
                family,
                "--warmup",
                str(args.warmup),
                "--repeats",
                str(args.repeats),
                "--shots",
                str(args.shots),
                "--time-budget-s",
                str(args.time_budget_s),
                "--run-id",
                child_run_id,
            ]
            if backend == "cudaq":
                cmd.extend(["--cudaq-target", args.cudaq_target])
            elif backend == "zxh-cuda":
                if args.zxh_disable_x:
                    cmd.append("--disable-x")
                if args.zxh_eager_expand_all:
                    cmd.append("--eager-expand-all")
            print(
                f"[case {index}/{len(rows)}] start family={family} backend={backend} child_run_id={child_run_id}",
                flush=True,
            )

            child_dir = RUN_RESULTS_ROOT / child_run_id
            child_summary_path = child_dir / "summary.json"
            child_raw_path = child_dir / "raw_results.json"

            if args.resume_existing and child_summary_path.is_file():
                print(
                    f"[case {index}/{len(rows)}] skip family={family} backend={backend} reason=summary_exists",
                    flush=True,
                )
                child_summary = _load_json(child_summary_path)
                child_summary_statuses = {str(item.get("status", "")) for item in child_summary.get("rows", [])}
                if "timeout" in child_summary_statuses:
                    _record_timeout_cutoff(timeout_cutoff_by_backend, sweep_key, sweep_n)
                if child_raw_path.is_file():
                    child_raw = _load_json(child_raw_path)
                    raw_rows.extend(list(child_raw.get("rows", [])))
                else:
                    error_row = _empty_error_row(
                        row=row,
                        family=family,
                        backend=backend,
                        error="summary.json exists but raw_results.json is missing during resume_existing",
                    )
                    raw_rows.append(error_row)
                    errors.append(error_row)
                child_runs.append(
                    {
                        "family": family,
                        "backend": backend,
                        "child_run_id": child_run_id,
                        "returncode": 0,
                        "summary_json": _repo_rel(child_summary_path),
                        "raw_json": _repo_rel(child_raw_path),
                        "status": "skipped_existing",
                    }
                )
                continue

            child_record = {
                "family": family,
                "backend": backend,
                "child_run_id": child_run_id,
                "summary_json": _repo_rel(child_summary_path),
                "raw_json": _repo_rel(child_raw_path),
                "host_mem_budget_bytes": host_mem_budget_bytes,
                "gpu_mem_budget_bytes": gpu_mem_budget_bytes,
                "timeout_s": args.timeout_s,
                "time_budget_s": args.time_budget_s,
                "effective_child_timeout_s": effective_child_timeout_s,
                "gpu_monitor_enabled": backend in GPU_MEMORY_MONITOR_BACKENDS,
            }

            try:
                child_result = _run_child_process(
                    cmd=cmd,
                    cwd=REPO_ROOT,
                    timeout_s=effective_child_timeout_s,
                    preexec_fn=child_preexec_fn,
                    monitor_gpu=(backend in GPU_MEMORY_MONITOR_BACKENDS),
                    gpu_mem_limit_bytes=gpu_mem_budget_bytes,
                )
                child_record["returncode"] = int(child_result["returncode"])
                child_record["observed_peak_gpu_mib"] = int(child_result["peak_gpu_mib"])
                child_record["elapsed_s"] = float(child_result["elapsed_s"])
                child_record["gpu_memory_monitor_error"] = str(child_result["gpu_memory_monitor_error"])

                if child_result["status"] == "timeout":
                    child_record["status"] = "timeout"
                elif child_result["status"] == "gpu_mem_limit_exceeded":
                    child_record["status"] = "gpu_mem_limit_exceeded"
                elif child_result["status"] == "gpu_mem_monitor_error":
                    child_record["status"] = "gpu_mem_monitor_error"
                else:
                    child_record["status"] = "pass" if child_record["returncode"] == 0 else f"error({child_record['returncode']})"
                child_runs.append(child_record)

                if child_result["status"] == "timeout":
                    _record_timeout_cutoff(timeout_cutoff_by_backend, sweep_key, sweep_n)
                    timeout_msg = (
                        f"Child run timed out after {effective_child_timeout_s} seconds before emitting summary.json"
                    )
                    error_row = _empty_error_row(
                        row=row,
                        family=family,
                        backend=backend,
                        error=timeout_msg,
                        status="timeout",
                    )
                    raw_rows.append(error_row)
                    errors.append(error_row)
                    print(
                        f"[case {index}/{len(rows)}] done family={family} backend={backend} status=timeout",
                        flush=True,
                    )
                    family_had_error = True
                    if args.stop_on_error:
                        break
                    continue

                if child_result["status"] == "gpu_mem_monitor_error":
                    error_row = _empty_error_row(
                        row=row,
                        family=family,
                        backend=backend,
                        error=f"GPU memory monitor failed: {child_record['gpu_memory_monitor_error']}",
                    )
                    raw_rows.append(error_row)
                    errors.append(error_row)
                    print(
                        f"[case {index}/{len(rows)}] done family={family} backend={backend} status=gpu_mem_monitor_error "
                        f"error={child_record['gpu_memory_monitor_error']}",
                        flush=True,
                    )
                    family_had_error = True
                    if args.stop_on_error:
                        break
                    continue

                if child_result["status"] == "gpu_mem_limit_exceeded":
                    error_row = _empty_error_row(
                        row=row,
                        family=family,
                        backend=backend,
                        error=(
                            "Child run exceeded external GPU memory limit: "
                            f"observed_peak_gpu_mib={child_record['observed_peak_gpu_mib']} "
                            f"gpu_mem_budget_bytes={gpu_mem_budget_bytes}"
                        ),
                    )
                    raw_rows.append(error_row)
                    errors.append(error_row)
                    print(
                        f"[case {index}/{len(rows)}] done family={family} backend={backend} status=gpu_mem_limit_exceeded "
                        f"peak_gpu_mib={child_record['observed_peak_gpu_mib']}",
                        flush=True,
                    )
                    family_had_error = True
                    if args.stop_on_error:
                        break
                    continue

                if child_raw_path.is_file():
                    child_raw = _load_json(child_raw_path)
                    raw_rows.extend(list(child_raw.get("rows", [])))
                else:
                    error_row = _empty_error_row(
                        row=row,
                        family=family,
                        backend=backend,
                        error=(
                            "Child run failed before emitting raw_results.json "
                            f"(returncode={child_record['returncode']})"
                        ),
                    )
                    raw_rows.append(error_row)
                    errors.append(error_row)

                if child_summary_path.is_file():
                    child_summary = _load_json(child_summary_path)
                    child_summary_statuses = {str(item.get("status", "")) for item in child_summary.get("rows", [])}
                    if "timeout" in child_summary_statuses and str(child_record["status"]).startswith("error("):
                        child_record["status"] = "timeout"
                    if "timeout" in child_summary_statuses:
                        _record_timeout_cutoff(timeout_cutoff_by_backend, sweep_key, sweep_n)
                    errors.extend(list(child_summary.get("errors", [])))

                print(
                    f"[case {index}/{len(rows)}] done family={family} backend={backend} status={child_record['status']}",
                    flush=True,
                )
                if child_record["returncode"] != 0:
                    family_had_error = True
                    if args.stop_on_error:
                        break
            except Exception as exc:
                child_record["returncode"] = -1
                child_record["status"] = "launcher_error"
                child_runs.append(child_record)
                error_row = _empty_error_row(
                    row=row,
                    family=family,
                    backend=backend,
                    error=f"LauncherError: {type(exc).__name__}: {exc}",
                )
                raw_rows.append(error_row)
                errors.append(error_row)
                print(
                    f"[case {index}/{len(rows)}] done family={family} backend={backend} status=launcher_error error={type(exc).__name__}: {exc}",
                    flush=True,
                )
                family_had_error = True
                if args.stop_on_error:
                    break

        if family_had_error and args.stop_on_error:
            break

    summary_rows = _build_summary_rows(raw_rows)
    metadata_obj: dict[str, Any] = {
        "run_id": run_id,
        "manifest_path": _repo_rel(manifest_path),
        "selected_backends": backends,
        "selected_families": [str(row["family"]) for row in rows],
        "warmup": args.warmup,
        "repeats": args.repeats,
        "shots": args.shots,
        "cudaq_target": args.cudaq_target,
        "timeout_s": args.timeout_s,
        "time_budget_s": args.time_budget_s,
        "effective_child_timeout_s": effective_child_timeout_s,
        "host_mem_budget_bytes": host_mem_budget_bytes,
        "gpu_mem_budget_bytes": gpu_mem_budget_bytes,
        "gpu_memory_monitor_backends": sorted(GPU_MEMORY_MONITOR_BACKENDS),
        "gpu_memory_poll_interval_s": GPU_MEMORY_POLL_INTERVAL_S,
        "execution_model": "family_isolated_subprocess",
        "skip_larger_n_after_timeout": True,
        "zxh_disable_x": args.zxh_disable_x,
        "zxh_eager_expand_all": args.zxh_eager_expand_all,
        "repeat_rsd_warning_threshold_pct": REPEAT_RSD_WARNING_THRESHOLD * 100.0,
        "child_runs": child_runs,
    }

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
            "end_to_end_ms_rsd_pct",
            "kernel_build_ms_mean",
            "execute_ms_mean",
            "sample_ms_mean",
            "warning",
            "status",
        ],
    )
    summary_md_path.write_text(_summary_markdown(summary_rows, metadata_obj), encoding="utf-8")

    print(f"raw_json={raw_json_path}", flush=True)
    print(f"raw_csv={raw_csv_path}", flush=True)
    print(f"summary_json={summary_json_path}", flush=True)
    print(f"summary_csv={summary_csv_path}", flush=True)
    print(f"summary_md={summary_md_path}", flush=True)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
