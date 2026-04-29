from __future__ import annotations

import math
from typing import Any


CANONICAL_QASM_GATES = ("x", "cx", "rz", "cp", "h", "u", "measure", "reset", "barrier")
CANONICAL_BASIS_GATES = ("x", "cx", "rz", "cp", "h", "u")
CANONICAL_X_TYPE_GATES = ("x", "cx")
CANONICAL_Z_TYPE_GATES = ("rz", "cp")
CANONICAL_H_TYPE_GATES = ("h", "u")
DEFAULT_CANONICAL_DECOMPOSE_REPS = 8
DEFAULT_CANONICAL_OPT_LEVEL = 2

# These gates may appear in raw workloads or baseline inputs, but the
# experiment-side canonical pass rewrites them into the canonical gate set.
SUPPORTED_BUT_NONCANONICAL_GATES = (
    "z",
    "h",
    "s",
    "sdg",
    "t",
    "tdg",
    "rx",
    "ry",
    "p",
    "u1",
    "u2",
    "u3",
    "swap",
    "cz",
    "rzz",
    "crz",
    "ccx",
    "ccz",
)


def _require_qiskit_quantum_circuit():
    try:
        from qiskit import QuantumCircuit
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "Experiment-side canonicalization requires qiskit. Install it with `pip install qiskit`."
        ) from exc
    return QuantumCircuit


def _qubit_index(circuit, qubit) -> int:
    return circuit.find_bit(qubit).index


def _clbit_index(circuit, clbit) -> int:
    return circuit.find_bit(clbit).index


def _to_float(value) -> float:
    try:
        return float(value)
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"Cannot evaluate symbolic parameter {value!r} to float.") from exc


class _CanonicalBuilder:
    def __init__(self, num_qubits: int, num_clbits: int, name: str | None = None) -> None:
        QuantumCircuit = _require_qiskit_quantum_circuit()
        self.circuit = QuantumCircuit(num_qubits, num_clbits, name=name)

    def X(self, q: int) -> None:
        self.circuit.x(q)

    def CX(self, cq: int, q: int) -> None:
        self.circuit.cx(cq, q)

    def H(self, q: int) -> None:
        self.circuit.h(q)

    def Rz(self, q: int, theta: float) -> None:
        self.circuit.rz(theta, q)

    def U3(self, q: int, theta: float, lambda_: float, phi: float) -> None:
        self.circuit.u(theta, phi, lambda_, q)

    def Rx(self, q: int, theta: float) -> None:
        self.U3(q, theta, math.pi / 2.0, -math.pi / 2.0)

    def Z(self, q: int) -> None:
        self.Rz(q, math.pi)

    def CP(self, cq: int, q: int, theta: float) -> None:
        self.circuit.cp(theta, cq, q)

    def measure(self, q: int, c: int) -> None:
        self.circuit.measure(q, c)

    def reset(self, q: int) -> None:
        self.circuit.reset(q)

    def barrier(self, qubits: list[int]) -> None:
        if qubits:
            self.circuit.barrier(*qubits)


def _emit_swap(builder: _CanonicalBuilder, q0: int, q1: int) -> None:
    builder.CX(q0, q1)
    builder.CX(q1, q0)
    builder.CX(q0, q1)


def _emit_phase(builder: _CanonicalBuilder, q: int, theta: float) -> None:
    builder.Rz(q, theta)


def _emit_t(builder: _CanonicalBuilder, q: int) -> None:
    _emit_phase(builder, q, math.pi / 4.0)


def _emit_tdg(builder: _CanonicalBuilder, q: int) -> None:
    _emit_phase(builder, q, -math.pi / 4.0)


def _emit_ccz(builder: _CanonicalBuilder, c0: int, c1: int, target: int) -> None:
    builder.CX(c1, target)
    _emit_tdg(builder, target)
    builder.CX(c0, target)
    _emit_t(builder, target)
    builder.CX(c1, target)
    _emit_tdg(builder, target)
    builder.CX(c0, target)
    _emit_t(builder, c1)
    _emit_t(builder, target)
    builder.CX(c0, c1)
    _emit_t(builder, c0)
    _emit_tdg(builder, c1)
    builder.CX(c0, c1)


def _emit_ccx(builder: _CanonicalBuilder, c0: int, c1: int, target: int) -> None:
    builder.H(target)
    _emit_ccz(builder, c0, c1, target)
    builder.H(target)


def _lower_instruction(
    *,
    builder: _CanonicalBuilder,
    root_circuit,
    inst,
    qubit_map: dict[Any, Any],
    clbit_map: dict[Any, Any],
    depth_left: int,
) -> None:
    op = inst.operation
    qargs = [qubit_map.get(qubit, qubit) for qubit in inst.qubits]
    cargs = [clbit_map.get(clbit, clbit) for clbit in inst.clbits]
    name = op.name.lower()

    if name == "barrier":
        builder.barrier([_qubit_index(root_circuit, qubit) for qubit in qargs])
        return

    if name == "measure":
        if len(qargs) != 1 or len(cargs) != 1:
            raise NotImplementedError("Only one-qubit one-clbit measurements are supported in canonicalization.")
        builder.measure(_qubit_index(root_circuit, qargs[0]), _clbit_index(root_circuit, cargs[0]))
        return

    if name == "reset":
        if len(qargs) != 1:
            raise NotImplementedError("Only one-qubit reset is supported in canonicalization.")
        builder.reset(_qubit_index(root_circuit, qargs[0]))
        return

    if name == "id":
        return

    if name == "x":
        builder.X(_qubit_index(root_circuit, qargs[0]))
        return

    if name == "cx":
        builder.CX(_qubit_index(root_circuit, qargs[0]), _qubit_index(root_circuit, qargs[1]))
        return

    if name == "swap":
        _emit_swap(builder, _qubit_index(root_circuit, qargs[0]), _qubit_index(root_circuit, qargs[1]))
        return

    if name == "h":
        builder.H(_qubit_index(root_circuit, qargs[0]))
        return

    if name == "z":
        builder.Z(_qubit_index(root_circuit, qargs[0]))
        return

    if name == "cz":
        builder.CP(_qubit_index(root_circuit, qargs[0]), _qubit_index(root_circuit, qargs[1]), math.pi)
        return

    if name == "rz":
        builder.Rz(_qubit_index(root_circuit, qargs[0]), _to_float(op.params[0]))
        return

    if name == "rx":
        builder.Rx(_qubit_index(root_circuit, qargs[0]), _to_float(op.params[0]))
        return

    if name == "ry":
        builder.U3(_qubit_index(root_circuit, qargs[0]), _to_float(op.params[0]), 0.0, 0.0)
        return

    if name in {"p", "u1"}:
        builder.Rz(_qubit_index(root_circuit, qargs[0]), _to_float(op.params[0]))
        return

    if name == "u2":
        phi = _to_float(op.params[0])
        lam = _to_float(op.params[1])
        builder.U3(_qubit_index(root_circuit, qargs[0]), math.pi / 2.0, lam, phi)
        return

    if name == "s":
        _emit_phase(builder, _qubit_index(root_circuit, qargs[0]), math.pi / 2.0)
        return

    if name == "sdg":
        _emit_phase(builder, _qubit_index(root_circuit, qargs[0]), -math.pi / 2.0)
        return

    if name == "t":
        _emit_t(builder, _qubit_index(root_circuit, qargs[0]))
        return

    if name == "tdg":
        _emit_tdg(builder, _qubit_index(root_circuit, qargs[0]))
        return

    if name in {"u3", "u"}:
        theta = _to_float(op.params[0])
        phi = _to_float(op.params[1])
        lam = _to_float(op.params[2])
        builder.U3(_qubit_index(root_circuit, qargs[0]), theta, lam, phi)
        return

    if name == "rzz":
        theta = _to_float(op.params[0])
        q0 = _qubit_index(root_circuit, qargs[0])
        q1 = _qubit_index(root_circuit, qargs[1])
        builder.CX(q0, q1)
        builder.Rz(q1, theta)
        builder.CX(q0, q1)
        return

    if name == "cp":
        theta = _to_float(op.params[0])
        builder.CP(_qubit_index(root_circuit, qargs[0]), _qubit_index(root_circuit, qargs[1]), theta)
        return

    if name == "ccz":
        _emit_ccz(
            builder,
            _qubit_index(root_circuit, qargs[0]),
            _qubit_index(root_circuit, qargs[1]),
            _qubit_index(root_circuit, qargs[2]),
        )
        return

    if name == "ccx":
        _emit_ccx(
            builder,
            _qubit_index(root_circuit, qargs[0]),
            _qubit_index(root_circuit, qargs[1]),
            _qubit_index(root_circuit, qargs[2]),
        )
        return

    definition = getattr(op, "definition", None)
    if definition is not None and depth_left > 0 and len(definition.data) > 0:
        nested_qmap = {definition.qubits[i]: qargs[i] for i in range(min(len(definition.qubits), len(qargs)))}
        nested_cmap = {definition.clbits[i]: cargs[i] for i in range(min(len(definition.clbits), len(cargs)))}
        for nested_inst in definition.data:
            _lower_instruction(
                builder=builder,
                root_circuit=root_circuit,
                inst=nested_inst,
                qubit_map=nested_qmap,
                clbit_map=nested_cmap,
                depth_left=depth_left - 1,
            )
        return

    raise NotImplementedError(f"Unsupported gate for experiment canonicalization: {name}")


def _optimize_canonical_basis(circuit, *, optimization_level: int = DEFAULT_CANONICAL_OPT_LEVEL):
    from qiskit import transpile

    # Use Qiskit's standard preset optimization flow in a constrained
    # backend-independent basis. This keeps H as a first-class operation
    # instead of forcing every single-qubit rewrite into Euler-U form.
    return transpile(
        circuit,
        basis_gates=list(CANONICAL_BASIS_GATES),
        optimization_level=optimization_level,
    )


def canonicalize_circuit(
    circuit,
    *,
    decompose_reps: int = DEFAULT_CANONICAL_DECOMPOSE_REPS,
    optimize_1q: bool = True,
    optimization_level: int = DEFAULT_CANONICAL_OPT_LEVEL,
):
    builder = _CanonicalBuilder(circuit.num_qubits, circuit.num_clbits, name=circuit.name)
    for inst in circuit.data:
        _lower_instruction(
            builder=builder,
            root_circuit=circuit,
            inst=inst,
            qubit_map={},
            clbit_map={},
            depth_left=decompose_reps,
        )

    out = builder.circuit
    if optimize_1q:
        out = _optimize_canonical_basis(out, optimization_level=optimization_level)
    return out
