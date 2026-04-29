from __future__ import annotations

from copy import deepcopy
from typing import Any


_BACKEND_ENTRIES: list[dict[str, Any]] = [
    {
        "backend": "single",
        "required": True,
        "env": {
            "ZXHSIM_BACKEND": "single",
        },
    },
    {
        "backend": "omp",
        "required": True,
        "env": {
            "ZXHSIM_BACKEND": "omp",
        },
    },
    {
        "backend": "mpi",
        "required": True,
        "env": {
            "ZXHSIM_BACKEND": "mpi",
        },
        "runtime": {
            "launcher": "mpirun",
            "nprocs": 2,
        },
    },
    {
        "backend": "mpi_omp",
        "required": True,
        "env": {
            "ZXHSIM_BACKEND": "mpi_omp",
        },
        "runtime": {
            "launcher": "mpirun",
            "nprocs": 2,
        },
    },
    {
        "backend": "cuda",
        "required": "conditional",
        "env": {
            "ZXHSIM_BACKEND": "cuda",
        },
    },
    {
        "backend": "mpi_cuda",
        "required": "conditional",
        "env": {
            "ZXHSIM_BACKEND": "mpi_cuda",
        },
        "runtime": {
            "launcher": "mpirun",
            "nprocs": 1,
        },
    },
]


def backend_entries() -> list[dict[str, Any]]:
    return deepcopy(_BACKEND_ENTRIES)


def backend_map() -> dict[str, dict[str, Any]]:
    return {str(entry["backend"]): entry for entry in backend_entries()}
