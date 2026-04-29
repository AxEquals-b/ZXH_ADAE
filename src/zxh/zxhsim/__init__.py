from __future__ import annotations

from . import _core as _core
from .analyzer import StructureStats, analyze_circuit, analyze_qasm
from .circ_optimizer import optimize_circuit
from .qasm import load_circuit, load_circuit_transpiled, load_qasm

__version__ = _core.__version__
PrintRes = _core.PrintRes
ZXH = _core.ZXH


def init() -> None:
    fn = getattr(_core, "init", None)
    if fn is not None:
        fn()


def finalize() -> None:
    fn = getattr(_core, "finalize", None)
    if fn is not None:
        fn()


def active() -> bool:
    fn = getattr(_core, "active", None)
    if fn is not None:
        return bool(fn())
    return False


def rank() -> int:
    fn = getattr(_core, "rank", None)
    if fn is not None:
        return int(fn())
    return 0


def nprocs() -> int:
    fn = getattr(_core, "nprocs", None)
    if fn is not None:
        return int(fn())
    return 1


def make_zxh_backend(
    *,
    disable_x: bool = False,
    eager_expand_all: bool = False,
):
    from .qiskit_backend import make_zxh_backend as _make_zxh_backend

    return _make_zxh_backend(
        disable_x=disable_x,
        eager_expand_all=eager_expand_all,
    )


__all__ = [
    "PrintRes",
    "ZXH",
    "StructureStats",
    "init",
    "finalize",
    "active",
    "rank",
    "nprocs",
    "load_circuit",
    "load_circuit_transpiled",
    "load_qasm",
    "make_zxh_backend",
    "optimize_circuit",
    "analyze_circuit",
    "analyze_qasm",
]
