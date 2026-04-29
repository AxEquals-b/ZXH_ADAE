from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .canonical_ir import CANONICAL_QASM_GATES, canonicalize_circuit
from .common import (
    CANONICAL_CASES_ROOT,
    RAW_CASES_ROOT,
    WORKFLOW_OUTPUT_ROOT,
    WORKLOADS_OUTPUT_ROOT,
    experiment_case_circuit,
    repo_rel,
    select_size_at_or_below,
    validate_expected_adae_case_families,
    write_csv,
    write_json,
    write_qasm3,
)


@dataclass
class CanonicalizeRow:
    family: str
    representative_n: int | None
    N: int | None
    depth: int | None
    depth_source: str | None
    raw_qasm3_path: str | None
    canonical_qasm3_path: str | None
    canonical_gate_count: int | None
    canonical_gate_types: list[str]
    status: str
    note: str | None


def _load_selected_manifest(selected_manifest_json_path: Path) -> dict[str, Any]:
    return json.loads(selected_manifest_json_path.read_text(encoding="utf-8"))


def _clean_qasm_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for stale in path.glob("*.qasm3"):
        stale.unlink()


def _canonicalize_row(
    source_row: dict[str, Any],
    *,
    requested_n_cap: int,
    opt_level: int,
    raw_root: Path,
    canonical_root: Path,
) -> CanonicalizeRow:
    family = str(source_row["family"])
    valid_sizes = list(source_row.get("valid_sizes", []))
    selected_n = select_size_at_or_below(valid_sizes, requested_n_cap)
    filename = f"{family}_n{selected_n}.qasm3"
    raw_dst = raw_root / filename
    canonical_dst = canonical_root / filename

    try:
        circuit, _, source_note = experiment_case_circuit(
            family=family,
            requested_n=selected_n,
            opt_level=opt_level,
        )
        write_qasm3(raw_dst, circuit)
        canonical = canonicalize_circuit(circuit)
        write_qasm3(canonical_dst, canonical)

        gate_types = sorted({inst.operation.name.lower() for inst in canonical.data})
        invalid = sorted(name for name in gate_types if name not in CANONICAL_QASM_GATES)
        if invalid:
            raise ValueError(f"Unexpected canonical gate types: {invalid}")
        note_parts = [
            str(source_row.get("note", "")).strip(),
            str(source_note or "").strip(),
            f"size_cap={requested_n_cap} selected_n={selected_n}.",
        ]
        note = " ".join(part for part in note_parts if part)

        return CanonicalizeRow(
            family=family,
            representative_n=selected_n,
            N=canonical.num_qubits,
            depth=None,
            depth_source="regenerated_for_size_cap",
            raw_qasm3_path=repo_rel(raw_dst),
            canonical_qasm3_path=repo_rel(canonical_dst),
            canonical_gate_count=len(canonical.data),
            canonical_gate_types=gate_types,
            status="canonicalized",
            note=note,
        )
    except Exception as exc:
        note = source_row.get("note")
        failure = f"Canonicalization failed: {type(exc).__name__}: {exc}"
        note = failure if not note else f"{note} {failure}"
        return CanonicalizeRow(
            family=family,
            representative_n=None,
            N=None,
            depth=None,
            depth_source=None,
            raw_qasm3_path=repo_rel(raw_dst) if raw_dst.exists() else None,
            canonical_qasm3_path=repo_rel(canonical_dst) if canonical_dst.exists() else None,
            canonical_gate_count=None,
            canonical_gate_types=[],
            status="canonicalization_failed",
            note=note,
        )


def _markdown_report(rows: list[CanonicalizeRow], raw_root: Path, canonical_root: Path) -> str:
    done = sum(1 for row in rows if row.status == "canonicalized")
    failed = len(rows) - done

    lines = [
        "# Pass 3: Canonicalize",
        "",
        f"- selected_cases: `{len(rows)}`",
        f"- canonicalized_cases: `{done}`",
        f"- failed_cases: `{failed}`",
        f"- raw_output_dir: `{repo_rel(raw_root)}`",
        f"- canonical_output_dir: `{repo_rel(canonical_root)}`",
        "",
        "| family | N | canonical_gate_count | canonical_gate_types | status |",
        "| --- | ---: | ---: | --- | --- |",
    ]

    for row in rows:
        N = "" if row.N is None else str(row.N)
        gate_count = "" if row.canonical_gate_count is None else str(row.canonical_gate_count)
        gate_types = ",".join(row.canonical_gate_types)
        lines.append(f"| {row.family} | {N} | {gate_count} | {gate_types} | {row.status} |")

    return "\n".join(lines) + "\n"


def run_canonicalize(
    *,
    selected_manifest_json_path: Path,
    output_dir: Path | None = None,
    raw_output_dir: Path | None = None,
    canonical_output_dir: Path | None = None,
    representative_max_n: int = 30,
    dev_max_n: int = 24,
) -> dict[str, Any]:
    selected_manifest_path = selected_manifest_json_path.resolve()
    selected_manifest = _load_selected_manifest(selected_manifest_path)
    rows_in = list(selected_manifest["rows"])
    opt_level = int(selected_manifest.get("params", {}).get("opt_level", 2))
    validated_family_ids = validate_expected_adae_case_families([row["family"] for row in rows_in])
    row_map = {str(row["family"]): row for row in rows_in}

    output_root = (WORKFLOW_OUTPUT_ROOT / "03_pass3_canonicalize") if output_dir is None else output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    raw_root = RAW_CASES_ROOT if raw_output_dir is None else raw_output_dir.resolve()
    canonical_root = CANONICAL_CASES_ROOT if canonical_output_dir is None else canonical_output_dir.resolve()
    dev_raw_root = WORKLOADS_OUTPUT_ROOT / f"mqt_raw_dev_n{dev_max_n}"
    dev_canonical_root = WORKLOADS_OUTPUT_ROOT / f"mqt_canonical_dev_n{dev_max_n}"
    _clean_qasm_dir(raw_root)
    _clean_qasm_dir(canonical_root)
    _clean_qasm_dir(dev_raw_root)
    _clean_qasm_dir(dev_canonical_root)

    rows = [
        _canonicalize_row(
            row_map[family],
            requested_n_cap=representative_max_n,
            opt_level=opt_level,
            raw_root=raw_root,
            canonical_root=canonical_root,
        )
        for family in validated_family_ids
    ]
    dev_rows = [
        _canonicalize_row(
            row_map[family],
            requested_n_cap=dev_max_n,
            opt_level=opt_level,
            raw_root=dev_raw_root,
            canonical_root=dev_canonical_root,
        )
        for family in validated_family_ids
    ]

    canonicalized_rows = [row for row in rows if row.status == "canonicalized"]
    dev_canonicalized_rows = [row for row in dev_rows if row.status == "canonicalized"]

    json_path = output_root / "canonicalize.json"
    csv_path = output_root / "canonicalize.csv"
    md_path = output_root / "canonicalize.md"
    manifest_json_path = output_root / "canonical_manifest.json"
    manifest_csv_path = output_root / "canonical_manifest.csv"
    dev_manifest_json_path = output_root / "dev_canonical_manifest.json"
    dev_manifest_csv_path = output_root / "dev_canonical_manifest.csv"

    json_rows = [asdict(row) for row in rows]
    dev_json_rows = [asdict(row) for row in dev_rows]
    manifest_rows = [asdict(row) for row in canonicalized_rows]
    dev_manifest_rows = [asdict(row) for row in dev_canonicalized_rows]
    csv_rows = [
        {
            "family": row.family,
            "representative_n": row.representative_n,
            "N": row.N,
            "depth": row.depth,
            "depth_source": row.depth_source,
            "raw_qasm3_path": row.raw_qasm3_path,
            "canonical_qasm3_path": row.canonical_qasm3_path,
            "canonical_gate_count": row.canonical_gate_count,
            "canonical_gate_types": ";".join(row.canonical_gate_types),
            "status": row.status,
            "note": row.note,
        }
        for row in rows
    ]
    dev_csv_rows = [
        {
            "family": row.family,
            "representative_n": row.representative_n,
            "N": row.N,
            "depth": row.depth,
            "depth_source": row.depth_source,
            "raw_qasm3_path": row.raw_qasm3_path,
            "canonical_qasm3_path": row.canonical_qasm3_path,
            "canonical_gate_count": row.canonical_gate_count,
            "canonical_gate_types": ";".join(row.canonical_gate_types),
            "status": row.status,
            "note": row.note,
        }
        for row in dev_rows
    ]
    manifest_csv_rows = [
        {
            "family": row.family,
            "representative_n": row.representative_n,
            "N": row.N,
            "depth": row.depth,
            "depth_source": row.depth_source,
            "raw_qasm3_path": row.raw_qasm3_path,
            "canonical_qasm3_path": row.canonical_qasm3_path,
            "canonical_gate_count": row.canonical_gate_count,
            "canonical_gate_types": ";".join(row.canonical_gate_types),
            "status": row.status,
            "note": row.note,
        }
        for row in canonicalized_rows
    ]
    dev_manifest_csv_rows = [
        {
            "family": row.family,
            "representative_n": row.representative_n,
            "N": row.N,
            "depth": row.depth,
            "depth_source": row.depth_source,
            "raw_qasm3_path": row.raw_qasm3_path,
            "canonical_qasm3_path": row.canonical_qasm3_path,
            "canonical_gate_count": row.canonical_gate_count,
            "canonical_gate_types": ";".join(row.canonical_gate_types),
            "status": row.status,
            "note": row.note,
        }
        for row in dev_canonicalized_rows
    ]

    write_json(
        json_path,
        {
            "params": {
                "selected_manifest_json_path": repo_rel(selected_manifest_path),
                "opt_level": opt_level,
                "validated_family_ids": list(validated_family_ids),
                "representative_max_n": representative_max_n,
                "dev_max_n": dev_max_n,
                "raw_output_dir": repo_rel(raw_root),
                "canonical_output_dir": repo_rel(canonical_root),
                "dev_raw_output_dir": repo_rel(dev_raw_root),
                "dev_canonical_output_dir": repo_rel(dev_canonical_root),
            },
            "rows": json_rows,
            "dev_rows": dev_json_rows,
        },
    )
    write_csv(
        csv_path,
        csv_rows,
        [
            "family",
            "representative_n",
            "N",
            "depth",
            "depth_source",
            "raw_qasm3_path",
            "canonical_qasm3_path",
            "canonical_gate_count",
            "canonical_gate_types",
            "status",
            "note",
        ],
    )
    md_path.write_text(_markdown_report(rows, raw_root, canonical_root), encoding="utf-8")
    write_json(
        manifest_json_path,
        {
            "params": {
                "opt_level": opt_level,
                "validated_family_ids": list(validated_family_ids),
                "representative_max_n": representative_max_n,
            },
            "rows": manifest_rows,
        },
    )
    write_csv(
        manifest_csv_path,
        manifest_csv_rows,
        [
            "family",
            "representative_n",
            "N",
            "depth",
            "depth_source",
            "raw_qasm3_path",
            "canonical_qasm3_path",
            "canonical_gate_count",
            "canonical_gate_types",
            "status",
            "note",
        ],
    )
    write_json(
        dev_manifest_json_path,
        {
            "params": {
                "opt_level": opt_level,
                "validated_family_ids": list(validated_family_ids),
                "dev_max_n": dev_max_n,
            },
            "rows": dev_manifest_rows,
        },
    )
    write_csv(
        dev_manifest_csv_path,
        dev_manifest_csv_rows,
        [
            "family",
            "representative_n",
            "N",
            "depth",
            "depth_source",
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
        "output_dir": repo_rel(output_root),
        "json_path": repo_rel(json_path),
        "csv_path": repo_rel(csv_path),
        "md_path": repo_rel(md_path),
        "raw_output_dir": repo_rel(raw_root),
        "canonical_output_dir": repo_rel(canonical_root),
        "canonical_manifest_json_path": repo_rel(manifest_json_path),
        "canonical_manifest_csv_path": repo_rel(manifest_csv_path),
        "dev_raw_output_dir": repo_rel(dev_raw_root),
        "dev_canonical_output_dir": repo_rel(dev_canonical_root),
        "dev_canonical_manifest_json_path": repo_rel(dev_manifest_json_path),
        "dev_canonical_manifest_csv_path": repo_rel(dev_manifest_csv_path),
    }
