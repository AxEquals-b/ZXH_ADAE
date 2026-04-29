#!/usr/bin/env python3
from __future__ import annotations

import importlib
import inspect
import sys
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from qiskit import QuantumCircuit, qasm3, transpile
from qiskit.circuit import Barrier, Measure


warnings.filterwarnings(
    "ignore",
    message=r".*(MCXRecursive|MCXVChain|MCXGate\.get_num_ancilla_qubits).*",
    category=PendingDeprecationWarning,
)


SRC_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = SRC_ROOT.parent
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "output" / "circuits"
DEFAULT_SEED_TRANSPILER = 10
DEFAULT_MQT_SEED = 10
LOCAL_PYDEPS_ROOT = SRC_ROOT / "pydeps"

BASE_MANIFEST_FIELDS = [
    "suite",
    "circuit",
    "family",
    "N",
    "num_qubits",
    "depth",
    "gate_count",
    "gate_types",
    "qasm_path",
    "qasm_status",
    "qasm_error",
    "status",
    "error",
]

ZXH_MANIFEST_FIELDS = [
    "x_count",
    "z_count",
    "h_count",
    "M",
    "rho_X",
    "rho_M",
    "rho_L",
]

_ZXH_ANALYZE_CIRCUIT = None


if LOCAL_PYDEPS_ROOT.is_dir():
    local_pydeps = str(LOCAL_PYDEPS_ROOT)
    if local_pydeps not in sys.path:
        sys.path.insert(0, local_pydeps)


@dataclass
class GeneratedCircuit:
    circuit: QuantumCircuit
    analysis_circuit: QuantumCircuit
    qasm_path: Path
    manifest_row: dict[str, Any]
    timings: dict[str, float]


def circuit_stem(family: str, num_qubits: int) -> str:
    return f"{family}_n{num_qubits}"


def qasm_path_for_case(
    *,
    output_root: Path,
    suite_name: str,
    backend_name: str,
    family: str,
    num_qubits: int,
) -> Path:
    return output_root / suite_name / backend_name / f"{circuit_stem(family, num_qubits)}.qasm3"


def benchmark_default_kwargs(family: str) -> dict[str, Any]:
    module = importlib.import_module(f"mqt.bench.benchmarks.{family}")
    create_circuit = getattr(module, "create_circuit", None)
    if create_circuit is None:
        return {}
    try:
        signature = inspect.signature(create_circuit)
    except (TypeError, ValueError):
        return {}
    if "seed" in signature.parameters:
        return {"seed": DEFAULT_MQT_SEED}
    return {}


def normalize_circuit(circuit: QuantumCircuit) -> QuantumCircuit:
    if circuit.qregs and (circuit.num_clbits == 0 or circuit.cregs):
        return circuit

    normalized = QuantumCircuit(circuit.num_qubits, circuit.num_clbits, name=circuit.name)
    normalized.global_phase = circuit.global_phase
    normalized.metadata = dict(circuit.metadata or {})

    qubit_index = {bit: i for i, bit in enumerate(circuit.qubits)}
    clbit_index = {bit: i for i, bit in enumerate(circuit.clbits)}

    for instruction in circuit.data:
        normalized.append(
            instruction.operation,
            [normalized.qubits[qubit_index[bit]] for bit in instruction.qubits],
            [normalized.clbits[clbit_index[bit]] for bit in instruction.clbits],
        )
    return normalized


def strip_analysis_only_ops(circuit: QuantumCircuit) -> QuantumCircuit:
    stripped = QuantumCircuit(circuit.num_qubits, circuit.num_clbits, name=circuit.name)
    stripped.global_phase = circuit.global_phase
    stripped.metadata = dict(circuit.metadata or {})

    qubit_index = {bit: i for i, bit in enumerate(circuit.qubits)}
    clbit_index = {bit: i for i, bit in enumerate(circuit.clbits)}

    for instruction in circuit.data:
        operation = instruction.operation
        if isinstance(operation, (Barrier, Measure)):
            continue
        stripped.append(
            operation,
            [stripped.qubits[qubit_index[bit]] for bit in instruction.qubits],
            [stripped.clbits[clbit_index[bit]] for bit in instruction.clbits],
        )

    return normalize_circuit(stripped)


def load_zxh_tools():
    global _ZXH_ANALYZE_CIRCUIT
    if _ZXH_ANALYZE_CIRCUIT is not None:
        return _ZXH_ANALYZE_CIRCUIT

    analyzer_module = importlib.import_module("zxhsim.analyzer")
    _ZXH_ANALYZE_CIRCUIT = analyzer_module.analyze_circuit
    return _ZXH_ANALYZE_CIRCUIT


def analyze_zxh_metadata(circuit: QuantumCircuit) -> dict[str, Any]:
    analyze_circuit = load_zxh_tools()
    stats = analyze_circuit(circuit)
    return {
        "x_count": stats.compiled_x_type_count,
        "z_count": stats.compiled_z_type_count,
        "h_count": stats.compiled_h_type_count,
        "M": stats.M,
        "rho_X": stats.rho_X,
        "rho_M": stats.rho_M,
        "rho_L": stats.rho_L,
    }


def base_manifest_row(
    *,
    suite_name: str,
    family: str,
    num_qubits: int,
    qasm_path: Path,
) -> dict[str, Any]:
    return {
        "suite": suite_name,
        "circuit": circuit_stem(family, num_qubits),
        "family": family,
        "N": num_qubits,
        "num_qubits": 0,
        "depth": 0,
        "gate_count": 0,
        "gate_types": "",
        "qasm_path": str(qasm_path),
        "qasm_status": "",
        "qasm_error": "",
        "status": "error",
        "error": "",
    }


def serialize_qasm(circuit: QuantumCircuit, qasm_path: Path) -> tuple[str, str]:
    qasm_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with qasm_path.open("w", encoding="utf-8") as f:
            qasm3.dump(circuit, f)
        return "pass", ""
    except Exception as exc:
        try:
            qasm_path.unlink(missing_ok=True)
        except OSError:
            pass
        return "error", f"{type(exc).__name__}: {exc}"


def generate_case(
    *,
    suite_name: str,
    family: str,
    num_qubits: int,
    backend_name: str,
    backend: Any,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    seed_transpiler: int = DEFAULT_SEED_TRANSPILER,
    emit_qasm: bool = True,
) -> GeneratedCircuit:
    from mqt.bench import BenchmarkLevel, get_benchmark

    qasm_path = qasm_path_for_case(
        output_root=output_root,
        suite_name=suite_name,
        backend_name=backend_name,
        family=family,
        num_qubits=num_qubits,
    )

    timings: dict[str, float] = {}

    t0 = time.perf_counter()
    raw = get_benchmark(
        family,
        BenchmarkLevel.ALG,
        num_qubits,
        **benchmark_default_kwargs(family),
    )
    timings["raw_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    lowered = transpile(
        raw,
        backend=backend,
        seed_transpiler=seed_transpiler,
    )
    timings["transpile_s"] = time.perf_counter() - t0

    t0 = time.perf_counter()
    analysis_circuit = strip_analysis_only_ops(lowered)
    timings["analysis_copy_s"] = time.perf_counter() - t0

    qasm_status = "skipped"
    qasm_error = ""
    if emit_qasm:
        t0 = time.perf_counter()
        qasm_status, qasm_error = serialize_qasm(lowered, qasm_path)
        timings["qasm_dump_s"] = time.perf_counter() - t0
    else:
        timings["qasm_dump_s"] = 0.0

    gate_types = sorted({inst.operation.name.lower() for inst in analysis_circuit.data})
    manifest_row = base_manifest_row(
        suite_name=suite_name,
        family=family,
        num_qubits=num_qubits,
        qasm_path=qasm_path,
    )
    manifest_row.update(
        {
            "num_qubits": analysis_circuit.num_qubits,
            "depth": analysis_circuit.depth(),
            "gate_count": len(analysis_circuit.data),
            "gate_types": ";".join(gate_types),
            "qasm_status": qasm_status,
            "qasm_error": qasm_error,
            "status": "pass",
            "error": "",
        }
    )
    if backend_name == "zxh":
        manifest_row.update(analyze_zxh_metadata(analysis_circuit))

    return GeneratedCircuit(
        circuit=lowered,
        analysis_circuit=analysis_circuit,
        qasm_path=qasm_path,
        manifest_row=manifest_row,
        timings=timings,
    )
