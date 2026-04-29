#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import selectors
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import psutil

from suite_registry import load_suite_cases


SRC_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SRC_ROOT.parent
DEFAULT_CIRCUITS_ROOT = PROJECT_ROOT / "output" / "circuits"
DEFAULT_RESULTS_ROOT = PROJECT_ROOT / "output" / "results"
MONITOR_INTERVAL_S = 0.2
RUNNER_PREFIX = "runner: "
RESULT_FIELDS = ["circuit", "times", "sample_time", "status", "max_rss_mb", "max_gpu_mem_mb"]


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def make_result_row(
    circuit: str,
    *,
    times_value: list[float] | None,
    sample_times_value: list[float | None] | None,
    status: str,
    peaks: dict[str, float],
) -> dict[str, str]:
    return {
        "circuit": circuit,
        "times": "" if times_value is None else json.dumps([float(v) for v in times_value]),
        "sample_time": ""
        if sample_times_value is None
        else json.dumps([None if v is None else float(v) for v in sample_times_value]),
        "status": status,
        "max_rss_mb": f"{peaks['max_rss_mb']:.3f}",
        "max_gpu_mem_mb": f"{peaks['max_gpu_mem_mb']:.3f}",
    }


def collect_process_tree(pid: int) -> list[psutil.Process]:
    try:
        root = psutil.Process(pid)
    except psutil.Error:
        return []

    processes = [root]
    try:
        processes.extend(root.children(recursive=True))
    except psutil.Error:
        pass
    return processes


def current_rss_bytes(pid: int) -> int:
    total = 0
    for process in collect_process_tree(pid):
        try:
            total += process.memory_info().rss
        except psutil.Error:
            continue
    return total


def current_gpu_mem_mb(pid: int) -> float:
    pids = {process.pid for process in collect_process_tree(pid)}
    if not pids:
        return 0.0

    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-compute-apps=pid,used_memory",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        return 0.0

    total_mb = 0.0
    for line in output.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 2:
            continue
        try:
            line_pid = int(parts[0])
            used_mb = float(parts[1])
        except ValueError:
            continue
        if line_pid in pids:
            total_mb += used_mb
    return total_mb


def monitor_peak_usage(pid: int, stop_event: threading.Event, peaks: dict[str, float]) -> None:
    while not stop_event.is_set():
        peaks["max_rss_mb"] = max(peaks["max_rss_mb"], current_rss_bytes(pid) / (1024.0 * 1024.0))
        peaks["max_gpu_mem_mb"] = max(peaks["max_gpu_mem_mb"], current_gpu_mem_mb(pid))
        stop_event.wait(MONITOR_INTERVAL_S)

    peaks["max_rss_mb"] = max(peaks["max_rss_mb"], current_rss_bytes(pid) / (1024.0 * 1024.0))
    peaks["max_gpu_mem_mb"] = max(peaks["max_gpu_mem_mb"], current_gpu_mem_mb(pid))


def terminate_process(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return

    proc.kill()
    try:
        proc.wait(timeout=5.0)
    except subprocess.TimeoutExpired:
        pass


def monitor_runner_protocol(
    *,
    proc: subprocess.Popen[str],
    timeout_s: float,
) -> tuple[str, list[float] | None, list[float | None] | None, str]:
    selector = selectors.DefaultSelector()
    assert proc.stdout is not None
    assert proc.stderr is not None
    selector.register(proc.stdout, selectors.EVENT_READ, "stdout")
    selector.register(proc.stderr, selectors.EVENT_READ, "stderr")

    ready_seen = False
    last_runner_output_at: float | None = None
    ignored_output: list[str] = []
    result_payload: dict[str, object] | None = None
    final_status = "error"
    detail = ""

    try:
        while selector.get_map():
            if ready_seen and last_runner_output_at is not None:
                remaining_s = timeout_s - (time.monotonic() - last_runner_output_at)
                if remaining_s <= 0.0:
                    final_status = "timeout"
                    detail = f"runner_silence>{timeout_s:.3f}s"
                    terminate_process(proc)
                    break
                events = selector.select(timeout=remaining_s)
            else:
                events = selector.select(timeout=None)

            if not events:
                final_status = "timeout"
                detail = f"runner_silence>{timeout_s:.3f}s"
                terminate_process(proc)
                break

            for key, _ in events:
                stream = key.fileobj
                stream_name = str(key.data)
                line = stream.readline()
                if line == "":
                    try:
                        selector.unregister(stream)
                    except Exception:
                        pass
                    continue

                stripped = line.rstrip("\r\n")
                if not stripped:
                    continue

                if not stripped.startswith(RUNNER_PREFIX):
                    ignored_output.append(f"{stream_name}:{stripped}")
                    continue

                payload_text = stripped[len(RUNNER_PREFIX) :].strip()
                try:
                    payload = json.loads(payload_text)
                except json.JSONDecodeError:
                    ignored_output.append(f"{stream_name}:INVALID_PROTOCOL:{payload_text}")
                    continue

                kind = str(payload.get("kind", ""))
                if kind == "ready":
                    ready_seen = True
                    last_runner_output_at = time.monotonic()
                    continue

                last_runner_output_at = time.monotonic()

                if kind == "progress":
                    continue

                if kind == "result":
                    result_payload = payload
                    continue

                ignored_output.append(f"{stream_name}:UNKNOWN_PROTOCOL:{payload_text}")

            if final_status == "timeout":
                break

        if final_status == "timeout":
            return final_status, None, None, detail

        if result_payload is None:
            detail = "missing_runner_result"
            if ignored_output:
                detail += f" ignored_output={ignored_output[-3:]}"
            return "error", None, None, detail

        result_status = str(result_payload.get("status", "error"))
        if result_status != "pass":
            return result_status, None, None, str(result_payload.get("error", "")).strip()

        times_payload = result_payload.get("times", [])
        if not isinstance(times_payload, list):
            return "error", None, None, f"invalid_times_payload={times_payload!r}"
        final_times = [float(value) for value in times_payload]
        sample_times_payload = result_payload.get("sample_times")
        final_sample_times: list[float | None] | None = None
        if isinstance(sample_times_payload, list):
            final_sample_times = [None if value is None else float(value) for value in sample_times_payload]
        return "pass", final_times, final_sample_times, ""
    finally:
        selector.close()
        terminate_process(proc)


def append_run_log(
    *,
    results_root: Path,
    script_name: str,
    run_id: str,
    backend: str,
    suite_name: str,
    result_name: str,
    elapsed_s: float,
    failures: int,
    out_path: Path,
    repeat_desc: str,
) -> None:
    log_path = results_root / "runs.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().isoformat(timespec="seconds")
    with log_path.open("a", encoding="utf-8") as f:
        f.write(
            f"{stamp} script={script_name} run_id={run_id} backend={backend} "
            f"suite={suite_name} result={result_name} elapsed_s={elapsed_s:.6f} "
            f"failures={failures} repeat_policy={repeat_desc} "
            f"samples_recorded=times output={out_path}\n"
        )


def default_run_id(backend: str) -> str:
    return f"{backend}_{timestamp()}"


def run_suite(
    *,
    script_name: str,
    suite_name: str,
    result_name: str,
    backend: str,
    circuits_root: Path,
    results_root: Path,
    timeout_s: float,
    repeats: int,
    small_n_repeats: int | None = None,
    small_n_threshold: int | None = None,
    skip_larger_n_after_timeout: bool = False,
    shots: int,
    run_id: str,
) -> int:
    suite_cases = load_suite_cases(suite_name)
    out_path = results_root / backend / run_id / f"{result_name}.csv"
    single_script = Path(__file__).resolve().with_name("run_single_circuit.py")

    results: list[dict[str, str]] = []
    failures = 0
    started_at = time.perf_counter()
    skip_after_timeout_n: int | None = None

    for row in suite_cases:
        circuit = row["circuit"]
        num_qubits = int(row["N"])

        if skip_after_timeout_n is not None and num_qubits > skip_after_timeout_n:
            failures += 1
            peaks = {"max_rss_mb": 0.0, "max_gpu_mem_mb": 0.0}
            results.append(
                make_result_row(
                    circuit,
                    times_value=None,
                    sample_times_value=None,
                    status="timeout",
                    peaks=peaks,
                )
            )
            print(
                f"[skip-timeout] backend={backend} suite={suite_name} circuit={circuit} "
                f"trigger_n={skip_after_timeout_n} status=timeout",
                flush=True,
            )
            continue

        circuit_repeats = repeats
        if (
            small_n_repeats is not None
            and small_n_threshold is not None
            and num_qubits <= small_n_threshold
        ):
            circuit_repeats = small_n_repeats

        cmd = [
            sys.executable,
            str(single_script),
            "--backend",
            backend,
            "--suite",
            suite_name,
            "--family",
            row["family"],
            "--num-qubits",
            str(num_qubits),
            "--circuits-root",
            str(circuits_root),
            "--repeats",
            str(circuit_repeats),
            "--shots",
            str(shots),
        ]

        proc = subprocess.Popen(
            cmd,
            text=True,
            bufsize=1,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
                timeout_s=timeout_s,
            )
        finally:
            stop_event.set()
            monitor_thread.join()

        if status == "timeout":
            failures += 1
            if skip_larger_n_after_timeout:
                skip_after_timeout_n = num_qubits
            results.append(
                make_result_row(
                    circuit,
                    times_value=None,
                    sample_times_value=None,
                    status="timeout",
                    peaks=peaks,
                )
            )
            print(
                f"[timeout] backend={backend} suite={suite_name} circuit={circuit} "
                f"timeout_s={timeout_s:.3f} repeats={circuit_repeats} detail={detail} "
                f"max_rss_mb={peaks['max_rss_mb']:.3f} max_gpu_mem_mb={peaks['max_gpu_mem_mb']:.3f}",
                flush=True,
            )
            continue

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
                f"[error] backend={backend} suite={suite_name} circuit={circuit} "
                f"status={status} repeats={circuit_repeats} detail={detail} "
                f"max_rss_mb={peaks['max_rss_mb']:.3f} "
                f"max_gpu_mem_mb={peaks['max_gpu_mem_mb']:.3f}",
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
            f"[pass] backend={backend} suite={suite_name} circuit={circuit} "
            f"repeats={circuit_repeats} num_samples={len(times_value or [])} "
            f"max_rss_mb={peaks['max_rss_mb']:.3f} max_gpu_mem_mb={peaks['max_gpu_mem_mb']:.3f}",
            flush=True,
        )

    write_csv(out_path, results)
    elapsed_s = time.perf_counter() - started_at
    repeat_desc = f"default={repeats}"
    if small_n_repeats is not None and small_n_threshold is not None:
        repeat_desc += f";n<={small_n_threshold}->{small_n_repeats}"
    if skip_larger_n_after_timeout:
        repeat_desc += ";skip_larger_after_timeout=1"
    append_run_log(
        results_root=results_root,
        script_name=script_name,
        run_id=run_id,
        backend=backend,
        suite_name=suite_name,
        result_name=result_name,
        elapsed_s=elapsed_s,
        failures=failures,
        out_path=out_path,
        repeat_desc=repeat_desc,
    )
    print(f"results_csv={out_path}", flush=True)
    print(f"wall_time_s={elapsed_s:.6f}", flush=True)
    return 1 if failures else 0
