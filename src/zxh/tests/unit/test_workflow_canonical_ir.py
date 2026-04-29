from __future__ import annotations

import unittest

from qiskit import QuantumCircuit
from qiskit.quantum_info import Operator

from benchmarks.ADAE.prepare.generators.mqt_workflow.canonical_ir import (
    CANONICAL_QASM_GATES,
    SUPPORTED_BUT_NONCANONICAL_GATES,
    canonicalize_circuit,
)


class WorkflowCanonicalIRTests(unittest.TestCase):
    def test_crz_is_not_a_canonical_gate(self) -> None:
        self.assertNotIn("crz", CANONICAL_QASM_GATES)
        self.assertIn("h", CANONICAL_QASM_GATES)
        self.assertIn("crz", SUPPORTED_BUT_NONCANONICAL_GATES)

    def test_crz_lowers_via_qiskit_definition(self) -> None:
        qc = QuantumCircuit(2)
        qc.crz(0.37, 0, 1)

        canonical = canonicalize_circuit(qc, optimize_1q=False)
        gate_names = [inst.operation.name.lower() for inst in canonical.data]

        self.assertEqual(gate_names, ["rz", "cx", "rz", "cx"])
        self.assertTrue(Operator(qc).equiv(Operator(canonical)))

    def test_single_h_is_preserved_by_canonical_optimization(self) -> None:
        qc = QuantumCircuit(1)
        qc.h(0)

        canonical = canonicalize_circuit(qc)
        gate_names = [inst.operation.name.lower() for inst in canonical.data]

        self.assertEqual(gate_names, ["h"])
        self.assertTrue(Operator(qc).equiv(Operator(canonical)))


if __name__ == "__main__":
    unittest.main()
