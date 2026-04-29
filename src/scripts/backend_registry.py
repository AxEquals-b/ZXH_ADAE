#!/usr/bin/env python3
from __future__ import annotations

from typing import Any

from zxhsim import make_zxh_backend


SUPPORTED_BACKENDS = ("cuQuantum", "ddsim", "qblaze", "zxh", "zxh-nox", "zxh-exp")


def all_backends() -> list[str]:
    return list(SUPPORTED_BACKENDS)


def make_backend(backend_name: str) -> Any:
    if backend_name == "cuQuantum":
        from cusvaer.backends import StatevectorSimulator

        return StatevectorSimulator()

    if backend_name == "ddsim":
        import mqt.ddsim as ddsim

        provider = ddsim.DDSIMProvider()
        return provider.get_backend("qasm_simulator")

    if backend_name == "qblaze":
        from qblaze.qiskit import Backend

        return Backend()

    if backend_name == "zxh":
        return make_zxh_backend()

    if backend_name == "zxh-nox":
        return make_zxh_backend(disable_x=True)

    if backend_name == "zxh-exp":
        return make_zxh_backend(eager_expand_all=True)

    raise ValueError(f"Unsupported backend: {backend_name}. supported={SUPPORTED_BACKENDS}")
