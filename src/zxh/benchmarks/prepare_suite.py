#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

BENCH_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BENCH_ROOT.parent
TOOLS_DIR = REPO_ROOT / "tools"

_COLOR_ENABLED = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb"
_GREEN = "\033[32m"
_RED = "\033[31m"
_RESET = "\033[0m"

if str(BENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCH_ROOT))
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from manifest import load_manifest
from backend_registry import backend_map
from stage import prepare_backend


def _colorize(text: str, color: str) -> str:
    if not _COLOR_ENABLED:
        return text
    return f"{color}{text}{_RESET}"


def _green(text: str) -> str:
    return _colorize(text, _GREEN)


def _red(text: str) -> str:
    return _colorize(text, _RED)


def _suite_path_from_args(raw: str) -> Path:
    path = Path(raw)
    if path.suffix:
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        return path
    return (BENCH_ROOT / "suites" / f"{raw}.yaml").resolve()


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare shared stage for a benchmark suite")
    parser.add_argument("--suite", type=str, required=True, help="Suite id or suite yaml path")
    args = parser.parse_args()

    suite_path = _suite_path_from_args(args.suite)
    suite = load_manifest(suite_path)
    backend = str(suite["backend"])
    backends = backend_map()
    if backend not in backends:
        raise KeyError(f"unknown backend in suite: {backend}")

    print(f"Preparing benchmark stage for suite={suite.get('suite_id', suite_path.stem)} backend={backend} ...")
    result = prepare_backend(REPO_ROOT, backends[backend])
    if result["status"] == "built":
        print(
            f"{_green('[BUILT]')} {backend} "
            f"elapsed_s={result['elapsed_s']:.3f} "
            f"stage_dir={result['stage_dir']}"
        )
        return 0

    print(f"{_red('[FAIL]')} {backend}: {result['error']}")
    print(f"log: {result['log_path']}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
