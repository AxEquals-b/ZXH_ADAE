from __future__ import annotations

from collections import Counter
import importlib
import math
import sys
import unittest
from pathlib import Path

from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector


THIS_DIR = Path(__file__).resolve().parent
REPO_ROOT = THIS_DIR.parent.parent
TOOLS_DIR = REPO_ROOT / "tools"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from shared_stage import activate_shared_python_stage


def _purge_zxhsim_modules() -> None:
    doomed = [name for name in sys.modules if name == "zxhsim" or name.startswith("zxhsim.")]
    for name in doomed:
        del sys.modules[name]


class MeasureApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            stage_dir = activate_shared_python_stage(REPO_ROOT, "cuda")
        except FileNotFoundError as exc:
            raise unittest.SkipTest(str(exc)) from exc

        repo_root_resolved = REPO_ROOT.resolve()
        stage_dir_resolved = stage_dir.resolve()
        filtered_sys_path: list[str] = []
        for entry in sys.path:
            entry_path = Path(entry or ".").resolve()
            if entry_path == repo_root_resolved and entry_path != stage_dir_resolved:
                continue
            filtered_sys_path.append(entry)
        sys.path[:] = filtered_sys_path

        _purge_zxhsim_modules()
        cls.zxhsim = importlib.import_module("zxhsim")
        cls.qasm = importlib.import_module("zxhsim.qasm")

    def _compile_and_execute(self, circuit: QuantumCircuit, **sim_kwargs):
        sim = self.zxhsim.ZXH(circuit.num_qubits, **sim_kwargs)
        self.qasm.load_circuit(sim, circuit)
        sim.execute()
        return sim

    def _measure_bitstrings(
        self,
        circuit: QuantumCircuit,
        *,
        shots: int,
        seed: int | None = None,
    ) -> tuple[list[str], int]:
        self.zxhsim.init()
        try:
            sim = self._compile_and_execute(circuit)
            if seed is not None:
                sim.set_seed(seed)
            sim.measure(shots)
            rows = sim.get_results()
            return [self.qasm.bitrow_to_str(row) for row in rows], sim.measured_count()
        finally:
            self.zxhsim.finalize()

    def _sample_bitstrings(
        self,
        circuit: QuantumCircuit,
        *,
        shots: int,
        seed: int | None = None,
    ) -> list[str]:
        self.zxhsim.init()
        try:
            sim = self._compile_and_execute(circuit)
            if seed is not None:
                sim.set_seed(seed)
            rows = sim.Sampling(shots)
            return [self.qasm.bitrow_to_str(row) for row in rows]
        finally:
            self.zxhsim.finalize()

    def _get_statevector(self, circuit: QuantumCircuit, **sim_kwargs) -> list[complex]:
        self.zxhsim.init()
        try:
            sim = self._compile_and_execute(circuit, **sim_kwargs)
            return list(sim.get_state())
        finally:
            self.zxhsim.finalize()

    def _assert_statevector_close(
        self,
        actual: list[complex],
        expected: list[complex],
        *,
        places: int = 6,
    ) -> None:
        self.assertEqual(len(actual), len(expected))
        for got, want in zip(actual, expected):
            self.assertAlmostEqual(got.real, want.real, places=places)
            self.assertAlmostEqual(got.imag, want.imag, places=places)

    def _qiskit_to_cudaq_order(self, state: list[complex], num_qubits: int) -> list[complex]:
        out = [0j] * len(state)
        for idx, amp in enumerate(state):
            reversed_idx = 0
            for bit in range(num_qubits):
                reversed_idx = (reversed_idx << 1) | ((idx >> bit) & 1)
            out[reversed_idx] = amp
        return out

    def test_measure_zero_shots_returns_empty_result(self) -> None:
        qc = QuantumCircuit(1)
        qc.h(0)

        self.zxhsim.init()
        try:
            sim = self._compile_and_execute(qc)
            sim.measure(0)
            self.assertEqual(sim.measured_count(), 0)
            self.assertEqual(sim.get_results(), [])
        finally:
            self.zxhsim.finalize()

    def test_get_state_matches_cudaq_order_for_asymmetric_basis_state(self) -> None:
        qc = QuantumCircuit(2)
        qc.x(0)

        actual = self._get_statevector(qc)
        expected = self._qiskit_to_cudaq_order(list(Statevector.from_instruction(qc).data), qc.num_qubits)
        self._assert_statevector_close(actual, expected)

    def test_get_state_preserves_global_phase_accumulated_by_rz(self) -> None:
        qc = QuantumCircuit(1)
        qc.rz(math.pi, 0)

        actual = self._get_statevector(qc)
        expected = list(Statevector.from_instruction(qc).data)
        self._assert_statevector_close(actual, expected)

    def test_get_state_matches_cudaq_order_for_general_single_qubit_u(self) -> None:
        qc = QuantumCircuit(2)
        qc.u(0.3, 0.4, 0.5, 0)

        actual = self._get_statevector(qc)
        expected = self._qiskit_to_cudaq_order(list(Statevector.from_instruction(qc).data), qc.num_qubits)
        self._assert_statevector_close(actual, expected)

    def test_get_state_matches_expected_when_disable_x_executes_explicit_kernels(self) -> None:
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 1)
        qc.x(2)
        qc.cx(1, 2)
        qc.u(0.2, 0.4, 0.1, 1)

        actual = self._get_statevector(qc, disable_x=True)
        expected = self._qiskit_to_cudaq_order(list(Statevector.from_instruction(qc).data), qc.num_qubits)
        self._assert_statevector_close(actual, expected)

    def test_get_state_matches_expected_with_eager_expand_all_ablation(self) -> None:
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cp(0.3, 0, 1)
        qc.cx(1, 2)
        qc.rz(0.4, 2)

        actual = self._get_statevector(qc, eager_expand_all=True)
        expected = self._qiskit_to_cudaq_order(list(Statevector.from_instruction(qc).data), qc.num_qubits)
        self._assert_statevector_close(actual, expected)

    def test_get_state_matches_expected_with_combined_disable_x_and_eager_expand_all(self) -> None:
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 1)
        qc.x(2)
        qc.cx(1, 2)
        qc.h(2)

        actual = self._get_statevector(qc, disable_x=True, eager_expand_all=True)
        expected = self._qiskit_to_cudaq_order(list(Statevector.from_instruction(qc).data), qc.num_qubits)
        self._assert_statevector_close(actual, expected)

    def test_measure_preserves_affine_mapping_and_cached_results(self) -> None:
        qc = QuantumCircuit(3)
        qc.x(0)
        qc.cx(0, 1)
        qc.cx(1, 2)

        self.zxhsim.init()
        try:
            sim = self._compile_and_execute(qc)
            sim.measure(64)
            first = [self.qasm.bitrow_to_str(row) for row in sim.get_results()]
            second = [self.qasm.bitrow_to_str(row) for row in sim.get_results()]
            self.assertEqual(sim.measured_count(), 64)
            self.assertEqual(first, second)
            self.assertEqual(set(first), {"111"})
        finally:
            self.zxhsim.finalize()

    def test_measure_bell_distribution_matches_support_and_balance(self) -> None:
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.cx(0, 1)

        bitstrings, measured = self._measure_bitstrings(qc, shots=4096, seed=20260407)
        counts = Counter(bitstrings)

        self.assertEqual(measured, 4096)
        self.assertEqual(set(counts), {"00", "11"})
        self.assertAlmostEqual(counts["00"] / measured, 0.5, delta=0.05)
        self.assertAlmostEqual(counts["11"] / measured, 0.5, delta=0.05)

    def test_measure_u3_batch_local_no_expand_cluster_preserves_result(self) -> None:
        qc = QuantumCircuit(2)
        qc.h(0)
        qc.h(1)
        qc.x(0)
        qc.h(0)
        qc.h(1)

        bitstrings, measured = self._measure_bitstrings(qc, shots=128, seed=20260409)

        self.assertEqual(measured, 128)
        self.assertEqual(set(bitstrings), {"00"})

    def test_measure_is_seed_reproducible_and_matches_sampling_wrapper(self) -> None:
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cp(0.37, 0, 1)
        qc.h(1)
        qc.cx(1, 2)

        expected, measured = self._measure_bitstrings(qc, shots=256, seed=31415926)
        replay, replay_measured = self._measure_bitstrings(qc, shots=256, seed=31415926)
        wrapped = self._sample_bitstrings(qc, shots=256, seed=31415926)

        self.assertEqual(measured, 256)
        self.assertEqual(replay_measured, 256)
        self.assertEqual(replay, expected)
        self.assertEqual(wrapped, expected)

    def test_sample_counts_matches_sampling_wrapper(self) -> None:
        qc = QuantumCircuit(3)
        qc.h(0)
        qc.cx(0, 1)
        qc.h(2)

        self.zxhsim.init()
        try:
            sim = self._compile_and_execute(qc)
            sim.set_seed(27182818)
            native_counts = dict(sim.sample_counts(8))

            sim.set_seed(27182818)
            wrapped_counts = Counter(
                self.qasm.bitrow_to_str(row) for row in sim.Sampling(8)
            )

            self.assertEqual(native_counts, dict(wrapped_counts))
        finally:
            self.zxhsim.finalize()

    def test_crz_matches_expected_interference_distribution(self) -> None:
        qc = QuantumCircuit(2)
        qc.x(0)
        qc.h(1)
        qc.crz(0.6, 0, 1)
        qc.h(1)

        bitstrings, measured = self._measure_bitstrings(qc, shots=4096, seed=20260408)
        counts = Counter(bitstrings)
        p_zero = counts["01"] / measured
        p_one = counts["11"] / measured

        self.assertEqual(measured, 4096)
        self.assertEqual(set(counts), {"01", "11"})
        self.assertAlmostEqual(p_zero, math.cos(0.6 / 2.0) ** 2, delta=0.03)
        self.assertAlmostEqual(p_one, math.sin(0.6 / 2.0) ** 2, delta=0.03)


if __name__ == "__main__":
    unittest.main()
