from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .canonical_ir import CANONICAL_QASM_GATES, canonicalize_circuit
from .common import (
    SWEEP_CANONICAL_ROOT,
    SWEEP_RAW_ROOT,
    WORKFLOW_OUTPUT_ROOT,
    experiment_case_circuit,
    repo_rel,
    write_csv,
    write_json,
    write_qasm3,
)

EXPECTED_REPRESENTATIVE_FAMILIES = {
    "bounded_support_min_rho_M_excluding_ghz": "bv",
    "transport_heavy_max_rho_X_excluding_ghz": "vqe_two_local",
    "lazy_expansion_min_rho_L_excluding_ghz": "qft",
    "adverse_full_support_max_rho_L_excluding_ghz": "qwalk",
}

@dataclass
class SweepRow:
    criterion: str
    family: str
    requested_n: int
    N: int | None
    circuit_source: str | None
    raw_qasm3_path: str | None
    canonical_qasm3_path: str | None
    canonical_gate_count: int | None
    canonical_gate_types: list[str]
    status: str
    note: str | None


def _load_representative_candidates(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _clean_qasm_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for stale in path.glob("*.qasm3"):
        stale.unlink()


def _validate_expected_representatives(candidates_obj: dict[str, Any]) -> dict[str, str]:
    observed = {str(row["criterion"]): str(row["family"]) for row in candidates_obj.get("rows", [])}

    missing = sorted(key for key in EXPECTED_REPRESENTATIVE_FAMILIES if key not in observed)
    if missing:
        raise RuntimeError(
            "Representative selection is incomplete; required criteria are missing: "
            + ", ".join(missing)
        )

    mismatched = [
        f"{criterion}: expected {expected}, got {observed[criterion]}"
        for criterion, expected in EXPECTED_REPRESENTATIVE_FAMILIES.items()
        if observed[criterion] != expected
    ]
    if mismatched:
        raise RuntimeError(
            "Representative selection drifted; refusing to generate hard-coded sweeps. "
            + " | ".join(mismatched)
        )

    family_values = [observed[criterion] for criterion in EXPECTED_REPRESENTATIVE_FAMILIES]
    if len(set(family_values)) != len(family_values):
        raise RuntimeError(
            "Representative selection is invalid because the four criteria are not mapped to four distinct families."
        )

    return dict(EXPECTED_REPRESENTATIVE_FAMILIES)


def _row_filename(family: str, requested_n: int) -> str:
    return f"{family}_n{requested_n}.qasm3"


def _generate_row(
    *,
    criterion: str,
    family: str,
    requested_n: int,
    opt_level: int,
    raw_root: Path,
    canonical_root: Path,
) -> SweepRow:
    filename = _row_filename(family, requested_n)
    raw_path = raw_root / filename
    canonical_path = canonical_root / filename

    try:
        circuit, source, note = experiment_case_circuit(
            family=family,
            requested_n=requested_n,
            opt_level=opt_level,
        )
        canonical = canonicalize_circuit(circuit)

        gate_types = sorted({inst.operation.name.lower() for inst in canonical.data})
        invalid = sorted(name for name in gate_types if name not in CANONICAL_QASM_GATES)
        if invalid:
            raise ValueError(f"Unexpected canonical gate types: {invalid}")

        write_qasm3(raw_path, circuit)
        write_qasm3(canonical_path, canonical)
        return SweepRow(
            criterion=criterion,
            family=family,
            requested_n=requested_n,
            N=circuit.num_qubits,
            circuit_source=source,
            raw_qasm3_path=repo_rel(raw_path),
            canonical_qasm3_path=repo_rel(canonical_path),
            canonical_gate_count=len(canonical.data),
            canonical_gate_types=gate_types,
            status="generated",
            note=note,
        )
    except Exception as exc:
        return SweepRow(
            criterion=criterion,
            family=family,
            requested_n=requested_n,
            N=None,
            circuit_source=None,
            raw_qasm3_path=repo_rel(raw_path) if raw_path.exists() else None,
            canonical_qasm3_path=repo_rel(canonical_path) if canonical_path.exists() else None,
            canonical_gate_count=None,
            canonical_gate_types=[],
            status="generation_failed",
            note=f"{type(exc).__name__}: {exc}",
        )


def _markdown_report(
    *,
    rows: list[SweepRow],
    validated_mapping: dict[str, str],
    n_min: int,
    n_max: int,
    raw_root: Path,
    canonical_root: Path,
) -> str:
    generated = sum(1 for row in rows if row.status == "generated")
    failed = len(rows) - generated
    lines = [
        "# Pass 5: Sweep Families",
        "",
        f"- range: `{n_min}..{n_max}`",
        f"- expected_representatives: `{validated_mapping}`",
        f"- generated_cases: `{generated}`",
        f"- failed_cases: `{failed}`",
        f"- raw_output_dir: `{repo_rel(raw_root)}`",
        f"- canonical_output_dir: `{repo_rel(canonical_root)}`",
        "",
        "| criterion | family | n | canonical_gate_count | status |",
        "| --- | --- | ---: | ---: | --- |",
    ]
    for row in rows:
        gate_count = "" if row.canonical_gate_count is None else str(row.canonical_gate_count)
        lines.append(
            f"| {row.criterion} | {row.family} | {row.requested_n} | {gate_count} | {row.status} |"
        )
    return "\n".join(lines) + "\n"


def run_sweep(
    *,
    representative_candidates_json_path: Path,
    output_dir: Path | None = None,
    raw_output_dir: Path | None = None,
    canonical_output_dir: Path | None = None,
    n_min: int = 20,
    n_max: int = 32,
    opt_level: int = 2,
) -> dict[str, Any]:
    candidates_path = representative_candidates_json_path.resolve()
    candidates_obj = _load_representative_candidates(candidates_path)
    validated_mapping = _validate_expected_representatives(candidates_obj)

    output_root = (WORKFLOW_OUTPUT_ROOT / "05_pass5_sweep") if output_dir is None else output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    raw_root = SWEEP_RAW_ROOT if raw_output_dir is None else raw_output_dir.resolve()
    canonical_root = SWEEP_CANONICAL_ROOT if canonical_output_dir is None else canonical_output_dir.resolve()
    _clean_qasm_dir(raw_root)
    _clean_qasm_dir(canonical_root)

    rows: list[SweepRow] = []
    for criterion, family in validated_mapping.items():
        for requested_n in range(n_min, n_max + 1):
            rows.append(
                _generate_row(
                    criterion=criterion,
                    family=family,
                    requested_n=requested_n,
                    opt_level=opt_level,
                    raw_root=raw_root,
                    canonical_root=canonical_root,
                )
            )

    json_path = output_root / "sweep.json"
    csv_path = output_root / "sweep.csv"
    md_path = output_root / "sweep.md"
    manifest_json_path = output_root / "sweep_manifest.json"
    manifest_csv_path = output_root / "sweep_manifest.csv"

    json_rows = [asdict(row) for row in rows]
    generated_rows = [row for row in rows if row.status == "generated"]
    manifest_rows = [asdict(row) for row in generated_rows]
    csv_rows = [
        {
            "criterion": row.criterion,
            "family": row.family,
            "requested_n": row.requested_n,
            "N": row.N,
            "circuit_source": row.circuit_source,
            "raw_qasm3_path": row.raw_qasm3_path,
            "canonical_qasm3_path": row.canonical_qasm3_path,
            "canonical_gate_count": row.canonical_gate_count,
            "canonical_gate_types": ";".join(row.canonical_gate_types),
            "status": row.status,
            "note": row.note,
        }
        for row in rows
    ]
    manifest_csv_rows = [
        {
            "criterion": row.criterion,
            "family": row.family,
            "requested_n": row.requested_n,
            "N": row.N,
            "circuit_source": row.circuit_source,
            "raw_qasm3_path": row.raw_qasm3_path,
            "canonical_qasm3_path": row.canonical_qasm3_path,
            "canonical_gate_count": row.canonical_gate_count,
            "canonical_gate_types": ";".join(row.canonical_gate_types),
            "status": row.status,
            "note": row.note,
        }
        for row in generated_rows
    ]

    write_json(
        json_path,
        {
            "params": {
                "representative_candidates_json_path": repo_rel(candidates_path),
                "n_min": n_min,
                "n_max": n_max,
                "opt_level": opt_level,
                "validated_mapping": validated_mapping,
                "raw_output_dir": repo_rel(raw_root),
                "canonical_output_dir": repo_rel(canonical_root),
            },
            "rows": json_rows,
        },
    )
    write_csv(
        csv_path,
        csv_rows,
        [
            "criterion",
            "family",
            "requested_n",
            "N",
            "circuit_source",
            "raw_qasm3_path",
            "canonical_qasm3_path",
            "canonical_gate_count",
            "canonical_gate_types",
            "status",
            "note",
        ],
    )
    md_path.write_text(
        _markdown_report(
            rows=rows,
            validated_mapping=validated_mapping,
            n_min=n_min,
            n_max=n_max,
            raw_root=raw_root,
            canonical_root=canonical_root,
        ),
        encoding="utf-8",
    )
    write_json(manifest_json_path, {"rows": manifest_rows})
    write_csv(
        manifest_csv_path,
        manifest_csv_rows,
        [
            "criterion",
            "family",
            "requested_n",
            "N",
            "circuit_source",
            "raw_qasm3_path",
            "canonical_qasm3_path",
            "canonical_gate_count",
            "canonical_gate_types",
            "status",
            "note",
        ],
    )

    return {
        "rows": json_rows,
        "validated_mapping": validated_mapping,
        "output_dir": repo_rel(output_root),
        "json_path": repo_rel(json_path),
        "csv_path": repo_rel(csv_path),
        "md_path": repo_rel(md_path),
        "raw_output_dir": repo_rel(raw_root),
        "canonical_output_dir": repo_rel(canonical_root),
        "sweep_manifest_json_path": repo_rel(manifest_json_path),
        "sweep_manifest_csv_path": repo_rel(manifest_csv_path),
    }
