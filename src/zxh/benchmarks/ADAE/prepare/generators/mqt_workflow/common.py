from __future__ import annotations

import csv
import importlib
import inspect
import json
import math
import re
import sys
from functools import cache
from pathlib import Path
from typing import Any

import openqasm3
from qiskit import QuantumCircuit
from qiskit.qasm3 import dump as dump_qasm3


REPO_ROOT = Path(__file__).resolve().parents[5]
ADAE_ROOT = REPO_ROOT / "benchmarks" / "ADAE"
RESULTS_ROOT = ADAE_ROOT / "results"
PREPARE_RESULTS_ROOT = RESULTS_ROOT / "prepare"
RUN_RESULTS_ROOT = RESULTS_ROOT / "run"
AGGREGATE_RESULTS_ROOT = RESULTS_ROOT / "aggregate"
WORKFLOW_OUTPUT_ROOT = PREPARE_RESULTS_ROOT / "workflow"
WORKLOADS_OUTPUT_ROOT = PREPARE_RESULTS_ROOT / "workloads"
RAW_CASES_ROOT = WORKLOADS_OUTPUT_ROOT / "mqt_raw"
CANONICAL_CASES_ROOT = WORKLOADS_OUTPUT_ROOT / "mqt_canonical"
SWEEP_RAW_ROOT = WORKLOADS_OUTPUT_ROOT / "mqt_sweep_raw"
SWEEP_CANONICAL_ROOT = WORKLOADS_OUTPUT_ROOT / "mqt_sweep_canonical"
MQT_BENCH_SRC = REPO_ROOT / "workspace" / "external" / "mqt-bench" / "src"

EXPECTED_ADAE_CASE_FAMILIES: tuple[str, ...] = (
    "ae",
    "bmw_quark_cardinality",
    "bmw_quark_copula",
    "bv",
    "cdkm_ripple_carry_adder",
    "dj",
    "draper_qft_adder",
    "full_adder",
    "ghz",
    "graphstate",
    "half_adder",
    "hhl",
    "hrs_cumulative_multiplier",
    "modular_adder",
    "multiplier",
    "qaoa",
    "qft",
    "qftentangled",
    "qnn",
    "qpeexact",
    "qpeinexact",
    "qwalk",
    "randomcircuit",
    "rg_qft_multiplier",
    "vbe_ripple_carry_adder",
    "vqe_real_amp",
    "vqe_su2",
    "vqe_two_local",
    "wstate",
)

COUNT_IGNORED_OPS = {"barrier", "id"}
CONTROL_FLOW_OPS = {"if_else", "if_test", "for_loop", "while_loop", "switch_case"}
PRIMITIVE_GATE_OPS = {
    "measure",
    "reset",
    "delay",
    "x",
    "y",
    "z",
    "h",
    "s",
    "sdg",
    "t",
    "tdg",
    "sx",
    "sxdg",
    "p",
    "rx",
    "ry",
    "rz",
    "r",
    "u",
    "u1",
    "u2",
    "u3",
    "swap",
    "iswap",
    "cx",
    "cy",
    "cz",
    "ch",
    "cp",
    "cs",
    "csdg",
    "csx",
    "cswap",
    "crx",
    "cry",
    "crz",
    "cu",
    "cu1",
    "cu3",
    "dcx",
    "ecr",
    "rxx",
    "ryy",
    "rzx",
    "rzz",
    "xx_plus_yy",
    "xx_minus_yy",
    "ccx",
    "ccz",
    "rccx",
    "rcccx",
    "c3sx",
    "mcphase",
}


def ensure_import_paths() -> None:
    for path in (MQT_BENCH_SRC, REPO_ROOT):
        path_str = str(path.resolve())
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def import_mqt_bench():
    ensure_import_paths()
    from mqt.bench import BenchmarkLevel, get_benchmark
    from mqt.bench.benchmarks import get_available_benchmark_names

    return BenchmarkLevel, get_benchmark, get_available_benchmark_names


def load_known_valid_sizes_20_32() -> dict[str, list[int]] | None:
    ensure_import_paths()
    try:
        from workspace.bench_analysis.analyze_mqt_families import KNOWN_VALID_SIZES_20_32
    except Exception:
        return None
    return KNOWN_VALID_SIZES_20_32


def repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path.resolve())


def validate_expected_adae_case_families(observed_families: list[str]) -> tuple[str, ...]:
    expected = tuple(EXPECTED_ADAE_CASE_FAMILIES)
    observed = tuple(str(family) for family in observed_families)

    duplicates: list[str] = []
    seen: set[str] = set()
    for family in observed:
        if family in seen and family not in duplicates:
            duplicates.append(family)
        seen.add(family)

    missing = sorted(set(expected) - set(observed))
    unexpected = sorted(set(observed) - set(expected))
    if duplicates or missing or unexpected or len(observed) != len(expected):
        parts: list[str] = []
        if duplicates:
            parts.append(f"duplicates={duplicates}")
        if missing:
            parts.append(f"missing={missing}")
        if unexpected:
            parts.append(f"unexpected={unexpected}")
        if len(observed) != len(expected):
            parts.append(f"count={len(observed)} expected={len(expected)}")
        raise RuntimeError(
            "ADAE family selection drifted; refusing to continue. " + " | ".join(parts)
        )

    return expected


def select_size_at_or_below(valid_sizes: list[int], max_n: int) -> int:
    candidates = sorted({int(n) for n in valid_sizes if int(n) <= max_n})
    if not candidates:
        raise ValueError(f"No valid circuit size is available at or below max_n={max_n}.")
    return candidates[-1]


def normalize_raw_gate_name(name: str) -> str:
    lowered = name.lower()
    if re.fullmatch(r"circuit-\d+(_dg)?", lowered):
        return re.sub(r"\d+", "*", lowered)
    if re.fullmatch(r"ccircuit-\d+\*\*\d+", lowered):
        return "ccircuit-*"
    return lowered


def build_ae_lowered(num_qubits: int, probability: float = 0.2) -> QuantumCircuit:
    if num_qubits < 2:
        raise ValueError("AE benchmark requires at least 2 qubits.")

    theta_p = 2.0 * math.asin(math.sqrt(probability))
    num_eval_qubits = num_qubits - 1
    target = num_eval_qubits
    qc = QuantumCircuit(num_qubits, num_qubits, name="ae")

    qc.ry(theta_p, target)
    for q in range(num_eval_qubits):
        qc.h(q)

    for q in range(num_eval_qubits):
        theta = (2**q) * (2.0 * theta_p)
        qc.ry(theta / 2.0, target)
        qc.cx(q, target)
        qc.ry(-theta / 2.0, target)
        qc.cx(q, target)

    for hi in reversed(range(num_eval_qubits)):
        for lo in reversed(range(hi)):
            qc.cp(-math.pi / (2 ** (hi - lo)), lo, hi)
        qc.h(hi)

    qc.measure(range(num_qubits), range(num_qubits))
    return qc


@cache
def benchmark_default_kwargs(family: str) -> dict[str, Any]:
    ensure_import_paths()
    module = importlib.import_module(f"mqt.bench.benchmarks.{family}")
    create_circuit = getattr(module, "create_circuit")
    signature = inspect.signature(create_circuit)
    if "seed" in signature.parameters:
        return {"seed": 10}
    return {}


def is_environment_error(exc: BaseException) -> bool:
    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if isinstance(current, (ImportError, ModuleNotFoundError)):
            return True
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return False


def load_raw_circuit(*, family: str, requested_n: int, opt_level: int):
    BenchmarkLevel, get_benchmark, _ = import_mqt_bench()
    kwargs = benchmark_default_kwargs(family)

    if family == "ae":
        return None, "ae_manual_fallback", "使用手工 AE fallback 生成 representative case。"

    try:
        circuit = get_benchmark(family, BenchmarkLevel.INDEP, requested_n, opt_level=opt_level, **kwargs)
    except Exception as exc:
        if is_environment_error(exc):
            raise RuntimeError(
                f"Failed to generate benchmark family {family!r} due to missing or broken environment dependency."
            ) from exc
        raise
    return circuit, "mqt_bench", None


def representative_circuit(*, family: str, requested_n: int, opt_level: int):
    circuit, source, note = load_raw_circuit(
        family=family,
        requested_n=requested_n,
        opt_level=opt_level,
    )
    if family == "ae":
        circuit = build_ae_lowered(requested_n)
        return circuit, "ae_manual_fallback", note
    return circuit, source, note


def experiment_case_circuit(*, family: str, requested_n: int, opt_level: int):
    return representative_circuit(
        family=family,
        requested_n=requested_n,
        opt_level=opt_level,
    )


def write_qasm3(path: Path, circuit: QuantumCircuit) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        dump_qasm3(circuit, f)


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def load_qasm3_program(path: Path) -> openqasm3.ast.Program:
    return openqasm3.parse(path.read_text(encoding="utf-8"))


def qasm3_contains_branching(program: openqasm3.ast.Program) -> tuple[bool, list[str]]:
    found: set[str] = set()

    def visit_statements(statements: list[Any]) -> None:
        for stmt in statements:
            stmt_type = type(stmt).__name__
            if stmt_type == "BranchingStatement":
                found.add("if_else")
                visit_statements(list(getattr(stmt, "if_block", []) or []))
                visit_statements(list(getattr(stmt, "else_block", []) or []))
                continue

            body = getattr(stmt, "body", None)
            if isinstance(body, list):
                visit_statements(body)
                continue

            block = getattr(stmt, "block", None)
            if isinstance(block, list):
                visit_statements(block)

    visit_statements(list(program.statements))
    return bool(found), sorted(found)


def load_qasm3_circuit(path: Path) -> QuantumCircuit:
    from qiskit.qasm3 import loads as load_qasm3

    return load_qasm3(path.read_text(encoding="utf-8"))


def _qasm3_gate_name(node: Any) -> str:
    name = getattr(node, "name", None)
    if hasattr(name, "name"):
        return normalize_raw_gate_name(name.name)
    return normalize_raw_gate_name(str(name))


def _qasm3_loop_multiplier(node: Any) -> int | None:
    set_declaration = getattr(node, "set_declaration", None)
    if set_declaration is None:
        return None
    values = getattr(set_declaration, "values", None)
    if values is not None:
        return len(values)
    start = getattr(set_declaration, "start", None)
    end = getattr(set_declaration, "end", None)
    step = getattr(set_declaration, "step", None)
    if start is None or end is None:
        return None
    try:
        start_value = start.value
        end_value = end.value
        step_value = 1 if step is None else step.value
        if step_value == 0:
            return None
        if step_value > 0:
            return max(0, ((end_value - start_value) // step_value) + 1)
        return max(0, ((start_value - end_value) // (-step_value)) + 1)
    except Exception:
        return None


def estimate_qasm3_gate_count(program: openqasm3.ast.Program, *, max_definition_depth: int = 32) -> tuple[int, list[str]]:
    gate_definitions: dict[str, list[Any]] = {}
    for stmt in program.statements:
        if type(stmt).__name__ == "QuantumGateDefinition":
            gate_definitions[normalize_raw_gate_name(stmt.name.name)] = list(stmt.body)

    memo: dict[str, tuple[int, tuple[str, ...]]] = {}

    def count_block(
        statements: list[Any],
        *,
        depth_left: int,
        active_defs: set[str],
    ) -> tuple[int, set[str]]:
        total = 0
        opaque: set[str] = set()
        for stmt in statements:
            count, names = count_statement(
                stmt,
                depth_left=depth_left,
                active_defs=active_defs,
            )
            total += count
            opaque.update(names)
        return total, opaque

    def count_statement(
        stmt: Any,
        *,
        depth_left: int,
        active_defs: set[str],
    ) -> tuple[int, set[str]]:
        stmt_type = type(stmt).__name__

        if stmt_type in {
            "Include",
            "QubitDeclaration",
            "ClassicalDeclaration",
            "IODeclaration",
            "ConstantDeclaration",
            "ExternDeclaration",
            "CalibrationGrammarDeclaration",
            "AliasStatement",
            "QuantumGateDefinition",
            "SubroutineDefinition",
            "Pragma",
        }:
            return 0, set()

        if stmt_type == "QuantumBarrier":
            return 0, set()

        if stmt_type in {"QuantumMeasurementStatement", "QuantumReset", "DelayInstruction", "QuantumPhase"}:
            return 1, set()

        if stmt_type == "QuantumGate":
            gate_name = _qasm3_gate_name(stmt)
            if gate_name in PRIMITIVE_GATE_OPS:
                return 1, set()
            if gate_name not in gate_definitions:
                return 1, {gate_name}
            if depth_left <= 0 or gate_name in active_defs:
                return 1, {gate_name}
            if gate_name in memo:
                cached_count, cached_names = memo[gate_name]
                return cached_count, set(cached_names)

            nested_active = set(active_defs)
            nested_active.add(gate_name)
            count, opaque = count_block(
                gate_definitions[gate_name],
                depth_left=depth_left - 1,
                active_defs=nested_active,
            )
            memo[gate_name] = (count, tuple(sorted(opaque)))
            return count, opaque

        if stmt_type == "BranchingStatement":
            if_count, if_opaque = count_block(
                list(getattr(stmt, "if_block", [])),
                depth_left=depth_left,
                active_defs=active_defs,
            )
            else_count, else_opaque = count_block(
                list(getattr(stmt, "else_block", [])),
                depth_left=depth_left,
                active_defs=active_defs,
            )
            return max(if_count, else_count), (if_opaque | else_opaque)

        if stmt_type == "ForInLoop":
            body = list(getattr(stmt, "block", None) or getattr(stmt, "body", []) or [])
            body_count, opaque = count_block(
                body,
                depth_left=depth_left,
                active_defs=active_defs,
            )
            multiplier = _qasm3_loop_multiplier(stmt)
            if multiplier is None:
                return body_count, opaque | {"for_loop"}
            return multiplier * body_count, opaque

        if stmt_type == "WhileLoop":
            body = list(getattr(stmt, "block", None) or getattr(stmt, "body", []) or [])
            body_count, opaque = count_block(
                body,
                depth_left=depth_left,
                active_defs=active_defs,
            )
            return body_count, opaque | {"while_loop"}

        return 1, {normalize_raw_gate_name(stmt_type)}

    total, opaque = count_block(
        list(program.statements),
        depth_left=max_definition_depth,
        active_defs=set(),
    )
    return total, sorted(opaque)
