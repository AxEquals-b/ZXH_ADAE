from __future__ import annotations

import math
import unittest
from collections import Counter

from qiskit import QuantumCircuit
from qiskit.circuit.library import CCXGate, CCZGate, CZGate, PhaseGate, SGate, SdgGate, SwapGate, TdgGate, TGate, U1Gate, U2Gate
from qiskit.quantum_info import Operator

from zxhsim.qasm import load_circuit, load_circuit_transpiled


class _Recorder:
    def __init__(self, num_qubits: int) -> None:
        self.num_qubits = num_qubits
        self.gates: list[tuple] = []

    def clear_gates(self) -> None:
        self.gates.clear()

    def X(self, q: int) -> None:
        self.gates.append(("X", q))

    def CX(self, cq: int, q: int) -> None:
        self.gates.append(("CX", cq, q))

    def H(self, q: int) -> None:
        self.gates.append(("H", q))

    def U3(self, q: int, theta: float, lambda_: float, phi: float) -> None:
        self.gates.append(("U3", q, theta, lambda_, phi))

    def Rz(self, q: int, theta: float) -> None:
        self.gates.append(("Rz", q, theta))

    def CP(self, cq: int, q: int, theta: float) -> None:
        self.gates.append(("CP", cq, q, theta))

    def CRz(self, cq: int, q: int, theta: float) -> None:
        self.gates.append(("CRz", cq, q, theta))

    def Z(self, q: int) -> None:
        self.gates.append(("Z", q))

    def Rx(self, q: int, theta: float) -> None:
        self.gates.append(("Rx", q, theta))


def _replay(recorded: _Recorder) -> QuantumCircuit:
    qc = QuantumCircuit(recorded.num_qubits)
    for gate in recorded.gates:
        kind = gate[0]
        if kind == "X":
            qc.x(gate[1])
        elif kind == "CX":
            qc.cx(gate[1], gate[2])
        elif kind == "H":
            qc.h(gate[1])
        elif kind == "U3":
            _, q, theta, lambda_, phi = gate
            qc.u(theta, phi, lambda_, q)
        elif kind == "Rz":
            qc.rz(gate[2], gate[1])
        elif kind == "CP":
            qc.cp(gate[3], gate[1], gate[2])
        elif kind == "CRz":
            qc.crz(gate[3], gate[1], gate[2])
        elif kind == "Z":
            qc.z(gate[1])
        elif kind == "Rx":
            qc.rx(gate[2], gate[1])
        else:  # pragma: no cover
            raise AssertionError(f"unexpected recorded gate: {gate}")
    return qc


class LoadCircuitTests(unittest.TestCase):
    def _load(self, circuit: QuantumCircuit, optimize_level: int | None = 0) -> _Recorder:
        recorder = _Recorder(circuit.num_qubits)
        load_circuit(recorder, circuit, optimize_level=optimize_level)
        return recorder

    def _load_transpiled(self, circuit: QuantumCircuit) -> _Recorder:
        recorder = _Recorder(circuit.num_qubits)
        load_circuit_transpiled(recorder, circuit)
        return recorder

    def _assert_equiv(self, circuit: QuantumCircuit, recorder: _Recorder) -> None:
        lowered = _replay(recorder)
        self.assertTrue(
            Operator(circuit).equiv(Operator(lowered)),
            msg=f"lowered circuit is not equivalent:\nsource={circuit}\nlowered={lowered}",
        )

    def test_phase_like_gates_lower_to_single_rz(self) -> None:
        cases = [
            ("p", PhaseGate(0.37), 0.37),
            ("u1", U1Gate(-0.41), -0.41),
            ("t", TGate(), math.pi / 4.0),
            ("tdg", TdgGate(), -math.pi / 4.0),
            ("s", SGate(), math.pi / 2.0),
            ("sdg", SdgGate(), -math.pi / 2.0),
        ]
        for name, gate, expected_theta in cases:
            with self.subTest(name=name):
                qc = QuantumCircuit(1)
                qc.append(gate, [0])
                recorder = self._load(qc, optimize_level=0)
                self.assertEqual(len(recorder.gates), 1)
                kind, q, theta = recorder.gates[0]
                self.assertEqual(kind, "Rz")
                self.assertEqual(q, 0)
                self.assertAlmostEqual(theta, expected_theta)
                self._assert_equiv(qc, recorder)

    def test_u2_lowers_to_single_u3(self) -> None:
        phi = 0.23
        lam = -0.71
        qc = QuantumCircuit(1)
        qc.append(U2Gate(phi, lam), [0])
        recorder = self._load(qc, optimize_level=0)
        self.assertEqual(len(recorder.gates), 1)
        kind, q, theta, lambda_, phi_out = recorder.gates[0]
        self.assertEqual(kind, "U3")
        self.assertEqual(q, 0)
        self.assertAlmostEqual(theta, math.pi / 2.0)
        self.assertAlmostEqual(lambda_, lam)
        self.assertAlmostEqual(phi_out, phi)
        self._assert_equiv(qc, recorder)

    def test_swap_lowers_to_three_cx(self) -> None:
        qc = QuantumCircuit(2)
        qc.append(SwapGate(), [0, 1])
        recorder = self._load(qc, optimize_level=0)
        self.assertEqual(recorder.gates, [("CX", 0, 1), ("CX", 1, 0), ("CX", 0, 1)])
        self._assert_equiv(qc, recorder)

    def test_cz_lowers_to_cp_pi(self) -> None:
        qc = QuantumCircuit(2)
        qc.append(CZGate(), [0, 1])
        recorder = self._load(qc, optimize_level=0)
        self.assertEqual(len(recorder.gates), 1)
        self.assertEqual(recorder.gates[0][0], "CP")
        self.assertEqual(recorder.gates[0][1:3], (0, 1))
        self.assertAlmostEqual(recorder.gates[0][3], math.pi)
        self._assert_equiv(qc, recorder)

    def test_crz_is_forwarded_directly_by_transpiled_loader(self) -> None:
        qc = QuantumCircuit(2)
        qc.crz(0.125, 0, 1)
        recorder = self._load_transpiled(qc)
        self.assertEqual(recorder.gates, [("CRz", 0, 1, 0.125)])
        self._assert_equiv(qc, recorder)

    def test_ccz_lowers_to_cx_plus_diagonal_only(self) -> None:
        qc = QuantumCircuit(3)
        qc.append(CCZGate(), [0, 1, 2])
        recorder = self._load(qc, optimize_level=0)
        counts = Counter(gate[0] for gate in recorder.gates)
        self.assertEqual(set(counts), {"CX", "Rz"})
        self.assertEqual(counts["CX"], 6)
        self.assertEqual(counts["Rz"], 7)
        self._assert_equiv(qc, recorder)

    def test_ccx_lowers_with_only_two_h_gates(self) -> None:
        qc = QuantumCircuit(3)
        qc.append(CCXGate(), [0, 1, 2])
        recorder = self._load(qc, optimize_level=0)
        counts = Counter(gate[0] for gate in recorder.gates)
        self.assertEqual(set(counts), {"H", "CX", "Rz"})
        self.assertEqual(counts["H"], 2)
        self.assertEqual(counts["CX"], 6)
        self.assertEqual(counts["Rz"], 7)
        self._assert_equiv(qc, recorder)

    def test_transpiled_loader_accepts_native_gate_set(self) -> None:
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cp(0.25, 0, 1)
        qc.u(0.2, 0.3, 0.4, 0)
        recorder = self._load_transpiled(qc)
        self.assertEqual(len(recorder.gates), 3)

    def test_transpiled_loader_rejects_non_native_gate(self) -> None:
        qc = QuantumCircuit(2)
        qc.append(SwapGate(), [0, 1])
        recorder = _Recorder(qc.num_qubits)
        with self.assertRaises(NotImplementedError):
            load_circuit_transpiled(recorder, qc)

    def test_custom_gate_is_inlined_before_lowering(self) -> None:
        sub = QuantumCircuit(2, name="my_custom")
        sub.h(0)
        sub.cp(0.25, 0, 1)

        qc = QuantumCircuit(2)
        qc.append(sub.to_gate(), [0, 1])

        recorder = self._load(qc, optimize_level=0)
        self.assertEqual(recorder.gates[0], ("H", 0))
        self.assertEqual(recorder.gates[1], ("CP", 0, 1, 0.25))
        self._assert_equiv(qc, recorder)


if __name__ == "__main__":
    unittest.main()
