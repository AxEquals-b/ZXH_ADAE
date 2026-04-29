from __future__ import annotations

import importlib
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from benchmarks.stage import activate_python_stage

from .common import REPO_ROOT, WORKFLOW_OUTPUT_ROOT, load_qasm3_circuit, repo_rel, write_csv, write_json


@dataclass
class AnalysisRow:
    family: str
    representative_n: int | None
    N: int | None
    depth: int | None
    depth_source: str | None
    raw_qasm3_path: str | None
    canonical_qasm3_path: str | None
    status: str
    note: str | None
    compiled_gate_count: int | None
    compiled_x_type_count: int | None
    compiled_z_type_count: int | None
    compiled_h_type_count: int | None
    compiled_gate_type_counts: dict[str, int] | None
    M: int | None
    rho_X: float | None
    rho_M: float | None
    rho_L: float | None
    zh_gate_count: int | None
    zh_traversal_volume: int | None
    zh_full_width_volume: int | None
    clear_gates_calls: int | None
    expansion_event_count: int | None
    expansion_events: list[dict[str, Any]]
    final_affine_rows: list[str]
    final_affine_offset: str | None


def _load_canonical_manifest(canonical_manifest_json_path: Path) -> dict[str, Any]:
    return json.loads(canonical_manifest_json_path.read_text(encoding="utf-8"))


def _resolve_repo_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return (REPO_ROOT / path).resolve()


def _load_staged_analyzer(backend: str) -> tuple[str, Any]:
    try:
        stage_dir = activate_python_stage(REPO_ROOT, backend)
    except FileNotFoundError as exc:
        raise FileNotFoundError(
            "Staged ZXH package not found for ADAE prepare analyze. "
            "Run `python benchmarks/ADAE/prepare/scripts/build_zxh_stages.py --backend cuda` first."
        ) from exc
    doomed = [name for name in sys.modules if name == "zxhsim" or name.startswith("zxhsim.")]
    for name in doomed:
        del sys.modules[name]
    analyzer_mod = importlib.import_module("zxhsim.analyzer")
    return repo_rel(stage_dir), analyzer_mod.analyze_circuit


def _analyze_row(row: dict[str, Any], *, analyze_circuit_fn) -> AnalysisRow:
    canonical_qasm3_path = row["canonical_qasm3_path"]
    qasm_path = _resolve_repo_path(canonical_qasm3_path)

    try:
        circuit = load_qasm3_circuit(qasm_path)
        stats = analyze_circuit_fn(circuit)
        return AnalysisRow(
            family=row["family"],
            representative_n=row.get("representative_n"),
            N=row.get("N", circuit.num_qubits),
            depth=row.get("depth"),
            depth_source=row.get("depth_source"),
            raw_qasm3_path=row.get("raw_qasm3_path"),
            canonical_qasm3_path=canonical_qasm3_path,
            status="analyzed",
            note=row.get("note"),
            compiled_gate_count=stats.compiled_gate_count,
            compiled_x_type_count=stats.compiled_x_type_count,
            compiled_z_type_count=stats.compiled_z_type_count,
            compiled_h_type_count=stats.compiled_h_type_count,
            compiled_gate_type_counts=stats.compiled_gate_type_counts,
            M=stats.M,
            rho_X=stats.rho_X,
            rho_M=stats.rho_M,
            rho_L=stats.rho_L,
            zh_gate_count=stats.zh_gate_count,
            zh_traversal_volume=stats.zh_traversal_volume,
            zh_full_width_volume=stats.zh_full_width_volume,
            clear_gates_calls=stats.clear_gates_calls,
            expansion_event_count=stats.expansion_event_count,
            expansion_events=stats.expansion_events,
            final_affine_rows=stats.final_affine_rows,
            final_affine_offset=stats.final_affine_offset,
        )
    except Exception as exc:
        note = row.get("note")
        failure = f"Analysis failed: {type(exc).__name__}: {exc}"
        note = failure if not note else f"{note} {failure}"
        return AnalysisRow(
            family=row["family"],
            representative_n=row.get("representative_n"),
            N=row.get("N"),
            depth=row.get("depth"),
            depth_source=row.get("depth_source"),
            raw_qasm3_path=row.get("raw_qasm3_path"),
            canonical_qasm3_path=canonical_qasm3_path,
            status="analysis_failed",
            note=note,
            compiled_gate_count=None,
            compiled_x_type_count=None,
            compiled_z_type_count=None,
            compiled_h_type_count=None,
            compiled_gate_type_counts=None,
            M=None,
            rho_X=None,
            rho_M=None,
            rho_L=None,
            zh_gate_count=None,
            zh_traversal_volume=None,
            zh_full_width_volume=None,
            clear_gates_calls=None,
            expansion_event_count=None,
            expansion_events=[],
            final_affine_rows=[],
            final_affine_offset=None,
        )


def _stable_min(rows: list[AnalysisRow], key_name: str) -> AnalysisRow | None:
    valid = [row for row in rows if getattr(row, key_name) is not None]
    if not valid:
        return None
    return min(valid, key=lambda row: (getattr(row, key_name), row.family))


def _stable_max(rows: list[AnalysisRow], key_name: str) -> AnalysisRow | None:
    valid = [row for row in rows if getattr(row, key_name) is not None]
    if not valid:
        return None
    return max(valid, key=lambda row: (getattr(row, key_name), row.family))


def _pack_row(row: AnalysisRow | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "family": row.family,
        "representative_n": row.representative_n,
        "N": row.N,
        "M": row.M,
        "rho_M": row.rho_M,
        "rho_X": row.rho_X,
        "rho_L": row.rho_L,
        "canonical_qasm3_path": row.canonical_qasm3_path,
        "raw_qasm3_path": row.raw_qasm3_path,
    }


def _pick_distinct(
    rows: list[AnalysisRow],
    *,
    key_name: str,
    reverse: bool,
    used_families: set[str],
    extra_filter=None,
) -> AnalysisRow | None:
    candidates = [row for row in rows if row.status == "analyzed" and row.family not in used_families]
    if extra_filter is not None:
        candidates = [row for row in candidates if extra_filter(row)]
    candidates = [row for row in candidates if getattr(row, key_name) is not None]
    if not candidates:
        return None
    ordered = sorted(
        candidates,
        key=lambda row: (getattr(row, key_name), row.family),
        reverse=reverse,
    )
    return ordered[0]


def _selection_summary(rows: list[AnalysisRow]) -> dict[str, Any]:
    analyzed = [row for row in rows if row.status == "analyzed"]
    analyzed_nontrivial = [row for row in analyzed if row.family != "ghz"]

    extrema = {
        "min_rho_M_including_ghz": _pack_row(_stable_min(analyzed, "rho_M")),
        "max_rho_X_including_ghz": _pack_row(_stable_max(analyzed, "rho_X")),
        "min_rho_L_including_ghz": _pack_row(_stable_min(analyzed, "rho_L")),
        "max_rho_L_full_support_including_ghz": _pack_row(
            _stable_max(
                [
                    row
                    for row in analyzed
                    if row.rho_M is not None and math.isclose(row.rho_M, 1.0, rel_tol=0.0, abs_tol=1e-12)
                ],
                "rho_L",
            )
        ),
    }

    used_families: set[str] = set()
    bounded = _pick_distinct(analyzed_nontrivial, key_name="rho_M", reverse=False, used_families=used_families)
    if bounded is not None:
        used_families.add(bounded.family)

    transport = _pick_distinct(analyzed_nontrivial, key_name="rho_X", reverse=True, used_families=used_families)
    if transport is not None:
        used_families.add(transport.family)

    lazy = _pick_distinct(analyzed_nontrivial, key_name="rho_L", reverse=False, used_families=used_families)
    if lazy is not None:
        used_families.add(lazy.family)

    adverse = _pick_distinct(
        analyzed_nontrivial,
        key_name="rho_L",
        reverse=True,
        used_families=used_families,
        extra_filter=lambda row: row.rho_M is not None and math.isclose(row.rho_M, 1.0, rel_tol=0.0, abs_tol=1e-12),
    )

    return {
        "extrema": extrema,
        "representative_candidates": {
            "bounded_support_min_rho_M_excluding_ghz": _pack_row(bounded),
            "transport_heavy_max_rho_X_excluding_ghz": _pack_row(transport),
            "lazy_expansion_min_rho_L_excluding_ghz": _pack_row(lazy),
            "adverse_full_support_max_rho_L_excluding_ghz": _pack_row(adverse),
        },
    }


def _markdown_report(rows: list[AnalysisRow], summary: dict[str, Any], *, zxh_backend: str, zxh_stage_dir: str) -> str:
    analyzed = [row for row in rows if row.status == "analyzed"]
    failed = [row for row in rows if row.status != "analyzed"]

    lines = [
        "# Pass 4: Analyze",
        "",
        f"- analyzed_cases: `{len(analyzed)}`",
        f"- failed_cases: `{len(failed)}`",
        f"- zxh_backend: `{zxh_backend}`",
        f"- zxh_stage_dir: `{zxh_stage_dir}`",
        "",
        "Representative-case candidates:",
    ]

    for key, row in summary["representative_candidates"].items():
        if row is None:
            lines.append(f"- {key}: `None`")
            continue
        lines.append(
            f"- {key}: `{row['family']}` "
            f"(rho_M={row['rho_M']:.6f}, rho_X={row['rho_X']:.6f}, rho_L={row['rho_L']:.6f})"
        )

    lines.extend(
        [
            "",
            "| family | N | M | compiled | rho_M | rho_X | rho_L | status |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )

    for row in rows:
        N = "" if row.N is None else str(row.N)
        M = "" if row.M is None else str(row.M)
        compiled = "" if row.compiled_gate_count is None else str(row.compiled_gate_count)
        rho_M = "" if row.rho_M is None else f"{row.rho_M:.6f}"
        rho_X = "" if row.rho_X is None else f"{row.rho_X:.6f}"
        rho_L = "" if row.rho_L is None else f"{row.rho_L:.6f}"
        lines.append(f"| {row.family} | {N} | {M} | {compiled} | {rho_M} | {rho_X} | {rho_L} | {row.status} |")

    return "\n".join(lines) + "\n"


def run_analyze(
    *,
    canonical_manifest_json_path: Path,
    output_dir: Path | None = None,
    zxh_backend: str = "cuda",
) -> dict[str, Any]:
    canonical_manifest_path = canonical_manifest_json_path.resolve()
    manifest_obj = _load_canonical_manifest(canonical_manifest_path)
    rows_in = list(manifest_obj["rows"])

    output_root = (WORKFLOW_OUTPUT_ROOT / "04_pass4_analyze") if output_dir is None else output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    zxh_stage_dir, analyze_circuit_fn = _load_staged_analyzer(zxh_backend)
    rows = [_analyze_row(row, analyze_circuit_fn=analyze_circuit_fn) for row in rows_in]
    summary = _selection_summary(rows)

    json_path = output_root / "analysis.json"
    csv_path = output_root / "analysis.csv"
    md_path = output_root / "analysis.md"
    candidates_json_path = output_root / "representative_candidates.json"
    candidates_csv_path = output_root / "representative_candidates.csv"

    json_rows = [asdict(row) for row in rows]
    csv_rows = [
        {
            "family": row.family,
            "representative_n": row.representative_n,
            "N": row.N,
            "depth": row.depth,
            "depth_source": row.depth_source,
            "raw_qasm3_path": row.raw_qasm3_path,
            "canonical_qasm3_path": row.canonical_qasm3_path,
            "status": row.status,
            "note": row.note,
            "compiled_gate_count": row.compiled_gate_count,
            "compiled_x_type_count": row.compiled_x_type_count,
            "compiled_z_type_count": row.compiled_z_type_count,
            "compiled_h_type_count": row.compiled_h_type_count,
            "M": row.M,
            "rho_M": row.rho_M,
            "rho_X": row.rho_X,
            "rho_L": row.rho_L,
            "zh_gate_count": row.zh_gate_count,
            "zh_traversal_volume": row.zh_traversal_volume,
            "zh_full_width_volume": row.zh_full_width_volume,
            "clear_gates_calls": row.clear_gates_calls,
            "expansion_event_count": row.expansion_event_count,
        }
        for row in rows
    ]
    candidate_rows = [
        {"criterion": key, **value}
        for key, value in summary["representative_candidates"].items()
        if value is not None
    ]

    write_json(
        json_path,
        {
            "params": {
                "canonical_manifest_json_path": repo_rel(canonical_manifest_path),
                "zxh_backend": zxh_backend,
                "zxh_stage_dir": zxh_stage_dir,
            },
            "summary": summary,
            "rows": json_rows,
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
            "status",
            "note",
            "compiled_gate_count",
            "compiled_x_type_count",
            "compiled_z_type_count",
            "compiled_h_type_count",
            "M",
            "rho_M",
            "rho_X",
            "rho_L",
            "zh_gate_count",
            "zh_traversal_volume",
            "zh_full_width_volume",
            "clear_gates_calls",
            "expansion_event_count",
        ],
    )
    md_path.write_text(
        _markdown_report(rows, summary, zxh_backend=zxh_backend, zxh_stage_dir=zxh_stage_dir),
        encoding="utf-8",
    )
    write_json(candidates_json_path, {"rows": candidate_rows})
    write_csv(
        candidates_csv_path,
        candidate_rows,
        [
            "criterion",
            "family",
            "representative_n",
            "N",
            "M",
            "rho_M",
            "rho_X",
            "rho_L",
            "canonical_qasm3_path",
            "raw_qasm3_path",
        ],
    )

    return {
        "rows": json_rows,
        "summary": summary,
        "output_dir": repo_rel(output_root),
        "zxh_backend": zxh_backend,
        "zxh_stage_dir": zxh_stage_dir,
        "json_path": repo_rel(json_path),
        "csv_path": repo_rel(csv_path),
        "md_path": repo_rel(md_path),
        "representative_candidates_json_path": repo_rel(candidates_json_path),
        "representative_candidates_csv_path": repo_rel(candidates_csv_path),
    }
