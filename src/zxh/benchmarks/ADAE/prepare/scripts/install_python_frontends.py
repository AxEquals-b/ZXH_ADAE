#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
from datetime import datetime
from importlib import metadata
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
ADAE_ROOT = REPO_ROOT / "benchmarks" / "ADAE"
ENV_RESULTS_ROOT = ADAE_ROOT / "results" / "prepare" / "env"

PACKAGE_SPECS = [
    {"label": "cudaq", "dist": "cudaq", "import_name": "cudaq"},
    {"label": "ddsim", "dist": "mqt.ddsim", "import_name": "mqt.ddsim"},
    {"label": "qblaze", "dist": "qblaze", "import_name": "qblaze"},
]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install baseline Python frontends and record an environment snapshot for ADAE prepare."
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        help="Optional output directory name under benchmarks/ADAE/results/prepare/env/.",
    )
    return parser.parse_args()


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _run_install(spec: dict[str, str], log_dir: Path) -> dict[str, Any]:
    dist = spec["dist"]
    cmd = [sys.executable, "-m", "pip", "install", dist]
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    log_path = log_dir / f"{dist.replace('.', '_')}.log"
    log_path.write_text(
        f"$ {' '.join(cmd)}\nreturncode={proc.returncode}\n\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}\n",
        encoding="utf-8",
    )

    row: dict[str, Any] = {
        "label": spec["label"],
        "dist": dist,
        "import_name": spec["import_name"],
        "command": cmd,
        "returncode": proc.returncode,
        "log_path": str(log_path),
    }
    if proc.returncode != 0:
        row["status"] = "install_failed"
        return row

    try:
        module = importlib.import_module(spec["import_name"])
        row["status"] = "installed"
        row["version"] = metadata.version(dist)
        row["module_path"] = getattr(module, "__file__", None)
    except Exception as exc:
        row["status"] = "import_failed"
        row["error"] = f"{type(exc).__name__}: {exc}"
    return row


def _summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Python Frontend Install Summary",
        "",
        f"- run_id: `{summary['run_id']}`",
        f"- python: `{summary['python_version']}`",
        f"- python_executable: `{summary['python_executable']}`",
        f"- pip_version: `{summary['pip_version']}`",
        "",
        "| label | dist | import | version | status | log_path |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in summary["rows"]:
        lines.append(
            "| {label} | {dist} | {import_name} | {version} | {status} | {log_path} |".format(
                label=row["label"],
                dist=row["dist"],
                import_name=row["import_name"],
                version=row.get("version", ""),
                status=row["status"],
                log_path=row["log_path"],
            )
        )
        if row.get("error"):
            lines.append("")
            lines.append(f"- `{row['label']}` error: `{row['error']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = _parse_args()
    run_id = args.run_id or f"python_frontends_{_timestamp()}"
    out_dir = ENV_RESULTS_ROOT / run_id
    log_dir = out_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for spec in PACKAGE_SPECS:
        row = _run_install(spec, log_dir)
        rows.append(row)
        print(f"[{spec['label']}] status={row['status']}")
        print(f"[{spec['label']}] log={row['log_path']}")

    try:
        pip_version = metadata.version("pip")
    except Exception:
        pip_version = "unknown"

    summary = {
        "run_id": run_id,
        "python_version": sys.version,
        "python_executable": sys.executable,
        "pip_version": pip_version,
        "rows": rows,
    }
    summary_json = out_dir / "install_summary.json"
    summary_md = out_dir / "install_summary.md"
    _write_json(summary_json, summary)
    summary_md.write_text(_summary_markdown(summary), encoding="utf-8")

    print(f"summary_json={summary_json}")
    print(f"summary_md={summary_md}")
    failures = [row for row in rows if row["status"] != "installed"]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
