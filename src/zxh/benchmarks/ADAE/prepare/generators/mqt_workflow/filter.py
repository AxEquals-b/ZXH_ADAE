from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .common import (
    WORKFLOW_OUTPUT_ROOT,
    estimate_qasm3_gate_count,
    load_qasm3_circuit,
    load_qasm3_program,
    qasm3_contains_branching,
    repo_rel,
    representative_circuit,
    validate_expected_adae_case_families,
    write_csv,
    write_json,
)


@dataclass
class FilterRow:
    family: str
    valid_sizes: list[int]
    representative_n: int | None
    N: int | None
    case_qasm3_path: str | None
    raw_instruction_count: int | None
    estimated_gate_count: int | None
    opaque_instruction_types: list[str]
    gate_budget: int | None
    gate_budget_passed: bool | None
    contains_branching: bool | None
    branching_types: list[str]
    depth: int | None
    depth_source: str | None
    status: str
    note: str | None


def _load_pass1(pass1_json_path: Path) -> dict[str, Any]:
    return json.loads(pass1_json_path.read_text(encoding="utf-8"))


def _raw_instruction_count(program: Any) -> int:
    return sum(
        1
        for stmt in program.statements
        if type(stmt).__name__
        not in {
            "Include",
            "QubitDeclaration",
            "ClassicalDeclaration",
            "IODeclaration",
            "ConstantDeclaration",
            "QuantumGateDefinition",
            "SubroutineDefinition",
            "ExternDeclaration",
            "CalibrationGrammarDeclaration",
            "Pragma",
        }
    )


def _build_note(parts: list[str]) -> str | None:
    filtered = [part for part in parts if part]
    if not filtered:
        return None
    return " ".join(filtered)


def _filter_family(
    *,
    row: dict[str, Any],
    opt_level: int,
    gate_count_budget: int | None,
    max_definition_depth: int,
) -> FilterRow:
    family = row["family"]
    valid_sizes = list(row.get("valid_sizes", []))
    representative_n = row["representative_n"]
    N = row.get("N")
    case_qasm3_path = row["case_qasm3_path"]

    if row["status"] != "case_generated":
        return FilterRow(
            family=family,
            valid_sizes=valid_sizes,
            representative_n=representative_n,
            N=N,
            case_qasm3_path=case_qasm3_path,
            raw_instruction_count=None,
            estimated_gate_count=None,
            opaque_instruction_types=[],
            gate_budget=gate_count_budget,
            gate_budget_passed=None,
            contains_branching=None,
            branching_types=[],
            depth=None,
            depth_source=None,
            status=row["status"],
            note=row.get("note"),
        )

    qasm_path = Path(case_qasm3_path)
    program = load_qasm3_program(qasm_path)
    raw_instruction_count = _raw_instruction_count(program)
    estimated_gate_count, opaque_instruction_types = estimate_qasm3_gate_count(
        program,
        max_definition_depth=max_definition_depth,
    )
    contains_branching, branching_types = qasm3_contains_branching(program)

    gate_budget_passed = None if gate_count_budget is None else estimated_gate_count <= gate_count_budget
    notes: list[str] = []
    if opaque_instruction_types:
        notes.append("Some instruction types were kept opaque during recursive counting.")

    depth = None
    depth_source = None
    status = "selected_for_structure_analysis"
    if gate_budget_passed is False:
        status = "filtered_by_gate_budget"
    elif contains_branching:
        status = "filtered_by_dynamic_control"
        notes.append("Contains data-dependent classical branching.")
    else:
        try:
            circuit = load_qasm3_circuit(qasm_path)
            depth = circuit.depth()
            depth_source = "qasm3_import"
        except Exception as exc:
            circuit, _, _ = representative_circuit(
                family=family,
                requested_n=representative_n,
                opt_level=opt_level,
            )
            depth = circuit.depth()
            depth_source = "reconstructed_circuit"
            notes.append(f"Depth import fallback: {type(exc).__name__}.")

    return FilterRow(
        family=family,
        valid_sizes=valid_sizes,
        representative_n=representative_n,
        N=N,
        case_qasm3_path=case_qasm3_path,
        raw_instruction_count=raw_instruction_count,
        estimated_gate_count=estimated_gate_count,
        opaque_instruction_types=opaque_instruction_types,
        gate_budget=gate_count_budget,
        gate_budget_passed=gate_budget_passed,
        contains_branching=contains_branching,
        branching_types=branching_types,
        depth=depth,
        depth_source=depth_source,
        status=status,
        note=_build_note(notes),
    )


def _markdown_report(
    *,
    rows: list[FilterRow],
    gate_count_budget: int | None,
    max_definition_depth: int,
) -> str:
    total = len(rows)
    selected = sum(1 for row in rows if row.status == "selected_for_structure_analysis")
    excluded = total - selected
    no_valid = sum(1 for row in rows if row.status == "no_valid_instance_in_range")
    gate_budget = sum(1 for row in rows if row.status == "filtered_by_gate_budget")
    dynamic = sum(1 for row in rows if row.status == "filtered_by_dynamic_control")
    opaque = sum(1 for row in rows if row.opaque_instruction_types)

    lines = [
        "# Pass 2: Filter",
        "",
        f"- gate_count_budget: `{gate_count_budget}`",
        f"- max_definition_depth: `{max_definition_depth}`",
        f"- total_families: `{total}`",
        f"- selected_for_structure_analysis: `{selected}`",
        f"- excluded_total: `{excluded}`",
        f"- excluded_by_qubit_count: `{no_valid}`",
        f"- excluded_by_gate_budget: `{gate_budget}`",
        f"- excluded_by_dynamic_control: `{dynamic}`",
        f"- cases_with_opaque_instruction_types: `{opaque}`",
        "",
        "| family | rep_n | N | depth | estimated_gate_count | status |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        rep_n = "" if row.representative_n is None else str(row.representative_n)
        N = "" if row.N is None else str(row.N)
        depth = "" if row.depth is None else str(row.depth)
        est = "" if row.estimated_gate_count is None else str(row.estimated_gate_count)
        lines.append(f"| {row.family} | {rep_n} | {N} | {depth} | {est} | {row.status} |")
    return "\n".join(lines) + "\n"


def run_filter(
    *,
    pass1_json_path: Path,
    output_dir: Path | None = None,
    gate_count_budget: int | None = 1_000_000,
    max_definition_depth: int = 32,
) -> dict[str, Any]:
    pass1_path = pass1_json_path.resolve()
    pass1_obj = _load_pass1(pass1_path)
    rows_in = list(pass1_obj["rows"])
    opt_level = int(pass1_obj["params"]["opt_level"])

    output_root = (WORKFLOW_OUTPUT_ROOT / "02_pass2_filter") if output_dir is None else output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    rows = [
        _filter_family(
            row=row,
            opt_level=opt_level,
            gate_count_budget=gate_count_budget,
            max_definition_depth=max_definition_depth,
        )
        for row in rows_in
    ]

    selected_rows = [row for row in rows if row.status == "selected_for_structure_analysis"]
    validated_family_ids = validate_expected_adae_case_families([row.family for row in selected_rows])
    selected_row_map = {row.family: row for row in selected_rows}
    selected_rows = [selected_row_map[family] for family in validated_family_ids]

    json_path = output_root / "filter.json"
    csv_path = output_root / "filter.csv"
    md_path = output_root / "filter.md"
    selected_json_path = output_root / "selected_manifest.json"
    selected_csv_path = output_root / "selected_manifest.csv"

    json_rows = [asdict(row) for row in rows]
    selected_json_rows = [asdict(row) for row in selected_rows]
    csv_rows = [
        {
            "family": row.family,
            "valid_sizes": ";".join(str(n) for n in row.valid_sizes),
            "representative_n": row.representative_n,
            "N": row.N,
            "case_qasm3_path": row.case_qasm3_path,
            "raw_instruction_count": row.raw_instruction_count,
            "estimated_gate_count": row.estimated_gate_count,
            "opaque_instruction_types": ";".join(row.opaque_instruction_types),
            "gate_budget": row.gate_budget,
            "gate_budget_passed": row.gate_budget_passed,
            "contains_branching": row.contains_branching,
            "branching_types": ";".join(row.branching_types),
            "depth": row.depth,
            "depth_source": row.depth_source,
            "status": row.status,
            "note": row.note,
        }
        for row in rows
    ]
    selected_csv_rows = [
        {
            "family": row.family,
            "valid_sizes": ";".join(str(n) for n in row.valid_sizes),
            "representative_n": row.representative_n,
            "N": row.N,
            "depth": row.depth,
            "depth_source": row.depth_source,
            "case_qasm3_path": row.case_qasm3_path,
            "raw_instruction_count": row.raw_instruction_count,
            "estimated_gate_count": row.estimated_gate_count,
            "status": row.status,
            "note": row.note,
        }
        for row in selected_rows
    ]

    write_json(
        json_path,
        {
            "params": {
                "pass1_json_path": repo_rel(pass1_path),
                "gate_count_budget": gate_count_budget,
                "max_definition_depth": max_definition_depth,
            },
            "rows": json_rows,
        },
    )
    write_csv(
        csv_path,
        csv_rows,
        [
            "family",
            "valid_sizes",
            "representative_n",
            "N",
            "case_qasm3_path",
            "raw_instruction_count",
            "estimated_gate_count",
            "opaque_instruction_types",
            "gate_budget",
            "gate_budget_passed",
            "contains_branching",
            "branching_types",
            "depth",
            "depth_source",
            "status",
            "note",
        ],
    )
    md_path.write_text(
        _markdown_report(
            rows=rows,
            gate_count_budget=gate_count_budget,
            max_definition_depth=max_definition_depth,
        ),
        encoding="utf-8",
    )
    write_json(
        selected_json_path,
        {
            "params": {
                "pass1_json_path": repo_rel(pass1_path),
                "opt_level": opt_level,
                "gate_count_budget": gate_count_budget,
                "max_definition_depth": max_definition_depth,
                "validated_family_ids": list(validated_family_ids),
            },
            "rows": selected_json_rows,
        },
    )
    write_csv(
        selected_csv_path,
        selected_csv_rows,
        [
            "family",
            "valid_sizes",
            "representative_n",
            "N",
            "depth",
            "depth_source",
            "case_qasm3_path",
            "raw_instruction_count",
            "estimated_gate_count",
            "status",
            "note",
        ],
    )

    return {
        "rows": json_rows,
        "output_dir": repo_rel(output_root),
        "json_path": repo_rel(json_path),
        "csv_path": repo_rel(csv_path),
        "md_path": repo_rel(md_path),
        "selected_json_path": repo_rel(selected_json_path),
        "selected_csv_path": repo_rel(selected_csv_path),
    }
