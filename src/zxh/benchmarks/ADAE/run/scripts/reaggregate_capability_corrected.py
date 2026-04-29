#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
BASE_DIR = REPO_ROOT / "benchmarks" / "ADAE" / "results" / "paper_submission_raw_data_20260409"
RUN_DIR = REPO_ROOT / "benchmarks" / "ADAE" / "results" / "run" / "representative_cuda"

BASE_SELECTED = BASE_DIR / "selected_30_family_filled.csv"
QBLAZE_TOTAL = BASE_DIR / "qblaze_n30_total.csv"
RUN3_RAW = RUN_DIR / "run3" / "raw_results.csv"

OUTPUT_PREFIX = BASE_DIR / "selected_30_family_capability_corrected"
TIME_BUDGET_MS = 100_000.0


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def gm(values: list[float]) -> float | None:
    if not values:
        return None
    return math.exp(sum(math.log(v) for v in values) / len(values))


def summarize_status(statuses: set[str]) -> str:
    if statuses == {"pass"}:
        return "pass"
    if "timeout" in statuses:
        return "timeout"
    if "undetermined" in statuses:
        return "undetermined"
    return "error"


def recompute_run3_corrected(raw_rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in raw_rows:
        groups[(row["family"], row["backend"])].append(row)

    out: dict[tuple[str, str], dict[str, Any]] = {}
    for key, bucket in groups.items():
        statuses = {row["status"] for row in bucket}
        passed = [float(row["execute_ms"]) + float(row["sample_ms"]) for row in bucket if row["status"] == "pass"]
        out[key] = {
            "status": summarize_status(statuses),
            "repeats": len(passed),
            "end_to_end_ms_mean": (sum(passed) / len(passed)) if passed else None,
        }
    return out


def qblaze_cap100_row(qrow: dict[str, str] | None) -> tuple[str, str, str, str]:
    if qrow is None:
        return "not_available", "", "", "No qblaze record."

    status = qrow["qblaze_final_status"] or "not_available"
    source_run = qrow["qblaze_final_source_run"]
    note = qrow["qblaze_final_note"]
    time_str = qrow["qblaze_final_end_to_end_ms"]

    if status == "pass" and time_str:
        if float(time_str) <= TIME_BUDGET_MS:
            return "pass", time_str, source_run, f"{note}; normalized under 100s budget."
        return "timeout", "", source_run, f"{note}; reclassified timeout under 100s budget."

    if status == "not_run_non30":
        return status, "", source_run, note
    if status in {"error", "timeout"}:
        return status, "", source_run, note
    return status, time_str, source_run, note


def format_float(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.15f}".rstrip("0").rstrip(".")


def build_corrected_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected_rows = read_csv(BASE_SELECTED)
    qblaze_rows = {row["family"]: row for row in read_csv(QBLAZE_TOTAL)}
    run3_corrected = recompute_run3_corrected(read_csv(RUN3_RAW))

    corrected_rows: list[dict[str, Any]] = []
    cudaq_speedups: list[float] = []
    qblaze_speedups: list[float] = []
    cudaq_speedups_no_ghz: list[float] = []
    qblaze_speedups_no_ghz: list[float] = []

    for row in selected_rows:
        out = dict(row)
        family = row["family"]

        cudaq_status = row["cudaq_filled_status"]
        cudaq_time = row["cudaq_filled_end_to_end_ms"]
        cudaq_source = row["cudaq_filled_source_run"]
        cudaq_note = row["cudaq_filled_note"]
        if cudaq_source == "run3" and cudaq_status == "pass":
            corrected = run3_corrected[(family, "cudaq")]
            cudaq_time = format_float(corrected["end_to_end_ms_mean"])
            cudaq_note = "Historical run3 value corrected offline from raw execute_ms + sample_ms."
        if cudaq_status == "pass" and cudaq_time and float(cudaq_time) > TIME_BUDGET_MS:
            cudaq_status = "timeout"
            cudaq_time = ""
            cudaq_note = f"{cudaq_note}; reclassified timeout under 100s budget."

        zxh_status = row["zxh_filled_status"]
        zxh_time = row["zxh_filled_end_to_end_ms"]
        zxh_source = row["zxh_filled_source_run"]
        zxh_note = row["zxh_filled_note"]
        if zxh_source == "run3" and zxh_status == "pass":
            corrected = run3_corrected[(family, "zxh-cuda")]
            zxh_time = format_float(corrected["end_to_end_ms_mean"])
            zxh_note = "Historical run3 value corrected offline from raw execute_ms + sample_ms."
        if zxh_status == "pass" and zxh_time and float(zxh_time) > TIME_BUDGET_MS:
            zxh_status = "timeout"
            zxh_time = ""
            zxh_note = f"{zxh_note}; reclassified timeout under 100s budget."

        qblaze_status, qblaze_time, qblaze_source, qblaze_note = qblaze_cap100_row(qblaze_rows.get(family))

        out["cudaq_cap_status"] = cudaq_status
        out["cudaq_cap_end_to_end_ms"] = cudaq_time
        out["cudaq_cap_source_run"] = cudaq_source
        out["cudaq_cap_note"] = cudaq_note

        out["zxh_cap_status"] = zxh_status
        out["zxh_cap_end_to_end_ms"] = zxh_time
        out["zxh_cap_source_run"] = zxh_source
        out["zxh_cap_note"] = zxh_note

        out["qblaze_cap100_status"] = qblaze_status
        out["qblaze_cap100_end_to_end_ms"] = qblaze_time
        out["qblaze_cap100_source_run"] = qblaze_source
        out["qblaze_cap100_note"] = qblaze_note

        zxh_vs_cudaq = ""
        if cudaq_status == "pass" and zxh_status == "pass" and cudaq_time and zxh_time:
            ratio = float(cudaq_time) / float(zxh_time)
            zxh_vs_cudaq = f"{ratio:.6f}"
            cudaq_speedups.append(ratio)
            if family != "ghz":
                cudaq_speedups_no_ghz.append(ratio)

        zxh_vs_qblaze = ""
        if qblaze_status == "pass" and zxh_status == "pass" and qblaze_time and zxh_time:
            ratio = float(qblaze_time) / float(zxh_time)
            zxh_vs_qblaze = f"{ratio:.6f}"
            qblaze_speedups.append(ratio)
            if family != "ghz":
                qblaze_speedups_no_ghz.append(ratio)

        out["zxh_speedup_over_cudaq_cap"] = zxh_vs_cudaq
        out["zxh_speedup_over_qblaze_cap100"] = zxh_vs_qblaze
        corrected_rows.append(out)

    summary = {
        "time_budget_s": 100.0,
        "gpu_metric": "execute_ms + sample_ms",
        "sources": {
            "base_selected_table": str(BASE_SELECTED.relative_to(REPO_ROOT)),
            "run3_raw": str(RUN3_RAW.relative_to(REPO_ROOT)),
            "qblaze_total": str(QBLAZE_TOTAL.relative_to(REPO_ROOT)),
        },
        "coverage": {
            "cudaq": sum(row["cudaq_cap_status"] == "pass" for row in corrected_rows),
            "zxh": sum(row["zxh_cap_status"] == "pass" for row in corrected_rows),
            "qblaze_cap100": sum(row["qblaze_cap100_status"] == "pass" for row in corrected_rows),
        },
        "intersections": {
            "zxh_vs_cudaq": {
                "common_pass_count": len(cudaq_speedups),
                "gm_speedup": gm(cudaq_speedups),
                "gm_speedup_excluding_ghz": gm(cudaq_speedups_no_ghz),
            },
            "zxh_vs_qblaze_cap100": {
                "common_pass_count": len(qblaze_speedups),
                "gm_speedup": gm(qblaze_speedups),
                "gm_speedup_excluding_ghz": gm(qblaze_speedups_no_ghz),
            },
        },
    }
    return corrected_rows, summary


def markdown_report(rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# Corrected Capability Table",
        "",
        "- metric: `execute_ms + sample_ms`",
        "- normalized time budget: `100s per case`",
        f"- coverage: `cudaq={summary['coverage']['cudaq']}`, `zxh={summary['coverage']['zxh']}`, `qblaze_cap100={summary['coverage']['qblaze_cap100']}`",
        (
            "- geometric mean speedup (ZXH over cuQuantum): "
            f"`{summary['intersections']['zxh_vs_cudaq']['gm_speedup']:.6f}x` "
            f"on `{summary['intersections']['zxh_vs_cudaq']['common_pass_count']}` common-pass cases"
        ),
        (
            "- geometric mean speedup (ZXH over qblaze): "
            f"`{summary['intersections']['zxh_vs_qblaze_cap100']['gm_speedup']:.6f}x` "
            f"on `{summary['intersections']['zxh_vs_qblaze_cap100']['common_pass_count']}` common-pass cases"
        ),
        (
            "- excluding `ghz`: "
            f"`ZXH/cuQuantum={summary['intersections']['zxh_vs_cudaq']['gm_speedup_excluding_ghz']:.6f}x`, "
            f"`ZXH/qblaze={summary['intersections']['zxh_vs_qblaze_cap100']['gm_speedup_excluding_ghz']:.6f}x`"
        ),
        "",
        "| family | n | cudaq_cap_status | cudaq_cap_ms | zxh_cap_status | zxh_cap_ms | zxh/cuQuantum | qblaze_cap100_status | qblaze_cap100_ms | zxh/qblaze |",
        "| --- | ---: | --- | ---: | --- | ---: | ---: | --- | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            "| {family} | {selected_n} | {cudaq_cap_status} | {cudaq_cap_end_to_end_ms} | {zxh_cap_status} | {zxh_cap_end_to_end_ms} | {zxh_speedup_over_cudaq_cap} | {qblaze_cap100_status} | {qblaze_cap100_end_to_end_ms} | {zxh_speedup_over_qblaze_cap100} |".format(
                **row
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    rows, summary = build_corrected_rows()

    fieldnames = list(rows[0].keys())
    write_csv(OUTPUT_PREFIX.with_suffix(".csv"), rows, fieldnames)
    write_json(OUTPUT_PREFIX.with_suffix(".json"), {"summary": summary, "rows": rows})
    OUTPUT_PREFIX.with_suffix(".md").write_text(markdown_report(rows, summary), encoding="utf-8")
    write_json(
        OUTPUT_PREFIX.with_name(OUTPUT_PREFIX.name + "_sources.json"),
        {
            "base_selected_table": str(BASE_SELECTED.relative_to(REPO_ROOT)),
            "run3_raw": str(RUN3_RAW.relative_to(REPO_ROOT)),
            "qblaze_total": str(QBLAZE_TOTAL.relative_to(REPO_ROOT)),
            "time_budget_s": 100.0,
            "gpu_metric": "execute_ms + sample_ms",
        },
    )
    print(f"wrote_csv={OUTPUT_PREFIX.with_suffix('.csv')}")
    print(f"wrote_json={OUTPUT_PREFIX.with_suffix('.json')}")
    print(f"wrote_md={OUTPUT_PREFIX.with_suffix('.md')}")
    print(
        "zxh_vs_cudaq_gm={:.6f} common={}".format(
            summary["intersections"]["zxh_vs_cudaq"]["gm_speedup"],
            summary["intersections"]["zxh_vs_cudaq"]["common_pass_count"],
        )
    )
    print(
        "zxh_vs_qblaze_gm={:.6f} common={}".format(
            summary["intersections"]["zxh_vs_qblaze_cap100"]["gm_speedup"],
            summary["intersections"]["zxh_vs_qblaze_cap100"]["common_pass_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
