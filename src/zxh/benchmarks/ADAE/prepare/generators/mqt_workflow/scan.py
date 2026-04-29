from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .common import (
    WORKFLOW_OUTPUT_ROOT,
    benchmark_default_kwargs,
    import_mqt_bench,
    is_environment_error,
    load_known_valid_sizes_20_32,
    repo_rel,
    representative_circuit,
    write_csv,
    write_json,
    write_qasm3,
)


@dataclass
class ScanRow:
    family: str
    valid_size_source: str
    valid_sizes: list[int]
    representative_n: int | None
    N: int | None
    circuit_source: str | None
    case_qasm3_path: str | None
    status: str
    note: str | None


def _valid_sizes_for_family(
    *,
    family: str,
    n_min: int,
    n_max: int,
    opt_level: int,
    use_known_size_cache: bool,
) -> tuple[list[int], str]:
    if use_known_size_cache and n_min == 20 and n_max == 32:
        cached = load_known_valid_sizes_20_32()
        if cached is not None and family in cached:
            return list(cached[family]), "known_valid_sizes_20_32"

    BenchmarkLevel, get_benchmark, _ = import_mqt_bench()
    sizes: list[int] = []
    kwargs = benchmark_default_kwargs(family)
    for n in range(n_min, n_max + 1):
        try:
            get_benchmark(family, BenchmarkLevel.INDEP, n, opt_level=opt_level, **kwargs)
        except Exception as exc:
            if is_environment_error(exc):
                raise RuntimeError(
                    f"Failed while probing benchmark family {family!r}; environment dependency is missing or broken."
                ) from exc
            continue
        sizes.append(n)
    return sizes, "live_probe"


def _scan_family(
    *,
    family: str,
    cases_dir: Path,
    n_min: int,
    n_max: int,
    opt_level: int,
    use_known_size_cache: bool,
) -> ScanRow:
    valid_sizes, valid_size_source = _valid_sizes_for_family(
        family=family,
        n_min=n_min,
        n_max=n_max,
        opt_level=opt_level,
        use_known_size_cache=use_known_size_cache,
    )
    if not valid_sizes:
        return ScanRow(
            family=family,
            valid_size_source=valid_size_source,
            valid_sizes=[],
            representative_n=None,
            N=None,
            circuit_source=None,
            case_qasm3_path=None,
            status="no_valid_instance_in_range",
            note=None,
        )

    representative_n = max(valid_sizes)
    circuit, circuit_source, note = representative_circuit(
        family=family,
        requested_n=representative_n,
        opt_level=opt_level,
    )

    case_qasm3_path = cases_dir / f"{family}_n{representative_n}.qasm3"
    write_qasm3(case_qasm3_path, circuit)

    return ScanRow(
        family=family,
        valid_size_source=valid_size_source,
        valid_sizes=valid_sizes,
        representative_n=representative_n,
        N=circuit.num_qubits,
        circuit_source=circuit_source,
        case_qasm3_path=repo_rel(case_qasm3_path),
        status="case_generated",
        note=note,
    )


def _markdown_report(
    *,
    rows: list[ScanRow],
    n_min: int,
    n_max: int,
    opt_level: int,
) -> str:
    total = len(rows)
    with_valid = sum(1 for row in rows if row.representative_n is not None)
    generated = sum(1 for row in rows if row.status == "case_generated")

    lines = [
        "# Pass 1: Scan",
        "",
        f"- range: `{n_min}..{n_max}`",
        f"- opt_level: `{opt_level}`",
        f"- total_families: `{total}`",
        f"- families_with_valid_instance: `{with_valid}`",
        f"- generated_representative_cases: `{generated}`",
        "",
        "| family | valid_sizes | rep_n | N | circuit_source | status |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        valid_sizes = ",".join(str(n) for n in row.valid_sizes)
        rep_n = "" if row.representative_n is None else str(row.representative_n)
        N = "" if row.N is None else str(row.N)
        source = "" if row.circuit_source is None else row.circuit_source
        lines.append(
            f"| {row.family} | {valid_sizes} | {rep_n} | {N} | {source} | {row.status} |"
        )
    return "\n".join(lines) + "\n"


def run_scan(
    *,
    output_dir: Path | None = None,
    n_min: int = 20,
    n_max: int = 32,
    opt_level: int = 2,
    use_known_size_cache: bool = True,
) -> dict[str, Any]:
    _, _, get_available_benchmark_names = import_mqt_bench()
    families = sorted(get_available_benchmark_names())

    output_root = (WORKFLOW_OUTPUT_ROOT / "01_pass1_scan") if output_dir is None else output_dir.resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    cases_dir = output_root / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    for stale in cases_dir.glob("*.qpy"):
        stale.unlink()
    for stale in cases_dir.glob("*.qasm3"):
        stale.unlink()

    rows = [
        _scan_family(
            family=family,
            cases_dir=cases_dir,
            n_min=n_min,
            n_max=n_max,
            opt_level=opt_level,
            use_known_size_cache=use_known_size_cache,
        )
        for family in families
    ]

    json_path = output_root / "scan.json"
    csv_path = output_root / "scan.csv"
    md_path = output_root / "scan.md"

    json_rows = [asdict(row) for row in rows]
    csv_rows = [
        {
            "family": row.family,
            "valid_size_source": row.valid_size_source,
            "valid_sizes": ";".join(str(n) for n in row.valid_sizes),
            "representative_n": row.representative_n,
            "N": row.N,
            "circuit_source": row.circuit_source,
            "case_qasm3_path": row.case_qasm3_path,
            "status": row.status,
            "note": row.note,
        }
        for row in rows
    ]

    write_json(
        json_path,
        {
            "params": {
                "n_min": n_min,
                "n_max": n_max,
                "opt_level": opt_level,
                "use_known_size_cache": use_known_size_cache,
            },
            "rows": json_rows,
        },
    )
    write_csv(
        csv_path,
        csv_rows,
        [
            "family",
            "valid_size_source",
            "valid_sizes",
            "representative_n",
            "N",
            "circuit_source",
            "case_qasm3_path",
            "status",
            "note",
        ],
    )
    md_path.write_text(
        _markdown_report(
            rows=rows,
            n_min=n_min,
            n_max=n_max,
            opt_level=opt_level,
        ),
        encoding="utf-8",
    )

    return {
        "families": families,
        "rows": json_rows,
        "output_dir": repo_rel(output_root),
        "cases_dir": repo_rel(cases_dir),
        "json_path": repo_rel(json_path),
        "csv_path": repo_rel(csv_path),
        "md_path": repo_rel(md_path),
    }
