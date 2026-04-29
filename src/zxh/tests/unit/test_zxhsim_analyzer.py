from __future__ import annotations

import unittest

from qiskit import QuantumCircuit

from zxhsim.analyzer import analyze_circuit
from zxhsim.circ_optimizer import optimize_circuit


class ZXHSimAnalyzerTests(unittest.TestCase):
    def test_ghz_has_m_equals_one(self) -> None:
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 1)
        qc.cx(1, 2)

        stats = analyze_circuit(qc, optimize_level=2)

        self.assertEqual(stats.M, 1)
        self.assertEqual(stats.compiled_gate_count, 3)
        self.assertEqual(stats.compiled_x_type_count, 2)
        self.assertEqual(stats.compiled_h_type_count, 1)
        self.assertAlmostEqual(stats.rho_M, 1.0 / 3.0)
        self.assertAlmostEqual(stats.rho_X, 2.0 / 3.0)
        self.assertAlmostEqual(stats.rho_L, 1.0)

    def test_lazy_expansion_ratio_uses_post_gate_width(self) -> None:
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cp(0.25, 0, 1)
        qc.h(1)

        stats = analyze_circuit(qc, optimize_level=2)

        self.assertEqual(stats.M, 2)
        self.assertEqual(stats.compiled_gate_count, 3)
        self.assertEqual(stats.compiled_z_type_count, 1)
        self.assertEqual(stats.compiled_h_type_count, 2)
        self.assertEqual(stats.zh_gate_count, 3)
        self.assertEqual(stats.zh_traversal_volume, 8)
        self.assertEqual(stats.zh_full_width_volume, 12)
        self.assertAlmostEqual(stats.rho_L, 2.0 / 3.0)

    def test_x_only_circuit_has_full_transport_ratio(self) -> None:
        qc = QuantumCircuit(4)
        qc.x(0)
        qc.cx(0, 1)
        qc.swap(1, 2)

        stats = analyze_circuit(optimize_circuit(qc, optimize_level=0), optimize_level=0)

        self.assertEqual(stats.M, 0)
        self.assertEqual(stats.compiled_gate_count, 5)
        self.assertEqual(stats.compiled_x_type_count, 5)
        self.assertEqual(stats.compiled_z_type_count, 0)
        self.assertEqual(stats.compiled_h_type_count, 0)
        self.assertAlmostEqual(stats.rho_M, 0.0)
        self.assertAlmostEqual(stats.rho_X, 1.0)
        self.assertIsNone(stats.rho_L)

    def test_nontranspiled_circuit_is_rejected_when_opt_level_is_zero(self) -> None:
        qc = QuantumCircuit(2)
        qc.swap(0, 1)
        with self.assertRaises(NotImplementedError):
            analyze_circuit(qc, optimize_level=0)


if __name__ == "__main__":
    unittest.main()
