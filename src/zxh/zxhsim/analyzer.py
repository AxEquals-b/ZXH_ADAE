from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ._agl import AffineAddressMap, bit, format_mask
from .circ_optimizer import optimize_circuit
from .qasm import _validate_gate_set, load_qasm
from .gate_sets import ZXH_NATIVE_GATES


@dataclass
class StructureStats:
    compiled_gate_count: int
    compiled_x_type_count: int
    compiled_z_type_count: int
    compiled_h_type_count: int
    compiled_gate_type_counts: dict[str, int]
    M: int
    rho_X: float | None
    rho_M: float | None
    rho_L: float | None
    zh_gate_count: int
    zh_traversal_volume: int
    zh_full_width_volume: int
    clear_gates_calls: int
    expansion_event_count: int
    expansion_events: list[dict[str, Any]]
    final_affine_rows: list[str]
    final_affine_offset: str


class _AnalyzerState:
    def __init__(self, num_qubits: int) -> None:
        self.num_qubits = num_qubits
        self.clear_gates_calls = 0
        self._reset_state()

    def _reset_state(self) -> None:
        self.affine = AffineAddressMap(self.num_qubits)
        self.compiled_gate_count = 0
        self.compiled_x_type_count = 0
        self.compiled_z_type_count = 0
        self.compiled_h_type_count = 0
        self.compiled_gate_type_counts: Counter[str] = Counter()
        self.zh_gate_count = 0
        self.zh_traversal_volume = 0
        self.expansion_events: list[dict[str, Any]] = []

    def clear_gates(self) -> None:
        self.clear_gates_calls += 1
        self._reset_state()

    def _record_gate(self, gate_type: str, gate_class: str, qubits: tuple[int, ...], expanded: bool = False) -> None:
        self.compiled_gate_count += 1
        self.compiled_gate_type_counts[gate_type] += 1

        current_m = self.affine.width
        if gate_class == "X":
            self.compiled_x_type_count += 1
        elif gate_class == "Z":
            self.compiled_z_type_count += 1
            self.zh_gate_count += 1
            self.zh_traversal_volume += 1 << current_m
        elif gate_class == "H":
            self.compiled_h_type_count += 1
            self.zh_gate_count += 1
            self.zh_traversal_volume += 1 << current_m
        else:  # pragma: no cover
            raise ValueError(f"Unknown gate class: {gate_class}")

        if expanded:
            self.expansion_events.append(
                {
                    "compiled_gate_index": self.compiled_gate_count,
                    "gate_type": gate_type,
                    "qubits": list(qubits),
                    "m_after": current_m,
                }
            )

    def _solve_expand(self, qubit: int) -> bool:
        return self.affine.expand_for_qubit(qubit)

    def X(self, q: int) -> None:
        self.affine.x(q)
        self._record_gate("X", "X", (q,))

    def CX(self, cq: int, q: int) -> None:
        self.affine.cx(cq, q)
        self._record_gate("CX", "X", (cq, q))

    def H(self, q: int) -> None:
        expanded = self._solve_expand(q)
        self._record_gate("H", "H", (q,), expanded=expanded)

    def U3(self, q: int, theta: float, lambda_: float, phi: float) -> None:
        del theta, lambda_, phi
        expanded = self._solve_expand(q)
        self._record_gate("U3", "H", (q,), expanded=expanded)

    def Rx(self, q: int, theta: float) -> None:
        self.U3(q, theta, math.pi / 2.0, -math.pi / 2.0)

    def Z(self, q: int) -> None:
        self._record_gate("Z", "Z", (q,))

    def Rz(self, q: int, theta: float) -> None:
        del theta
        self._record_gate("Rz", "Z", (q,))

    def CP(self, cq: int, q: int, theta: float) -> None:
        del theta
        self._record_gate("CP", "Z", (cq, q))

    def CRz(self, cq: int, q: int, theta: float) -> None:
        del theta
        self._record_gate("CRz", "Z", (cq, q))

    def stats(self) -> StructureStats:
        compiled_gate_count = self.compiled_gate_count
        M = self.affine.width
        rho_X = self.compiled_x_type_count / compiled_gate_count if compiled_gate_count > 0 else None
        rho_M = M / self.num_qubits if self.num_qubits > 0 else None
        zh_full_width_volume = self.zh_gate_count * (1 << M) if self.zh_gate_count > 0 else 0
        rho_L = self.zh_traversal_volume / zh_full_width_volume if zh_full_width_volume > 0 else None

        final_affine_rows = [format_mask(self.affine.get_row(row), M) for row in range(self.num_qubits)]
        final_affine_offset = format_mask(self.affine.offset_mask, self.num_qubits)

        return StructureStats(
            compiled_gate_count=compiled_gate_count,
            compiled_x_type_count=self.compiled_x_type_count,
            compiled_z_type_count=self.compiled_z_type_count,
            compiled_h_type_count=self.compiled_h_type_count,
            compiled_gate_type_counts=dict(sorted(self.compiled_gate_type_counts.items())),
            M=M,
            rho_X=rho_X,
            rho_M=rho_M,
            rho_L=rho_L,
            zh_gate_count=self.zh_gate_count,
            zh_traversal_volume=self.zh_traversal_volume,
            zh_full_width_volume=zh_full_width_volume,
            clear_gates_calls=self.clear_gates_calls,
            expansion_event_count=len(self.expansion_events),
            expansion_events=list(self.expansion_events),
            final_affine_rows=final_affine_rows,
            final_affine_offset=final_affine_offset,
        )


def _load_any_qasm(path: str | Path):
    qasm_path = Path(path)
    if qasm_path.suffix.lower() == ".qasm3":
        from qiskit.qasm3 import loads as load_qasm3

        return load_qasm3(qasm_path.read_text(encoding="utf-8"))
    return load_qasm(qasm_path)


def analyze_circuit(
    circuit,
    *,
    optimize_level: int | None = None,
) -> StructureStats:
    if optimize_level is None:
        optimize_level = 0
    if optimize_level > 0:
        circuit = optimize_circuit(circuit, optimize_level=optimize_level)

    _validate_gate_set(circuit, ZXH_NATIVE_GATES)
    sim = _AnalyzerState(circuit.num_qubits)
    for inst in circuit.data:
        name = inst.operation.name.lower()
        qubits = [circuit.find_bit(qubit).index for qubit in inst.qubits]

        if name in {"barrier", "measure", "id"}:
            continue
        if name == "reset":
            sim.clear_gates()
            continue
        if name == "x":
            sim.X(qubits[0])
            continue
        if name == "cx":
            sim.CX(qubits[0], qubits[1])
            continue
        if name == "h":
            sim.H(qubits[0])
            continue
        if name in {"u", "u3"}:
            sim.U3(qubits[0], 0.0, 0.0, 0.0)
            continue
        if name == "rx":
            sim.Rx(qubits[0], 0.0)
            continue
        if name == "z":
            sim.Z(qubits[0])
            continue
        if name == "rz":
            sim.Rz(qubits[0], 0.0)
            continue
        if name == "cp":
            sim.CP(qubits[0], qubits[1], 0.0)
            continue
        if name == "crz":
            sim.CRz(qubits[0], qubits[1], 0.0)
            continue
        raise NotImplementedError(f"Unsupported gate for ZXH analysis: {name}")
    return sim.stats()


def analyze_qasm(
    path: str | Path,
    *,
    optimize_level: int | None = None,
) -> StructureStats:
    circuit = _load_any_qasm(path)
    return analyze_circuit(circuit, optimize_level=optimize_level)
