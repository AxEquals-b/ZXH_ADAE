from __future__ import annotations

from pathlib import Path
import sys


def shared_stage_root(repo_root: Path) -> Path:
    return (repo_root / "build" / "stage").resolve()


def shared_backend_root(repo_root: Path, backend: str) -> Path:
    return shared_stage_root(repo_root) / backend


def shared_build_dir(repo_root: Path, backend: str) -> Path:
    return shared_backend_root(repo_root, backend) / "build"


def shared_python_stage_dir(repo_root: Path, backend: str) -> Path:
    return shared_backend_root(repo_root, backend) / "python"


def activate_shared_python_stage(repo_root: Path, backend: str) -> Path:
    stage_dir = shared_python_stage_dir(repo_root, backend)
    if not stage_dir.is_dir():
        raise FileNotFoundError(
            "shared stage not found: "
            f"{stage_dir}. Run `python tests/integration/build_matrix.py --backend {backend}` first."
        )

    sys.meta_path = [
        finder for finder in sys.meta_path if finder.__class__.__module__ != "_zxhsim_editable"
    ]
    stage_dir_str = str(stage_dir)
    if stage_dir_str not in sys.path:
        sys.path.insert(0, stage_dir_str)
    return stage_dir
