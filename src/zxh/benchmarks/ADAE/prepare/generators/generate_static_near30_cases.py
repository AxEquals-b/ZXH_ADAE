#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from benchmarks.stage import activate_python_stage

from benchmarks.ADAE.prepare.generators.mqt_workflow.canonical_ir import canonicalize_circuit
from benchmarks.ADAE.prepare.generators.mqt_workflow.common import (
    PREPARE_RESULTS_ROOT,
    benchmark_default_kwargs,
    estimate_qasm3_gate_count,
    import_mqt_bench,
    is_environment_error,
    load_known_valid_sizes_20_32,
    qasm3_contains_branching,
    repo_rel,
    write_csv,
    write_json,
    write_qasm3,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
RAW_DIRNAME = "raw_cases"
COMMON_IR_DIRNAME = "common_ir"
DEFAULT_OUTPUT_ROOT = PREPARE_RESULTS_ROOT / "static_near30"
KNOWN_DYNAMIC_FAMILIES = {"ghz_dynamic", "seven_qubit_steane_code"}


@dataclass
class Near30Row:
    family: str
    target_n: int
    selected_n: int | None
    selected_n_source: str | None
    valid_sizes_20_32: list[int]
    size_distance_to_target: int | None
    raw_qasm3_path: str | None
    canonical_qasm3_path: str | None
    is_static: bool | None
    branching_types: list[str]
    estimated_raw_gate_count: int | None
    opaque_instruction_types: list[str]
    canonical_gate_count: int | None
    canonical_gate_types: list[str]
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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate one near-30 raw case and common IR for each static MQT Bench family, then analyze it with ZXH."
    )
    parser.add_argument("--target-n", type=int, default=30)
    parser.add_argument("--opt-level", type=int, choices=range(4), default=2)
    parser.add_argument("--zxh-backend", type=str, default="cuda")
    parser.add_argument("--probe-max-n", type=int, default=80)
    parser.add_argument("--max-estimated-gate-count", type=int, default=1_000_000)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def _load_staged_analyzer(backend: str):
    stage_dir = activate_python_stage(REPO_ROOT, backend)
    doomed = [name for name in sys.modules if name == "zxhsim" or name.startswith("zxhsim.")]
    for name in doomed:
        del sys.modules[name]
    analyzer_mod = importlib.import_module("zxhsim.analyzer")
    return stage_dir, analyzer_mod.analyze_circuit


def _resolve_selected_n(
    *,
    family: str,
    target_n: int,
    opt_level: int,
    cached_valid_sizes_20_32: dict[str, list[int]] | None,
    probe_max_n: int,
) -> tuple[int, str, list[int]]:
    valid_sizes_20_32 = []
    if cached_valid_sizes_20_32 is not None:
        valid_sizes_20_32 = list(cached_valid_sizes_20_32.get(family, []))
    if valid_sizes_20_32:
        if target_n in valid_sizes_20_32:
            return target_n, "cached_20_32_exact", valid_sizes_20_32
        selected_n = min(valid_sizes_20_32, key=lambda n: (abs(n - target_n), n))
        return selected_n, "cached_20_32_nearest", valid_sizes_20_32

    BenchmarkLevel, get_benchmark, _ = import_mqt_bench()
    kwargs = benchmark_default_kwargs(family)
    for delta in range(0, max(target_n, probe_max_n) + 1):
        candidates: list[int] = []
        lower = target_n - delta
        upper = target_n + delta
        if lower > 0:
            candidates.append(lower)
        if upper != lower and upper <= probe_max_n:
            candidates.append(upper)
        for n in candidates:
            try:
                get_benchmark(family, BenchmarkLevel.INDEP, n, opt_level=opt_level, **kwargs)
            except Exception as exc:
                if is_environment_error(exc):
                    raise RuntimeError(
                        f"Failed while probing benchmark family {family!r}; environment dependency is missing or broken."
                    ) from exc
                continue
            return n, "live_probe_nearest", valid_sizes_20_32
    raise RuntimeError(
        f"Could not find a valid size near target_n={target_n} for family {family!r} up to probe_max_n={probe_max_n}."
    )


def _generation_failure_row(
    *,
    family: str,
    target_n: int,
    valid_sizes_20_32: list[int],
    note: str,
) -> Near30Row:
    return Near30Row(
        family=family,
        target_n=target_n,
        selected_n=None,
        selected_n_source=None,
        valid_sizes_20_32=valid_sizes_20_32,
        size_distance_to_target=None,
        raw_qasm3_path=None,
        canonical_qasm3_path=None,
        is_static=None,
        branching_types=[],
        estimated_raw_gate_count=None,
        opaque_instruction_types=[],
        canonical_gate_count=None,
        canonical_gate_types=[],
        status="generation_failed",
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


def _process_family(
    *,
    family: str,
    target_n: int,
    opt_level: int,
    raw_root: Path,
    canonical_root: Path,
    analyze_circuit_fn,
    cached_valid_sizes_20_32: dict[str, list[int]] | None,
    probe_max_n: int,
    max_estimated_gate_count: int,
) -> Near30Row:
    if family in KNOWN_DYNAMIC_FAMILIES:
        return _generation_failure_row(
            family=family,
            target_n=target_n,
            valid_sizes_20_32=list(cached_valid_sizes_20_32.get(family, [])) if cached_valid_sizes_20_32 else [],
            note="Excluded as known dynamic-control family.",
        )

    try:
        selected_n, selected_n_source, valid_sizes_20_32 = _resolve_selected_n(
            family=family,
            target_n=target_n,
            opt_level=opt_level,
            cached_valid_sizes_20_32=cached_valid_sizes_20_32,
            probe_max_n=probe_max_n,
        )
    except Exception as exc:
        return _generation_failure_row(
            family=family,
            target_n=target_n,
            valid_sizes_20_32=list(cached_valid_sizes_20_32.get(family, [])) if cached_valid_sizes_20_32 else [],
            note=f"{type(exc).__name__}: {exc}",
        )

    try:
        from benchmarks.ADAE.prepare.generators.mqt_workflow.common import experiment_case_circuit, load_qasm3_program

        circuit, circuit_source, source_note = experiment_case_circuit(
            family=family,
            requested_n=selected_n,
            opt_level=opt_level,
        )
        raw_path = raw_root / f"{family}_n{selected_n}.qasm3"
        write_qasm3(raw_path, circuit)

        raw_program = load_qasm3_program(raw_path)
        contains_branching, branching_types = qasm3_contains_branching(raw_program)
        estimated_raw_gate_count, opaque_instruction_types = estimate_qasm3_gate_count(raw_program)
        if contains_branching:
            return Near30Row(
                family=family,
                target_n=target_n,
                selected_n=selected_n,
                selected_n_source=selected_n_source,
                valid_sizes_20_32=valid_sizes_20_32,
                size_distance_to_target=abs(selected_n - target_n),
                raw_qasm3_path=repo_rel(raw_path),
                canonical_qasm3_path=None,
                is_static=False,
                branching_types=branching_types,
                estimated_raw_gate_count=estimated_raw_gate_count,
                opaque_instruction_types=opaque_instruction_types,
                canonical_gate_count=None,
                canonical_gate_types=[],
                status="excluded_dynamic_after_selection",
                note=" ".join(part for part in [source_note, f"circuit_source={circuit_source}."] if part).strip() or None,
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

        if estimated_raw_gate_count > max_estimated_gate_count:
            return Near30Row(
                family=family,
                target_n=target_n,
                selected_n=selected_n,
                selected_n_source=selected_n_source,
                valid_sizes_20_32=valid_sizes_20_32,
                size_distance_to_target=abs(selected_n - target_n),
                raw_qasm3_path=repo_rel(raw_path),
                canonical_qasm3_path=None,
                is_static=True,
                branching_types=[],
                estimated_raw_gate_count=estimated_raw_gate_count,
                opaque_instruction_types=opaque_instruction_types,
                canonical_gate_count=None,
                canonical_gate_types=[],
                status="skipped_large_raw_gate_count",
                note=(
                    f"estimated_raw_gate_count={estimated_raw_gate_count} exceeds "
                    f"max_estimated_gate_count={max_estimated_gate_count}."
                ),
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

        canonical = canonicalize_circuit(circuit)
        canonical_path = canonical_root / f"{family}_n{selected_n}.qasm3"
        write_qasm3(canonical_path, canonical)
        gate_types = sorted({inst.operation.name.lower() for inst in canonical.data})
        stats = analyze_circuit_fn(canonical)
        note_parts = [source_note, f"circuit_source={circuit_source}.", f"selected_n_source={selected_n_source}."]
        return Near30Row(
            family=family,
            target_n=target_n,
            selected_n=selected_n,
            selected_n_source=selected_n_source,
            valid_sizes_20_32=valid_sizes_20_32,
            size_distance_to_target=abs(selected_n - target_n),
            raw_qasm3_path=repo_rel(raw_path),
            canonical_qasm3_path=repo_rel(canonical_path),
            is_static=True,
            branching_types=[],
            estimated_raw_gate_count=estimated_raw_gate_count,
            opaque_instruction_types=opaque_instruction_types,
            canonical_gate_count=len(canonical.data),
            canonical_gate_types=gate_types,
            status="analyzed",
            note=" ".join(part for part in note_parts if part).strip() or None,
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
        note_parts = [f"{type(exc).__name__}: {exc}"]
        if "source_note" in locals() and source_note:
            note_parts.insert(0, source_note)
        return Near30Row(
            family=family,
            target_n=target_n,
            selected_n=selected_n,
            selected_n_source=selected_n_source,
            valid_sizes_20_32=valid_sizes_20_32,
            size_distance_to_target=abs(selected_n - target_n),
            raw_qasm3_path=repo_rel(raw_path) if "raw_path" in locals() and raw_path.exists() else None,
            canonical_qasm3_path=repo_rel(canonical_path)
            if "canonical_path" in locals() and canonical_path.exists()
            else None,
            is_static=None,
            branching_types=[],
            estimated_raw_gate_count=estimated_raw_gate_count if "estimated_raw_gate_count" in locals() else None,
            opaque_instruction_types=opaque_instruction_types if "opaque_instruction_types" in locals() else [],
            canonical_gate_count=None,
            canonical_gate_types=[],
            status="analysis_failed",
            note=" ".join(note_parts),
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


def _markdown_report(rows: list[Near30Row], *, target_n: int, zxh_backend: str, zxh_stage_dir: str) -> str:
    analyzed = [row for row in rows if row.status == "analyzed"]
    excluded_dynamic = [row for row in rows if row.status == "excluded_dynamic_after_selection"]
    generation_failed = [row for row in rows if row.status == "generation_failed"]
    analysis_failed = [row for row in rows if row.status == "analysis_failed"]
    skipped_large = [row for row in rows if row.status == "skipped_large_raw_gate_count"]

    lines = [
        "# Static Near-30 Family Report",
        "",
        f"- target_n: `{target_n}`",
        f"- total_rows: `{len(rows)}`",
        f"- analyzed: `{len(analyzed)}`",
        f"- excluded_dynamic_after_selection: `{len(excluded_dynamic)}`",
        f"- generation_failed: `{len(generation_failed)}`",
        f"- analysis_failed: `{len(analysis_failed)}`",
        f"- skipped_large_raw_gate_count: `{len(skipped_large)}`",
        f"- zxh_backend: `{zxh_backend}`",
        f"- zxh_stage_dir: `{repo_rel(Path(zxh_stage_dir))}`",
        "",
        "| family | selected_n | static | M | rho_M | rho_X | rho_L | status |",
        "| --- | ---: | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        selected_n = "" if row.selected_n is None else str(row.selected_n)
        is_static = "" if row.is_static is None else ("Y" if row.is_static else "N")
        M = "" if row.M is None else str(row.M)
        rho_M = "" if row.rho_M is None else f"{row.rho_M:.6f}"
        rho_X = "" if row.rho_X is None else f"{row.rho_X:.6f}"
        rho_L = "" if row.rho_L is None else f"{row.rho_L:.6f}"
        lines.append(f"| {row.family} | {selected_n} | {is_static} | {M} | {rho_M} | {rho_X} | {rho_L} | {row.status} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    args = _parse_args()
    output_root = args.output_root.resolve()
    raw_root = output_root / RAW_DIRNAME
    canonical_root = output_root / COMMON_IR_DIRNAME
    raw_root.mkdir(parents=True, exist_ok=True)
    canonical_root.mkdir(parents=True, exist_ok=True)
    for stale in raw_root.glob("*.qasm3"):
        stale.unlink()
    for stale in canonical_root.glob("*.qasm3"):
        stale.unlink()

    _, _, get_available_benchmark_names = import_mqt_bench()
    families = sorted(get_available_benchmark_names())
    cached_valid_sizes_20_32 = load_known_valid_sizes_20_32()
    zxh_stage_dir, analyze_circuit_fn = _load_staged_analyzer(args.zxh_backend)

    rows: list[Near30Row] = []
    selected_families = [family for family in families if family not in KNOWN_DYNAMIC_FAMILIES]
    for index, family in enumerate(selected_families, start=1):
        print(f"[{index}/{len(selected_families)}] family={family}", flush=True)
        row = _process_family(
            family=family,
            target_n=args.target_n,
            opt_level=args.opt_level,
            raw_root=raw_root,
            canonical_root=canonical_root,
            analyze_circuit_fn=analyze_circuit_fn,
            cached_valid_sizes_20_32=cached_valid_sizes_20_32,
            probe_max_n=args.probe_max_n,
            max_estimated_gate_count=args.max_estimated_gate_count,
        )
        rows.append(row)
        print(
            f"[{index}/{len(selected_families)}] done family={family} status={row.status} selected_n={row.selected_n}",
            flush=True,
        )

    json_path = output_root / "analysis.json"
    csv_path = output_root / "analysis.csv"
    md_path = output_root / "analysis.md"

    json_rows = [asdict(row) for row in rows]
    csv_rows = [
        {
            "family": row.family,
            "target_n": row.target_n,
            "selected_n": row.selected_n,
            "selected_n_source": row.selected_n_source,
            "valid_sizes_20_32": ";".join(str(n) for n in row.valid_sizes_20_32),
            "size_distance_to_target": row.size_distance_to_target,
            "raw_qasm3_path": row.raw_qasm3_path,
            "canonical_qasm3_path": row.canonical_qasm3_path,
            "is_static": row.is_static,
            "branching_types": ";".join(row.branching_types),
            "estimated_raw_gate_count": row.estimated_raw_gate_count,
            "opaque_instruction_types": ";".join(row.opaque_instruction_types),
            "canonical_gate_count": row.canonical_gate_count,
            "canonical_gate_types": ";".join(row.canonical_gate_types),
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

    write_json(
        json_path,
        {
            "params": {
                "target_n": args.target_n,
                "opt_level": args.opt_level,
                "zxh_backend": args.zxh_backend,
                "probe_max_n": args.probe_max_n,
                "output_root": repo_rel(output_root),
                "raw_root": repo_rel(raw_root),
                "canonical_root": repo_rel(canonical_root),
                "zxh_stage_dir": repo_rel(Path(zxh_stage_dir)),
            },
            "rows": json_rows,
        },
    )
    write_csv(
        csv_path,
        csv_rows,
        [
            "family",
            "target_n",
            "selected_n",
            "selected_n_source",
            "valid_sizes_20_32",
            "size_distance_to_target",
            "raw_qasm3_path",
            "canonical_qasm3_path",
            "is_static",
            "branching_types",
            "estimated_raw_gate_count",
            "opaque_instruction_types",
            "canonical_gate_count",
            "canonical_gate_types",
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
        _markdown_report(
            rows,
            target_n=args.target_n,
            zxh_backend=args.zxh_backend,
            zxh_stage_dir=str(zxh_stage_dir),
        ),
        encoding="utf-8",
    )

    print(f"analysis_json={json_path}")
    print(f"analysis_csv={csv_path}")
    print(f"analysis_md={md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
