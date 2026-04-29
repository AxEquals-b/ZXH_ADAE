#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ADAE_ROOT = REPO_ROOT / "benchmarks" / "ADAE"
DEFAULT_MANIFEST = (
    ADAE_ROOT / "results" / "prepare" / "workflow" / "03_pass3_canonicalize" / "canonical_manifest.json"
)
RESULTS_ROOT = ADAE_ROOT / "results" / "run" / "gpu_mem_probe"
CUDAQ_RUNNER = ADAE_ROOT / "run" / "scripts" / "run_backend_cudaq.py"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe CUDA-Q GPU memory usage on ADAE manifests.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--warmup", type=int, default=0)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--shots", type=int, default=1)
    parser.add_argument("--timeout-s", type=float, default=30.0)
    parser.add_argument("--poll-interval-s", type=float, default=0.2)
    parser.add_argument("--cudaq-target", type=str, default="nvidia")
    parser.add_argument("--run-id", type=str, default=None)
    return parser.parse_args()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _resolve_repo_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


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


def _predicted_gpu_bytes(num_qubits: int) -> int:
    return 8 * (1 << num_qubits)


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


def _monitor_child_gpu_memory(proc: subprocess.Popen[str], *, timeout_s: float, poll_interval_s: float) -> tuple[int, float, bool]:
    t0 = time.perf_counter()
    peak_gpu_mib = 0
    timed_out = False

    while True:
        ret = proc.poll()
        try:
            peak_gpu_mib = max(peak_gpu_mib, _query_pid_gpu_memory_mib(proc.pid))
        except Exception:
            pass
        if ret is not None:
            break
        elapsed_s = time.perf_counter() - t0
        if elapsed_s >= timeout_s:
            timed_out = True
            proc.kill()
            proc.wait()
            break
        time.sleep(poll_interval_s)

    elapsed_s = time.perf_counter() - t0
    return peak_gpu_mib, elapsed_s, timed_out


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

    run_id = args.run_id or f"cudaq_gpu_mem_probe_{_timestamp()}"
    out_dir = RESULTS_ROOT / run_id
    logs_dir = out_dir / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        family = str(row["family"])
        num_qubits = int(row["N"])
        predicted_gpu_bytes = _predicted_gpu_bytes(num_qubits)
        predicted_gpu_mib = predicted_gpu_bytes / (1024**2)
        child_run_id = f"{run_id}/per_case/{index:02d}_{family}"
        log_path = logs_dir / f"{index:02d}_{family}.log"
        cmd = [
            sys.executable,
            "-u",
            str(CUDAQ_RUNNER),
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
            "--cudaq-target",
            args.cudaq_target,
            "--run-id",
            child_run_id,
        ]
        print(
            f"[probe {index}/{len(rows)}] family={family} N={num_qubits} predicted_gpu_mib={predicted_gpu_mib:.3f}",
            flush=True,
        )
        with log_path.open("w", encoding="utf-8") as log_file:
            proc = subprocess.Popen(
                cmd,
                cwd=REPO_ROOT,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
            )
            peak_gpu_mib, elapsed_s, timed_out = _monitor_child_gpu_memory(
                proc,
                timeout_s=args.timeout_s,
                poll_interval_s=args.poll_interval_s,
            )
            returncode = proc.returncode

        ratio = (peak_gpu_mib / predicted_gpu_mib) if predicted_gpu_mib > 0 else None
        status = "timeout" if timed_out else ("pass" if returncode == 0 else f"error({returncode})")
        result_row = {
            "family": family,
            "N": num_qubits,
            "qasm_path": str(row.get("canonical_qasm3_path", "")),
            "predicted_gpu_bytes": predicted_gpu_bytes,
            "predicted_gpu_mib": predicted_gpu_mib,
            "observed_peak_gpu_mib": peak_gpu_mib,
            "observed_peak_gpu_bytes": peak_gpu_mib * 1024 * 1024,
            "observed_to_predicted_ratio": ratio,
            "timeout_s": args.timeout_s,
            "elapsed_s": elapsed_s,
            "returncode": returncode,
            "status": status,
            "log_path": _repo_rel(log_path),
        }
        results.append(result_row)
        print(
            f"[probe {index}/{len(rows)}] done family={family} status={status} "
            f"observed_peak_gpu_mib={peak_gpu_mib} ratio={ratio}",
            flush=True,
        )

    metadata = {
        "run_id": run_id,
        "manifest_path": _repo_rel(manifest_path),
        "warmup": args.warmup,
        "repeats": args.repeats,
        "shots": args.shots,
        "timeout_s": args.timeout_s,
        "poll_interval_s": args.poll_interval_s,
        "cudaq_target": args.cudaq_target,
        "prediction_model": "8B * 2^N",
        "notes": "observed_peak_gpu_mib is sampled from nvidia-smi query-compute-apps and matched by child PID",
    }

    json_path = out_dir / "results.json"
    csv_path = out_dir / "results.csv"
    _write_json(json_path, {"metadata": metadata, "rows": results})
    _write_csv(
        csv_path,
        results,
        [
            "family",
            "N",
            "qasm_path",
            "predicted_gpu_bytes",
            "predicted_gpu_mib",
            "observed_peak_gpu_mib",
            "observed_peak_gpu_bytes",
            "observed_to_predicted_ratio",
            "timeout_s",
            "elapsed_s",
            "returncode",
            "status",
            "log_path",
        ],
    )
    print(f"json={json_path}", flush=True)
    print(f"csv={csv_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
