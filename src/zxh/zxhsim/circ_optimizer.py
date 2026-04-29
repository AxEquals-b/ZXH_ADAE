from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from qiskit.circuit.library import CPhaseGate, CXGate, HGate, RZGate
from qiskit.quantum_info import Operator
from qiskit.synthesis import OneQubitEulerDecomposer

from ._agl import AffineAddressMap
from .gate_sets import ZXH_FRONTEND_GATES

_ATOL = 1e-9

_I2 = np.eye(2, dtype=complex)
_X2 = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
_H2 = np.array([[1.0, 1.0], [1.0, -1.0]], dtype=complex) / math.sqrt(2.0)
_ONE_OVER_SQRT2 = 1.0 / math.sqrt(2.0)
_CX_GATE = CXGate()
_H_GATE = HGate()


def _normalize_angle(theta: float) -> float:
    return math.atan2(math.sin(theta), math.cos(theta))


def _angle_close(theta: float, target: float = 0.0, atol: float = _ATOL) -> bool:
    return abs(_normalize_angle(theta - target)) <= atol


def _phase_matrix(theta: float) -> np.ndarray:
    theta = _normalize_angle(theta)
    return np.array([[1.0, 0.0], [0.0, np.exp(1j * theta)]], dtype=complex)


def _normalize_global_phase(matrix: np.ndarray, atol: float = _ATOL) -> np.ndarray:
    out = np.asarray(matrix, dtype=complex).copy()
    for value in out.flat:
        if abs(value) > atol:
            out /= value / abs(value)
            break
    return out


def _matrix_equiv_up_to_phase(lhs: np.ndarray, rhs: np.ndarray, atol: float = _ATOL) -> bool:
    lhs = np.asarray(lhs, dtype=complex)
    rhs = np.asarray(rhs, dtype=complex)
    if lhs.shape != rhs.shape:
        return False

    scale = None
    for lval, rval in zip(lhs.flat, rhs.flat, strict=False):
        if abs(rval) > atol:
            if abs(lval) <= atol:
                return False
            scale = lval / rval
            break
        if abs(lval) > atol:
            return False

    if scale is None:
        return np.allclose(lhs, rhs, atol=atol)

    if abs(scale) <= atol:
        return False
    scale /= abs(scale)
    return np.allclose(lhs, scale * rhs, atol=atol)


@dataclass
class Pending1Q:
    matrix: np.ndarray
    kind: str
    x: int = 0
    theta: float = 0.0
    near_theta: float = 0.0
    far_theta: float = 0.0


def _empty_pending() -> Pending1Q:
    return Pending1Q(matrix=_I2.copy(), kind="EMPTY")


def _make_zeroh(x: int, theta: float) -> Pending1Q:
    x = int(bool(x))
    theta = _normalize_angle(theta)
    if x == 0 and _angle_close(theta, 0.0):
        return _empty_pending()
    matrix = (_X2 if x else _I2) @ _phase_matrix(theta)
    return Pending1Q(matrix=matrix, kind="ZERO_H", x=x, theta=theta)


def _make_oneh(near_theta: float, far_theta: float) -> Pending1Q:
    near_theta = _normalize_angle(near_theta)
    far_theta = _normalize_angle(far_theta)
    matrix = _phase_matrix(near_theta) @ _H2 @ _phase_matrix(far_theta)
    return Pending1Q(matrix=matrix, kind="ONE_H", near_theta=near_theta, far_theta=far_theta)


def _classify_pending(matrix: np.ndarray) -> Pending1Q:
    matrix = np.asarray(matrix, dtype=complex)
    if _matrix_equiv_up_to_phase(matrix, _I2):
        return _empty_pending()

    normalized = _normalize_global_phase(matrix)

    if abs(normalized[0, 1]) <= _ATOL and abs(normalized[1, 0]) <= _ATOL:
        theta = _normalize_angle(np.angle(normalized[1, 1]) - np.angle(normalized[0, 0]))
        return _make_zeroh(0, theta)

    if abs(normalized[0, 0]) <= _ATOL and abs(normalized[1, 1]) <= _ATOL:
        base = matrix[1, 0]
        if abs(base) > _ATOL:
            renorm = matrix / (base / abs(base))
            theta = _normalize_angle(np.angle(renorm[0, 1]) - np.angle(renorm[1, 0]))
            return _make_zeroh(1, theta)

    mags = np.abs(normalized)
    if np.allclose(mags, _ONE_OVER_SQRT2, atol=1e-8):
        base = normalized[0, 0]
        if abs(base) > _ATOL:
            near_theta = _normalize_angle(np.angle(normalized[1, 0]) - np.angle(base))
            far_theta = _normalize_angle(np.angle(normalized[0, 1]) - np.angle(base))
            expect_11 = -np.exp(1j * (near_theta + far_theta)) * base
            if abs(normalized[1, 1] - expect_11) <= 1e-8:
                return _make_oneh(near_theta, far_theta)

    return Pending1Q(matrix=matrix, kind="TWO_H")


def _single_qubit_matrix(op) -> np.ndarray | None:
    try:
        matrix = Operator(op).data
    except Exception:
        return None
    if matrix.shape != (2, 2):
        return None
    return np.asarray(matrix, dtype=complex)


def _pending_is_exact_h(pending: Pending1Q) -> bool:
    return pending.kind == "ONE_H" and _matrix_equiv_up_to_phase(pending.matrix, _H2)


def _inline_custom_gates(circuit, max_rounds: int = 32):
    out = circuit
    for _ in range(max_rounds):
        unsupported = {
            inst.operation.name.lower()
            for inst in out.data
            if inst.operation.name.lower() not in ZXH_FRONTEND_GATES
        }
        if not unsupported:
            return out
        out = out.decompose()
    raise NotImplementedError(
        "Circuit still contains unsupported/custom gates after bounded decomposition: "
        f"{sorted(unsupported)}"
    )


def _lowered_ccz_steps(control0: int, control1: int, target: int):
    return [
        (_CX_GATE, (control1, target)),
        (RZGate(-math.pi / 4.0), (target,)),
        (_CX_GATE, (control0, target)),
        (RZGate(math.pi / 4.0), (target,)),
        (_CX_GATE, (control1, target)),
        (RZGate(-math.pi / 4.0), (target,)),
        (_CX_GATE, (control0, target)),
        (RZGate(math.pi / 4.0), (control1,)),
        (RZGate(math.pi / 4.0), (target,)),
        (_CX_GATE, (control0, control1)),
        (RZGate(math.pi / 4.0), (control0,)),
        (RZGate(-math.pi / 4.0), (control1,)),
        (_CX_GATE, (control0, control1)),
    ]


def _lower_noncore_steps(name: str, qubits: tuple[int, ...], params: tuple[object, ...]):
    if name == "swap":
        q0, q1 = qubits
        return [
            (_CX_GATE, (q0, q1)),
            (_CX_GATE, (q1, q0)),
            (_CX_GATE, (q0, q1)),
        ]

    if name == "cz":
        q0, q1 = qubits
        return [(CPhaseGate(math.pi), (q0, q1))]

    if name == "rzz":
        q0, q1 = qubits
        (theta,) = params
        return [
            (_CX_GATE, (q0, q1)),
            (RZGate(theta), (q1,)),
            (_CX_GATE, (q0, q1)),
        ]

    if name == "ccz":
        q0, q1, q2 = qubits
        return _lowered_ccz_steps(q0, q1, q2)

    if name == "ccx":
        q0, q1, q2 = qubits
        return [
            (_H_GATE, (q2,)),
            *_lowered_ccz_steps(q0, q1, q2),
            (_H_GATE, (q2,)),
        ]

    return None


class _BoundaryScheduler:
    def __init__(
        self,
        circuit,
        *,
        optimize_level: int,
        allowed_gates: tuple[str, ...] | None = None,
    ) -> None:
        self._in = circuit
        self._out = circuit.copy_empty_like()
        self._agl = AffineAddressMap(circuit.num_qubits)
        self._pending = [_empty_pending() for _ in range(circuit.num_qubits)]
        self._decomposer = OneQubitEulerDecomposer("U")
        self._optimize_level = optimize_level
        self._enable_boundary_opt = optimize_level > 0
        self._allowed_gates = {gate.lower() for gate in allowed_gates} if allowed_gates is not None else None

    def run(self):
        for inst in self._in.data:
            op = inst.operation
            qargs = inst.qubits
            clargs = inst.clbits
            name = op.name.lower()
            qubits = [self._in.find_bit(qubit).index for qubit in qargs]

            if name in {"barrier", "measure", "reset"}:
                self._flush_all()
                self._append_raw(op, qargs, clargs)
                if name == "reset":
                    self._agl.reset()
                continue

            lowered_steps = _lower_noncore_steps(name, tuple(qubits), tuple(op.params))
            if lowered_steps is not None:
                for lowered_op, lowered_qubits in lowered_steps:
                    self._process_generated_instruction(lowered_op, lowered_qubits)
                continue

            if len(qubits) == 1:
                matrix = _single_qubit_matrix(op)
                if matrix is not None:
                    self._absorb_1q(qubits[0], matrix)
                    if not self._enable_boundary_opt:
                        self._flush_qubit(qubits[0])
                    continue
                self._flush_qubits(qubits)
                self._append_raw(op, qargs, clargs)
                self._update_agl_for_emitted_gate(name, qubits)
                continue

            if len(qubits) == 2 and name == "cx":
                if self._enable_boundary_opt:
                    self._handle_cx(qubits[0], qubits[1])
                else:
                    self._flush_qubits((qubits[0], qubits[1]))
                    self._emit_cx(qubits[0], qubits[1])
                continue

            self._flush_qubits(qubits)
            self._append_raw(op, qargs, clargs)
            self._update_agl_for_emitted_gate(name, qubits)

        self._flush_all()
        return self._out

    def _append_raw(self, op, qargs, clargs) -> None:
        self._out.append(op, qargs, clargs)

    def _append_indexed(self, op, qubits: tuple[int, ...]) -> None:
        self._out.append(op, [self._in.qubits[qubit] for qubit in qubits], [])

    def _emit_rz(self, qubit: int, theta: float) -> None:
        theta = _normalize_angle(theta)
        if _angle_close(theta, 0.0):
            return
        self._out.rz(theta, self._in.qubits[qubit])

    def _emit_x(self, qubit: int) -> None:
        self._out.x(self._in.qubits[qubit])
        self._agl.x(qubit)

    def _emit_h(self, qubit: int) -> None:
        self._agl.expand_for_qubit(qubit)
        self._out.h(self._in.qubits[qubit])

    def _emit_u(self, qubit: int, matrix: np.ndarray) -> None:
        self._agl.expand_for_qubit(qubit)
        theta, phi, lam = self._decomposer.angles(matrix)
        self._out.u(float(theta), float(phi), float(lam), self._in.qubits[qubit])

    def _emit_cx(self, control: int, target: int) -> None:
        self._out.cx(self._in.qubits[control], self._in.qubits[target])
        self._agl.cx(control, target)

    def _process_generated_instruction(self, op, qubits: tuple[int, ...]) -> None:
        name = op.name.lower()

        if len(qubits) == 1:
            matrix = _single_qubit_matrix(op)
            if matrix is not None:
                self._absorb_1q(qubits[0], matrix)
                if not self._enable_boundary_opt:
                    self._flush_qubit(qubits[0])
                return
            self._flush_qubits(qubits)
            self._append_indexed(op, qubits)
            self._update_agl_for_emitted_gate(name, list(qubits))
            return

        if len(qubits) == 2 and name == "cx":
            if self._enable_boundary_opt:
                self._handle_cx(qubits[0], qubits[1])
            else:
                self._flush_qubits((qubits[0], qubits[1]))
                self._emit_cx(qubits[0], qubits[1])
            return

        self._flush_qubits(qubits)
        self._append_indexed(op, qubits)
        self._update_agl_for_emitted_gate(name, list(qubits))

    def _absorb_1q(self, qubit: int, matrix: np.ndarray) -> None:
        pending = self._pending[qubit]
        self._pending[qubit] = _classify_pending(matrix @ pending.matrix)

    def _pending_is_exact_h(self, qubit: int) -> bool:
        pending = self._pending[qubit]
        return _pending_is_exact_h(pending)

    def _flush_nonexact_h(self, qubit: int) -> None:
        pending = self._pending[qubit]
        if pending.kind == "EMPTY":
            return
        if _pending_is_exact_h(pending):
            return
        self._flush_qubit(qubit)

    def _handle_cx(self, control: int, target: int) -> None:
        self._flush_nonexact_h(control)
        self._flush_nonexact_h(target)

        if self._pending_is_exact_h(control) and self._pending_is_exact_h(target):
            self._emit_cx(target, control)
            return

        self._flush_qubits((control, target))
        self._emit_cx(control, target)

    def _flush_all(self) -> None:
        self._flush_qubits(range(self._in.num_qubits))

    def _flush_qubits(self, qubits) -> None:
        seen: set[int] = set()
        for qubit in qubits:
            if qubit in seen:
                continue
            seen.add(qubit)
            self._flush_qubit(qubit)

    def _flush_qubit(self, qubit: int) -> None:
        pending = self._pending[qubit]
        if pending.kind == "EMPTY":
            return

        if pending.kind == "ZERO_H":
            self._emit_rz(qubit, pending.theta)
            if pending.x:
                self._emit_x(qubit)
        elif pending.kind == "ONE_H":
            if _pending_is_exact_h(pending):
                self._emit_h(qubit)
            else:
                self._emit_u(qubit, pending.matrix)
        elif pending.kind == "TWO_H":
            self._emit_u(qubit, pending.matrix)
        else:  # pragma: no cover
            raise ValueError(f"unknown pending kind: {pending.kind}")

        self._pending[qubit] = _empty_pending()

    def _update_agl_for_emitted_gate(self, name: str, qubits: list[int]) -> None:
        if name == "x":
            self._agl.x(qubits[0])
            return
        if name == "cx":
            self._agl.cx(qubits[0], qubits[1])
            return
        if name == "swap":
            q0, q1 = qubits
            self._agl.cx(q0, q1)
            self._agl.cx(q1, q0)
            self._agl.cx(q0, q1)


def optimize_circuit(
    circuit,
    optimize_level: int = 2,
    *,
    allowed_gates: tuple[str, ...] | None = None,
):
    circuit = _inline_custom_gates(circuit)
    scheduler = _BoundaryScheduler(circuit, optimize_level=optimize_level, allowed_gates=allowed_gates)
    return scheduler.run()
