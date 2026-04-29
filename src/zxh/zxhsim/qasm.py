from __future__ import annotations
from collections import Counter
from pathlib import Path

from .circ_optimizer import optimize_circuit
from .gate_sets import ZXH_FRONTEND_GATES, ZXH_NATIVE_GATES

_ZXH_SUPPORTED_GATES = ZXH_FRONTEND_GATES
_ZXH_CORE_GATES = ZXH_NATIVE_GATES


def _require_qiskit_quantum_circuit():
    try:
        from qiskit import QuantumCircuit
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "读取 QASM 电路需要 qiskit。请先安装：`pip install qiskit`。"
        ) from exc
    return QuantumCircuit


def _qubit_index(circuit, qubit) -> int:
    return circuit.find_bit(qubit).index


def _to_float(value) -> float:
    try:
        return float(value)
    except Exception as exc:  # pragma: no cover
        raise ValueError(f"Cannot evaluate symbolic parameter {value!r} to float.") from exc


def load_qasm(path: str | Path):
    qasm_path = Path(path)
    if not qasm_path.is_file():
        raise FileNotFoundError(f"QASM 文件不存在: {qasm_path}")

    QuantumCircuit = _require_qiskit_quantum_circuit()
    return QuantumCircuit.from_qasm_file(str(qasm_path))


def _validate_gate_set(circuit, allowed_gates: frozenset[str]) -> None:
    unsupported = sorted(
        {inst.operation.name.lower() for inst in circuit.data if inst.operation.name.lower() not in allowed_gates}
    )
    if unsupported:
        raise NotImplementedError(
            "Circuit contains gates outside the allowed set: "
            f"{unsupported}. allowed_gates={sorted(allowed_gates)}"
        )


def load_circuit(
    sim,
    circuit,
    optimize_level: int | None = None,
) -> None:
    if optimize_level is None:
        optimize_level = 0

    transpiled = optimize_circuit(circuit, optimize_level=optimize_level)
    load_circuit_transpiled(sim, transpiled)


def load_circuit_transpiled(sim, circuit) -> None:
    _validate_gate_set(circuit, _ZXH_CORE_GATES)
    for inst in circuit.data:
        op = inst.operation
        qargs = inst.qubits
        name = op.name.lower()

        if name == "barrier":
            sim.Barrier()
            continue
        if name == "measure":
            continue
        if name == "id":
            continue
        if name == "reset":
            sim.clear_gates()
            continue

        if name == "x":
            sim.X(_qubit_index(circuit, qargs[0]))
            continue

        if name == "cx":
            sim.CX(_qubit_index(circuit, qargs[0]), _qubit_index(circuit, qargs[1]))
            continue

        if name == "h":
            sim.H(_qubit_index(circuit, qargs[0]))
            continue

        if name == "z":
            sim.Z(_qubit_index(circuit, qargs[0]))
            continue

        if name == "rz":
            theta = _to_float(op.params[0])
            sim.Rz(_qubit_index(circuit, qargs[0]), theta)
            continue

        if name == "rx":
            theta = _to_float(op.params[0])
            sim.Rx(_qubit_index(circuit, qargs[0]), theta)
            continue

        if name == "p":
            theta = _to_float(op.params[0])
            sim.P(_qubit_index(circuit, qargs[0]), theta)
            continue

        if name in {"u3", "u"}:
            theta = _to_float(op.params[0])
            phi = _to_float(op.params[1])
            lam = _to_float(op.params[2])
            # Qiskit uses U3/U(theta, phi, lambda), while ZXH::U3 stores
            # parameters as (theta, lambda, phi).
            sim.U3(_qubit_index(circuit, qargs[0]), theta, lam, phi)
            continue

        if name == "cp":
            theta = _to_float(op.params[0])
            sim.CP(_qubit_index(circuit, qargs[0]), _qubit_index(circuit, qargs[1]), theta)
            continue

        if name == "crz":
            theta = _to_float(op.params[0])
            sim.CRz(_qubit_index(circuit, qargs[0]), _qubit_index(circuit, qargs[1]), theta)
            continue

        raise NotImplementedError(f"Unsupported gate for ZXH native loading: {name}")


def bitrow_to_str(row) -> str:
    return "".join("1" if bit else "0" for bit in reversed(row))


def sample_counts(samples) -> Counter[str]:
    return Counter(bitrow_to_str(row) for row in samples)
