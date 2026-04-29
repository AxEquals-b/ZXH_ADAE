from __future__ import annotations

import unittest
from collections import Counter

from qiskit import QuantumCircuit
from qiskit.circuit.library import CCXGate, CCZGate, CZGate, RZZGate, SwapGate
from qiskit.quantum_info import Operator

from zxhsim.circ_optimizer import optimize_circuit
from zxhsim.analyzer import analyze_circuit


class CircOptimizerTests(unittest.TestCase):
    def test_hh_cx_crossing_preserves_equivalence(self) -> None:
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.h(1)
        qc.cx(0, 1)
        qc.h(0)
        qc.h(1)

        optimized = optimize_circuit(qc, optimize_level=2)

        self.assertTrue(Operator(qc).equiv(Operator(optimized)))
        self.assertEqual([inst.operation.name for inst in optimized.data], ["cx"])
        self.assertEqual(optimized.data[0].qubits, (optimized.qubits[1], optimized.qubits[0]))

    def test_optimizer_reduces_effective_support_when_h_pairs_cancel(self) -> None:
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.h(1)
        qc.cx(0, 1)
        qc.h(0)
        qc.h(1)

        stats_no_opt = analyze_circuit(optimize_circuit(qc, optimize_level=0), optimize_level=0)
        stats_opt = analyze_circuit(qc, optimize_level=2)

        self.assertEqual(stats_no_opt.M, 2)
        self.assertEqual(stats_opt.M, 0)

    def test_zeroh_is_flushed_locally_at_cx_boundary(self) -> None:
        qc = QuantumCircuit(2)
        qc.rz(0.3, 0)
        qc.x(0)
        qc.rz(-0.4, 1)
        qc.cx(0, 1)

        optimized = optimize_circuit(qc, optimize_level=2)
        self.assertTrue(Operator(qc).equiv(Operator(optimized)))
        self.assertNotIn("cp", [inst.operation.name for inst in optimized.data])

    def test_nonexact_oneh_is_flushed_locally_at_cx_boundary(self) -> None:
        qc = QuantumCircuit(2)
        qc.rz(0.25, 1)
        qc.h(1)
        qc.cx(0, 1)

        optimized = optimize_circuit(qc, optimize_level=2)
        self.assertTrue(Operator(qc).equiv(Operator(optimized)))
        self.assertNotIn("cp", [inst.operation.name for inst in optimized.data])
        self.assertEqual([inst.operation.name for inst in optimized.data], ["u", "cx"])

    def test_double_exact_h_rule_preserves_equivalence(self) -> None:
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.h(1)
        qc.cx(0, 1)

        optimized = optimize_circuit(qc, optimize_level=2)
        self.assertTrue(Operator(qc).equiv(Operator(optimized)))
        self.assertEqual([inst.operation.name for inst in optimized.data], ["cx", "h", "h"])
        self.assertEqual(optimized.data[0].qubits, (optimized.qubits[1], optimized.qubits[0]))

    def test_standalone_z_is_serialized_as_rz(self) -> None:
        qc = QuantumCircuit(1)
        qc.z(0)

        optimized = optimize_circuit(qc, optimize_level=2)
        self.assertEqual([inst.operation.name for inst in optimized.data], ["rz"])

    def test_swap_is_lowered_to_three_cx_inside_optimizer(self) -> None:
        qc = QuantumCircuit(2)
        qc.append(SwapGate(), [0, 1])

        optimized = optimize_circuit(qc, optimize_level=2)
        self.assertTrue(Operator(qc).equiv(Operator(optimized)))
        self.assertEqual([inst.operation.name for inst in optimized.data], ["cx", "cx", "cx"])

    def test_cz_is_lowered_to_cp_inside_optimizer(self) -> None:
        qc = QuantumCircuit(2)
        qc.append(CZGate(), [0, 1])

        optimized = optimize_circuit(qc, optimize_level=2)
        self.assertTrue(Operator(qc).equiv(Operator(optimized)))
        self.assertEqual([inst.operation.name for inst in optimized.data], ["cp"])

    def test_rzz_is_lowered_to_cx_rz_cx_inside_optimizer(self) -> None:
        qc = QuantumCircuit(2)
        qc.append(RZZGate(0.375), [0, 1])

        optimized = optimize_circuit(qc, optimize_level=2)
        self.assertTrue(Operator(qc).equiv(Operator(optimized)))
        self.assertEqual([inst.operation.name for inst in optimized.data], ["cx", "rz", "cx"])

    def test_ccz_is_lowered_to_cx_plus_rz_inside_optimizer(self) -> None:
        qc = QuantumCircuit(3)
        qc.append(CCZGate(), [0, 1, 2])

        optimized = optimize_circuit(qc, optimize_level=2)
        self.assertTrue(Operator(qc).equiv(Operator(optimized)))
        counts = Counter(inst.operation.name for inst in optimized.data)
        self.assertEqual(set(counts), {"cx", "rz"})
        self.assertEqual(counts["cx"], 6)
        self.assertEqual(counts["rz"], 7)

    def test_ccx_is_lowered_to_h_cx_rz_inside_optimizer(self) -> None:
        qc = QuantumCircuit(3)
        qc.append(CCXGate(), [0, 1, 2])

        optimized = optimize_circuit(qc, optimize_level=2)
        self.assertTrue(Operator(qc).equiv(Operator(optimized)))
        names = [inst.operation.name for inst in optimized.data]
        self.assertNotIn("ccx", names)
        self.assertEqual(names.count("cx"), 6)
        self.assertTrue(set(names).issubset({"h", "u", "cx", "rz"}))


if __name__ == "__main__":
    unittest.main()
