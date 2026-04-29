#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = PROJECT_ROOT / "output" / "results"
FIGURES_ROOT = PROJECT_ROOT / "output" / "figures"
ZXH_RUN_ID = os.environ.get("ZXH_RUN_ID", "latest")
BASELINE_RUN_ID = os.environ.get("BASELINE_RUN_ID", "latest")

NEAR30_BACKENDS = [
    ("zxh", ZXH_RUN_ID, "ZXH-Sim"),
    ("cuQuantum", BASELINE_RUN_ID, "cuQuantum"),
    ("qblaze", BASELINE_RUN_ID, "qblaze"),
    ("ddsim", BASELINE_RUN_ID, "DDSIM"),
]

mpl.rcParams.update({
    "font.family": "STIXGeneral",
    "mathtext.fontset": "stix",
    "font.size": 9.0,
    "axes.labelsize": 11.5,
    "axes.titlesize": 11.0,
    "xtick.labelsize": 9.0,
    "ytick.labelsize": 9.0,
    "legend.fontsize": 9.0,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.linewidth": 0.8,
    "axes.edgecolor": "#666666",
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "savefig.bbox": "tight",
})

backend_style = {
    "cuQuantum": {"color": "#1f77b4", "label": "cuQuantum"},
    "DDSIM": {"color": "#7a7a7a", "label": "DDSIM"},
    "qblaze": {"color": "#2ca02c", "label": "qblaze"},
    "ZXH-Sim": {"color": "#D62728", "label": "ZXH-Sim"},
}


def parse_times(text: object) -> list[float]:
    if not isinstance(text, str) or not text.strip():
        return []
    values = json.loads(text)
    return [float(value) for value in values if value is not None]


def mean_after_warmup(times: list[float]) -> float | None:
    if len(times) > 1:
        return float(np.mean(times[1:]))
    if len(times) == 1:
        return float(times[0])
    return None


def load_near30(backend_dir: str, run_id: str, label: str) -> pd.DataFrame:
    path = RESULTS_ROOT / backend_dir / run_id / "near30.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    rows: list[dict[str, object]] = []
    for _, row in df.iterrows():
        status = str(row["status"])
        runtime = math.nan
        if status == "pass":
            value = mean_after_warmup(parse_times(row.get("times", "")))
            if value is not None:
                runtime = value
        rows.append({
            "backend": label,
            "backend_dir": backend_dir,
            "run_id": run_id,
            "circuit": str(row["circuit"]),
            "status": status,
            "runtime_s": runtime,
        })
    return pd.DataFrame(rows)


def build_table() -> pd.DataFrame:
    frames = [load_near30(backend, run_id, label) for backend, run_id, label in NEAR30_BACKENDS]
    return pd.concat(frames, ignore_index=True)


def geometric_speedup(table: pd.DataFrame, numerator: str, denominator: str, exclude_ghz: bool) -> tuple[float, int]:
    fast = table[(table.backend == denominator) & (table.status == "pass")].set_index("circuit")
    slow = table[(table.backend == numerator) & (table.status == "pass")].set_index("circuit")
    common = sorted(set(fast.index) & set(slow.index))
    if exclude_ghz:
        common = [name for name in common if not name.startswith("ghz_")]
    ratios = [float(slow.loc[name, "runtime_s"]) / float(fast.loc[name, "runtime_s"]) for name in common]
    ratios = [ratio for ratio in ratios if math.isfinite(ratio) and ratio > 0.0]
    if not ratios:
        return math.nan, 0
    return math.exp(sum(math.log(ratio) for ratio in ratios) / len(ratios)), len(ratios)


def summarize(table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    total = int(table["circuit"].nunique())
    for _, _, label in NEAR30_BACKENDS:
        sub = table[table.backend == label]
        solved = int((sub.status == "pass").sum())
        failed = sorted(sub[sub.status != "pass"]["circuit"].tolist())
        rows.append({
            "backend": label,
            "solved": solved,
            "total": total,
            "failed": failed,
        })
    return pd.DataFrame(rows)


def style_axes(ax: plt.Axes) -> None:
    ax.set_facecolor("white")
    ax.grid(True, axis="y", which="major", color="#d2d2d2", linewidth=0.65, alpha=0.85)
    ax.grid(True, axis="y", which="minor", color="#ebebeb", linewidth=0.45, alpha=0.85)
    ax.set_axisbelow(True)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_linewidth(0.8)
        ax.spines[spine].set_color("#666666")


def main() -> int:
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)
    table = build_table()
    summary = summarize(table)
    total = int(summary["total"].iloc[0])
    cu_over_zxh, cu_common = geometric_speedup(table, "cuQuantum", "ZXH-Sim", exclude_ghz=False)
    cu_over_zxh_no_ghz, cu_common_no_ghz = geometric_speedup(table, "cuQuantum", "ZXH-Sim", exclude_ghz=True)

    fig, ax = plt.subplots(figsize=(4.2, 2.55), dpi=300)
    x = np.arange(len(summary))
    colors = [backend_style[name]["color"] for name in summary["backend"]]
    bars = ax.bar(x, summary["solved"], color=colors, width=0.64, edgecolor="#333333", linewidth=0.45)
    for bar, solved in zip(bars, summary["solved"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2.0,
            float(solved) + 0.45,
            f"{int(solved)}/{total}",
            ha="center",
            va="bottom",
            fontsize=9.4,
            fontweight="bold",
            color="#222222",
        )

    ax.set_ylim(0, total + 3.0)
    ax.set_ylabel("Solved near-30 cases")
    ax.set_xticks(x)
    ax.set_xticklabels(summary["backend"], rotation=18, ha="right")
    ax.set_title("Near-30 capability coverage", loc="left", pad=4, fontweight="bold")
    style_axes(ax)

    fig.subplots_adjust(left=0.14, right=0.985, top=0.90, bottom=0.24)
    path = FIGURES_ROOT / "capability_near30_sc.png"
    fig.savefig(path, dpi=600)
    plt.close(fig)

    print(path)
    for _, row in summary.iterrows():
        failed = ",".join(row["failed"]) if row["failed"] else "-"
        print(f"{row['backend']}: {row['solved']}/{row['total']} failed={failed}")
    print(f"ZXH/cuQuantum speedup: {cu_over_zxh:.6f}x common={cu_common}")
    print(f"ZXH/cuQuantum speedup excluding GHZ: {cu_over_zxh_no_ghz:.6f}x common={cu_common_no_ghz}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
