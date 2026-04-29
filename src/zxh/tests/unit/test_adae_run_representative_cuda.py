from __future__ import annotations

import unittest

from qiskit import QuantumCircuit

from benchmarks.ADAE.run.scripts.run_backend_cudaq import _compile_canonical_to_cudaq_kernel
from benchmarks.ADAE.run.scripts.run_all import (
    _derive_effective_timeout_s,
    _gib_to_bytes,
)
from benchmarks.ADAE.run.scripts.runner_common import (
    build_summary_rows,
    measured_end_to_end_ms,
    per_run_timeout_s,
)


class _FakeKernel:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def qalloc(self, n: int):
        self.calls.append(("qalloc", n))
        return list(range(n))

    def x(self, q: int) -> None:
        self.calls.append(("x", q))

    def h(self, q: int) -> None:
        self.calls.append(("h", q))

    def cx(self, cq: int, q: int) -> None:
        self.calls.append(("cx", cq, q))

    def rz(self, theta: float, q: int) -> None:
        self.calls.append(("rz", theta, q))

    def u3(self, theta: float, phi: float, lam: float, q: int) -> None:
        self.calls.append(("u3", theta, phi, lam, q))

    def cr1(self, theta: float, cq: int, q: int) -> None:
        self.calls.append(("cr1", theta, cq, q))

    def mz(self, q: int) -> None:
        self.calls.append(("mz", q))


class _FakeCudaq:
    def __init__(self) -> None:
        self.kernel = _FakeKernel()

    def make_kernel(self):
        return self.kernel


class ADAERunRepresentativeCudaTests(unittest.TestCase):
    def test_gib_to_bytes_accepts_none_and_positive_values(self) -> None:
        self.assertIsNone(_gib_to_bytes(None))
        self.assertEqual(_gib_to_bytes(1.5), int(1.5 * (1024**3)))

    def test_derive_effective_timeout_s_returns_none_when_explicit_timeout_is_absent(self) -> None:
        self.assertIsNone(_derive_effective_timeout_s(timeout_s=None))

    def test_derive_effective_timeout_s_returns_explicit_timeout_only(self) -> None:
        self.assertEqual(_derive_effective_timeout_s(timeout_s=20.0), 20.0)

    def test_per_run_timeout_s_uses_budget_times_one_point_five(self) -> None:
        self.assertEqual(per_run_timeout_s(2.5), 3.75)

    def test_per_run_timeout_s_matches_default_100s_time_budget(self) -> None:
        self.assertEqual(per_run_timeout_s(100.0), 150.0)

    def test_compile_canonical_to_cudaq_kernel_preserves_cp_as_r1(self) -> None:
        qc = QuantumCircuit(2, 1)
        qc.x(0)
        qc.h(1)
        qc.cx(0, 1)
        qc.rz(0.125, 0)
        qc.u(0.2, 0.3, 0.4, 1)
        qc.cp(0.5, 0, 1)
        qc.barrier(0, 1)
        qc.measure(0, 0)

        fake_cudaq = _FakeCudaq()
        kernel = _compile_canonical_to_cudaq_kernel(qc, fake_cudaq)

        self.assertIs(kernel, fake_cudaq.kernel)
        self.assertEqual(
            fake_cudaq.kernel.calls,
            [
                ("qalloc", 2),
                ("x", 0),
                ("h", 1),
                ("cx", 0, 1),
                ("rz", 0.125, 0),
                ("u3", 0.2, 0.3, 0.4, 1),
                ("cr1", 0.5, 0, 1),
                ("mz", 0),
            ],
        )

    def test_compile_canonical_to_cudaq_kernel_rejects_reset(self) -> None:
        qc = QuantumCircuit(1)
        qc.reset(0)

        with self.assertRaises(NotImplementedError):
            _compile_canonical_to_cudaq_kernel(qc, _FakeCudaq())

    def test_compile_canonical_to_cudaq_kernel_rejects_noncanonical_gate(self) -> None:
        qc = QuantumCircuit(2)
        qc.swap(0, 1)

        with self.assertRaises(ValueError):
            _compile_canonical_to_cudaq_kernel(qc, _FakeCudaq())

    def test_measured_end_to_end_ms_uses_execute_and_sample_only(self) -> None:
        self.assertEqual(
            measured_end_to_end_ms(
                execute_ms=30.0,
                sample_ms=5.0,
            ),
            35.0,
        )

    def test_build_summary_rows_emits_warning_when_repeat_rsd_exceeds_threshold(self) -> None:
        raw_rows = [
            {
                "family": "qft",
                "N": 30,
                "backend": "zxh-cuda",
                "backend_total_ms": 100.0,
                "end_to_end_ms": 120.0,
                "kernel_build_ms": 1.0,
                "execute_ms": 90.0,
                "sample_ms": 9.0,
                "status": "pass",
            },
            {
                "family": "qft",
                "N": 30,
                "backend": "zxh-cuda",
                "backend_total_ms": 140.0,
                "end_to_end_ms": 160.0,
                "kernel_build_ms": 1.0,
                "execute_ms": 130.0,
                "sample_ms": 9.0,
                "status": "pass",
            },
        ]

        summary_rows, warnings = build_summary_rows(raw_rows)

        self.assertEqual(len(summary_rows), 1)
        self.assertEqual(len(warnings), 1)
        self.assertGreater(summary_rows[0]["end_to_end_ms_rsd_pct"], 10.0)
        self.assertIn("end_to_end_ms=", summary_rows[0]["warning"])

    def test_build_summary_rows_keeps_warning_empty_for_stable_repeats(self) -> None:
        raw_rows = [
            {
                "family": "bv",
                "N": 30,
                "backend": "cudaq",
                "backend_total_ms": 100.0,
                "end_to_end_ms": 120.0,
                "kernel_build_ms": 80.0,
                "execute_ms": 20.0,
                "sample_ms": 0.0,
                "status": "pass",
            },
            {
                "family": "bv",
                "N": 30,
                "backend": "cudaq",
                "backend_total_ms": 101.0,
                "end_to_end_ms": 121.0,
                "kernel_build_ms": 80.5,
                "execute_ms": 20.5,
                "sample_ms": 0.0,
                "status": "pass",
            },
        ]

        summary_rows, warnings = build_summary_rows(raw_rows)

        self.assertEqual(len(summary_rows), 1)
        self.assertEqual(warnings, [])
        self.assertEqual(summary_rows[0]["warning"], "")


if __name__ == "__main__":
    unittest.main()
