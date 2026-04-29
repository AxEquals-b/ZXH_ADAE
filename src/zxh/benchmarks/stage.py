from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

_FORWARDED_TOOLCHAIN_ENV_KEYS = (
    "CUB_ROOT",
    "CMAKE_PREFIX_PATH",
)


def stage_root(repo_root: Path) -> Path:
    return (repo_root / "build" / "stage").resolve()


def backend_root(repo_root: Path, backend: str) -> Path:
    return stage_root(repo_root) / backend


def build_dir(repo_root: Path, backend: str) -> Path:
    return backend_root(repo_root, backend) / "build"


def python_stage_dir(repo_root: Path, backend: str) -> Path:
    return backend_root(repo_root, backend) / "python"


def activate_python_stage(repo_root: Path, backend: str) -> Path:
    stage_dir = python_stage_dir(repo_root, backend)
    if not stage_dir.is_dir():
        raise FileNotFoundError(
            "benchmark stage not found: "
            f"{stage_dir}. Run `python benchmarks/prepare_suite.py --suite <suite>` first."
        )

    sys.meta_path = [
        finder for finder in sys.meta_path if finder.__class__.__module__ != "_zxhsim_editable"
    ]
    stage_dir_str = str(stage_dir)
    if stage_dir_str not in sys.path:
        sys.path.insert(0, stage_dir_str)
    return stage_dir


def _build_env(backend_entry: dict[str, Any]) -> dict[str, str]:
    backend = str(backend_entry["backend"])
    env = {str(key): str(value) for key, value in backend_entry.get("env", {}).items()}
    if backend in {"cuda", "mpi_cuda"}:
        for key in _FORWARDED_TOOLCHAIN_ENV_KEYS:
            value = os.environ.get(key, "")
            if value:
                env.setdefault(key, value)
    env.setdefault("USE_PYTHON", "ON")
    return env


def _pip_install_command(repo_root: Path, backend: str) -> list[str]:
    return [
        sys.executable,
        "-m",
        "pip",
        "install",
        str(repo_root),
        "--no-deps",
        "--no-build-isolation",
        "--upgrade",
        "--target",
        str(python_stage_dir(repo_root, backend)),
        "-Cbuild-dir=" + str(build_dir(repo_root, backend)),
    ]


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _validate_artifacts(repo_root: Path, backend: str) -> tuple[bool, str]:
    stage_pkg = python_stage_dir(repo_root, backend) / "zxhsim"
    core_candidates = list(stage_pkg.glob("_core*.so")) + list(stage_pkg.glob("_core*.pyd"))
    if not stage_pkg.is_dir():
        return False, f"missing package dir: {stage_pkg}"
    if not core_candidates:
        return False, f"missing extension module under: {stage_pkg}"

    driver_candidates = list(build_dir(repo_root, backend).glob("driver_cat")) + list(
        build_dir(repo_root, backend).glob("driver_cat.exe")
    )
    if not driver_candidates:
        return False, f"missing driver_cat under: {build_dir(repo_root, backend)}"

    return True, ""


def prepare_backend(repo_root: Path, backend_entry: dict[str, Any]) -> dict[str, Any]:
    backend = str(backend_entry["backend"])
    backend_dir = backend_root(repo_root, backend)
    build_dir_path = build_dir(repo_root, backend)
    stage_dir_path = python_stage_dir(repo_root, backend)
    log_path = backend_dir / "benchmark-prepare.log"

    shutil.rmtree(build_dir_path, ignore_errors=True)
    shutil.rmtree(stage_dir_path, ignore_errors=True)
    backend_dir.mkdir(parents=True, exist_ok=True)

    build_env = _build_env(backend_entry)
    env = os.environ.copy()
    env.update(build_env)
    env.setdefault("PIP_DISABLE_PIP_VERSION_CHECK", "1")
    cmd = _pip_install_command(repo_root, backend)

    cub_root = env.get("CUB_ROOT", "")
    if backend in {"cuda", "mpi_cuda"} and cub_root and not Path(cub_root).is_dir():
        result: dict[str, Any] = {
            "backend": backend,
            "build_dir": str(build_dir_path),
            "stage_dir": str(stage_dir_path),
            "log_path": str(log_path),
            "elapsed_s": 0.0,
            "command": cmd,
            "env": build_env,
            "returncode": 1,
            "status": "failed",
            "error": f"CUB_ROOT does not exist: {cub_root}",
        }
        _write_text(log_path, f"CUB_ROOT={cub_root}\nerror={result['error']}\n")
        return result

    started_at = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=repo_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    elapsed = time.perf_counter() - started_at

    log_text = (
        f"$ {' '.join(cmd)}\n"
        + "".join(f"{key}={env[key]}\n" for key in sorted(build_env))
        + f"returncode={proc.returncode}\n\n"
        f"--- stdout ---\n{proc.stdout}\n"
        f"--- stderr ---\n{proc.stderr}\n"
    )
    _write_text(log_path, log_text)

    result: dict[str, Any] = {
        "backend": backend,
        "build_dir": str(build_dir_path),
        "stage_dir": str(stage_dir_path),
        "log_path": str(log_path),
        "elapsed_s": elapsed,
        "command": cmd,
        "env": build_env,
        "returncode": proc.returncode,
    }
    if proc.returncode != 0:
        result["status"] = "failed"
        result["error"] = "pip install failed"
        return result

    ok, error = _validate_artifacts(repo_root, backend)
    if not ok:
        result["status"] = "failed"
        result["error"] = error
        return result

    result["status"] = "built"
    return result
