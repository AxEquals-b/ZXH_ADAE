#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = PROJECT_ROOT / "output" / "results"
FIGURES_ROOT = PROJECT_ROOT / "output" / "figures"
FAMILIES = ["bv", "qft", "qwalk", "vqe_two_local"]
ZXH_RUN_ID = os.environ.get("ZXH_RUN_ID", "latest")
ABLATION_RUN_ID = os.environ.get("ABLATION_RUN_ID", "latest")

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

titles = {"bv": "(a) BV", "qft": "(b) QFT", "qwalk": "(c) QWalk", "vqe_two_local": "(d) VQE-2-Local"}
ann = {
    "bv": r"$N^{*}=30,\ M=14$" "\n" r"$\rho_M=0.467,\ \rho_X=0.023,\ \rho_L=0.143$",
    "qft": r"$N^{*}=30,\ M=30$" "\n" r"$\rho_M=1.000,\ \rho_X=0.000,\ \rho_L=0.052$",
    "qwalk": r"$N^{*}=30,\ M=30$" "\n" r"$\rho_M=1.000,\ \rho_X=0.486,\ \rho_L=0.996$",
    "vqe_two_local": r"$N^{*}=30,\ M=30$" "\n" r"$\rho_M=1.000,\ \rho_X=0.916,\ \rho_L=0.767$",
}
backend_style = {"ZXH-Sim": {"color": "#D62728", "marker": "D", "linestyle": "-", "label": "ZXH-Sim", "lw": 2.25, "alpha": 1.00}}
abl_styles = {
    "disable_x": dict(color="#4E79A7", marker="s", linestyle="--", lw=1.8, ms=4.4, mec="#4E79A7", mfc="white", mew=1.0, alpha=0.95),
    "eager_expand_all": dict(color="#4D4D4D", marker="o", linestyle=":", lw=2.0, ms=4.4, mec="#4D4D4D", mfc="white", mew=1.0, alpha=0.95),
}
abl_labels = {"disable_x": "no-X", "eager_expand_all": "eager expand-all"}


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


def parse_n(circuit: str) -> int:
    match = re.search(r"_n(\d+)$", circuit)
    if not match:
        raise ValueError(f"cannot parse N from circuit name: {circuit}")
    return int(match.group(1))


def load_backend(backend_dir: str, run_id: str, family: str, backend: str, backend_label: str) -> list[dict[str, object]]:
    path = RESULTS_ROOT / backend_dir / run_id / f"{family}.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    df = pd.read_csv(path)
    rows: list[dict[str, object]] = []
    for _, row in df.iterrows():
        status = str(row["status"])
        circuit = str(row["circuit"])
        n = parse_n(circuit)
        end_to_end_ms = math.nan
        sample_ms = math.nan
        execute_ms = math.nan
        if status == "pass":
            end_to_end = mean_after_warmup(parse_times(row.get("times", "")))
            sample = mean_after_warmup(parse_times(row.get("sample_time", "")))
            if end_to_end is not None:
                end_to_end_ms = end_to_end * 1000.0
                if sample is not None:
                    sample_ms = sample * 1000.0
                    execute_ms = max(0.0, end_to_end_ms - sample_ms)
                else:
                    sample_ms = 0.0
                    execute_ms = end_to_end_ms
        rows.append({
            "family": family,
            "N": n,
            "backend": backend,
            "backend_label": backend_label,
            "status": status,
            "end_to_end_ms": end_to_end_ms,
            "execute_ms": execute_ms,
            "sample_ms": sample_ms,
            "source_run": f"{backend_dir}/{run_id}",
        })
    return rows


def build_tables() -> tuple[pd.DataFrame, pd.DataFrame]:
    rep_rows: list[dict[str, object]] = []
    ab_rows: list[dict[str, object]] = []
    for family in FAMILIES:
        rep_rows.extend(load_backend("zxh", ZXH_RUN_ID, family, "baseline", "ZXH baseline"))
        ab_rows.extend(load_backend("zxh-nox", ABLATION_RUN_ID, family, "disable_x", "ZXH disable_x"))
        ab_rows.extend(load_backend("zxh-exp", ABLATION_RUN_ID, family, "eager_expand_all", "ZXH eager_expand_all"))
    return pd.DataFrame(rep_rows), pd.DataFrame(ab_rows)


def style_axes(ax) -> None:
    ax.set_facecolor("white")
    ax.grid(True, axis="both", which="major", color="#d2d2d2", linewidth=0.65, alpha=0.85)
    ax.grid(True, axis="y", which="minor", color="#ebebeb", linewidth=0.45, alpha=0.85)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_linewidth(0.8)
        ax.spines[spine].set_color("#666666")


def ylims_for(rep: pd.DataFrame, ab: pd.DataFrame, family: str) -> tuple[float, float]:
    yvals = pd.concat([
        rep[(rep.family == family) & (rep.status == "pass")]["end_to_end_ms"],
        ab[(ab.family == family) & (ab.status == "pass")]["end_to_end_ms"],
    ])
    yvals = yvals[np.isfinite(yvals)]
    ymin = max(10 ** np.floor(np.log10(yvals.min() * 0.75)), yvals.min() * 0.70)
    ymax = 10 ** np.ceil(np.log10(yvals.max() * 1.28))
    return ymin, ymax


def fmt_timeout_ns(ns: list[int]) -> str:
    ns = sorted(int(n) for n in ns)
    if not ns:
        return ""
    if len(ns) == 1:
        return str(ns[0])
    if ns == list(range(ns[0], ns[-1] + 1)):
        return f"{ns[0]}–{ns[-1]}"
    return ",".join(str(n) for n in ns)


def collect_timeout_notes(rep: pd.DataFrame, ab: pd.DataFrame, family: str) -> list[str]:
    notes = []
    rep_ns = rep[(rep.family == family) & (rep.status != "pass")]["N"].tolist()
    if rep_ns:
        notes.append(f"ZXH TO @{fmt_timeout_ns(rep_ns)}")
    for key, label in [("disable_x", "no-X"), ("eager_expand_all", "eager")]:
        ab_ns = ab[(ab.family == family) & (ab.backend == key) & (ab.status != "pass")]["N"].tolist()
        if ab_ns:
            notes.append(f"{label} TO @{fmt_timeout_ns(ab_ns)}")
    return notes


def ratio_notes(rep: pd.DataFrame, ab: pd.DataFrame, family: str) -> list[str]:
    base_rep = rep[(rep.family == family) & (rep.N == 30) & (rep.status == "pass")]
    if base_rep.empty:
        return []
    base = float(base_rep.iloc[0]["end_to_end_ms"])
    notes = []
    for key in ["disable_x", "eager_expand_all"]:
        row = ab[(ab.family == family) & (ab.backend == key) & (ab.N == 30) & (ab.status == "pass")]
        if row.empty:
            continue
        ratio = float(row.iloc[0]["end_to_end_ms"]) / base
        if ratio >= 1.15:
            label = "no-X" if key == "disable_x" else "eager"
            notes.append(f"{label}@30 +{ratio:.2f}x")
    return notes


def main() -> int:
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)
    rep, ab = build_tables()
    fig, axes = plt.subplots(2, 2, figsize=(7.05, 5.0), dpi=300)
    axes = axes.ravel()
    for i, (ax, family) in enumerate(zip(axes, FAMILIES)):
        sub_rep = rep[(rep.family == family) & (rep.status == "pass")].sort_values("N")
        ax.axvline(30, color="#b0b0b0", linestyle=(0, (2, 3)), linewidth=0.85, zorder=1)
        st = backend_style["ZXH-Sim"]
        ax.plot(sub_rep["N"], sub_rep["end_to_end_ms"], color=st["color"], marker=st["marker"], linestyle=st["linestyle"], linewidth=st["lw"], markersize=4.9, alpha=st["alpha"], label=st["label"], zorder=3)
        for key in ["disable_x", "eager_expand_all"]:
            sub_ab = ab[(ab.family == family) & (ab.backend == key) & (ab.status == "pass")].sort_values("N")
            if sub_ab.empty:
                continue
            sty = abl_styles[key]
            ax.plot(sub_ab["N"], sub_ab["end_to_end_ms"], color=sty["color"], marker=sty["marker"], linestyle=sty["linestyle"], linewidth=sty["lw"], markersize=sty["ms"], markeredgecolor=sty["mec"], markerfacecolor=sty["mfc"], markeredgewidth=sty["mew"], alpha=sty["alpha"], zorder=4)
        ax.set_yscale("log")
        ax.set_title(titles[family], loc="left", pad=4, fontweight="bold")
        ax.set_xlim(19.5, 31.5)
        ax.xaxis.set_major_locator(MultipleLocator(2))
        ax.xaxis.set_minor_locator(MultipleLocator(1))
        style_axes(ax)
        ax.set_ylim(*ylims_for(rep, ab, family))
        ax.text(0.03, 0.965, ann[family], transform=ax.transAxes, va="top", ha="left", fontsize=8.0, color="#333333", bbox=dict(boxstyle="round,pad=0.16", facecolor="#f8f8f8", edgecolor="#b8b8b8", linewidth=0.68))
        notes = collect_timeout_notes(rep, ab, family) + ratio_notes(rep, ab, family)
        if notes:
            ax.text(0.97, 0.965, "\n".join(notes), transform=ax.transAxes, va="top", ha="right", fontsize=7.1, color="#555555", bbox=dict(boxstyle="round,pad=0.14", facecolor="white", edgecolor="#d0d0d0", linewidth=0.55, alpha=0.94))
        ax.set_xlabel("" if i < 2 else "Qubits")
        ax.set_ylabel("End-to-end time (ms)" if i % 2 == 0 else "")

    handles = [
        Line2D([0], [0], color=backend_style["ZXH-Sim"]["color"], marker=backend_style["ZXH-Sim"]["marker"], linestyle=backend_style["ZXH-Sim"]["linestyle"], linewidth=backend_style["ZXH-Sim"]["lw"], markersize=5.0, label="ZXH-Sim"),
        Line2D([0], [0], color=abl_styles["disable_x"]["color"], marker=abl_styles["disable_x"]["marker"], linestyle=abl_styles["disable_x"]["linestyle"], linewidth=abl_styles["disable_x"]["lw"], markerfacecolor="white", markeredgecolor=abl_styles["disable_x"]["mec"], markeredgewidth=abl_styles["disable_x"]["mew"], markersize=4.8, label=abl_labels["disable_x"]),
        Line2D([0], [0], color=abl_styles["eager_expand_all"]["color"], marker=abl_styles["eager_expand_all"]["marker"], linestyle=abl_styles["eager_expand_all"]["linestyle"], linewidth=abl_styles["eager_expand_all"]["lw"], markerfacecolor="white", markeredgecolor=abl_styles["eager_expand_all"]["mec"], markeredgewidth=abl_styles["eager_expand_all"]["mew"], markersize=4.8, label=abl_labels["eager_expand_all"]),
    ]
    fig.legend(handles=handles, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.01), frameon=False, handlelength=1.8, columnspacing=1.2, handletextpad=0.45)
    fig.subplots_adjust(top=0.87, left=0.10, right=0.995, bottom=0.09, wspace=0.22, hspace=0.27)
    path = FIGURES_ROOT / "representative_families_ablation_sameframe_sc.png"
    fig.savefig(path, dpi=600)
    plt.close(fig)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
