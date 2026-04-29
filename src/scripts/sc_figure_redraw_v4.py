#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import re
import ctypes
import ctypes.util
import os
import subprocess
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.ticker import FixedLocator, FuncFormatter, LogLocator, MultipleLocator, NullFormatter

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULTS_ROOT = PROJECT_ROOT / "output" / "results"
FIGURES_ROOT = PROJECT_ROOT / "output" / "figures"
ZXH_RUN_ID = os.environ.get("ZXH_RUN_ID", "latest")
BASELINE_RUN_ID = os.environ.get("BASELINE_RUN_ID", "latest")
P_BATCH_RUN_ID = os.environ.get("P_BATCH_RUN_ID", ZXH_RUN_ID)

FAMILIES = ["bv", "qft", "qwalk", "vqe_two_local"]
REPRESENTATIVE_BACKENDS = [
    ("cuQuantum", BASELINE_RUN_ID, "cuQuantum", "cuQuantum"),
    ("ddsim", BASELINE_RUN_ID, "ddsim", "DDSIM"),
    ("qblaze", BASELINE_RUN_ID, "qblaze", "qblaze"),
    ("zxh", ZXH_RUN_ID, "zxh", "ZXH-Sim"),
]
P_BATCH_PATH = RESULTS_ROOT / "zxh" / P_BATCH_RUN_ID / "p_batch.csv"
PATTERN_REPEATS = 4
DIAG_IR_WORD_CAP = 6144
COMPLEX_BYTES = 8
READ_WRITE_FACTOR = 2
LOCAL_A100_PCIE_40GB_HBM_PEAK_GIB_S = 1555.0 * 1e9 / (1024**3)
CUDA_ATTR_MEMORY_CLOCK_RATE = 36
CUDA_ATTR_GLOBAL_MEMORY_BUS_WIDTH = 37
KNOWN_GPU_BUS_WIDTH_BITS = {
    "A100": 5120,
}

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

gate_style = {
    "p-low": {"label": "p-low", "color": "#1f77b4", "marker": "o", "linestyle": "-"},
    "p-high": {"label": "p-high", "color": "#56B4E9", "marker": "s", "linestyle": "-"},
    "cp-hh": {"label": "cp-hh", "color": "#2ca02c", "marker": "D", "linestyle": "--"},
    "cp-hl": {"label": "cp-hl", "color": "#E69F00", "marker": "^", "linestyle": "-."},
    "cp-ll": {"label": "cp-ll", "color": "#D62728", "marker": "v", "linestyle": ":"},
}
backend_style = {
    "cuQuantum": {"color": "#1f77b4", "marker": "o", "linestyle": "-", "label": "cuQuantum", "lw": 1.85, "alpha": 0.95},
    "DDSIM": {"color": "#7a7a7a", "marker": "s", "linestyle": "--", "label": "DDSIM", "lw": 1.8, "alpha": 0.95},
    "qblaze": {"color": "#2ca02c", "marker": "^", "linestyle": "-.", "label": "qblaze", "lw": 1.85, "alpha": 0.95},
    "ZXH-Sim": {"color": "#D62728", "marker": "D", "linestyle": "-", "label": "ZXH-Sim", "lw": 2.25, "alpha": 1.00},
}
titles = {"bv": "(a) BV", "qft": "(b) QFT", "qwalk": "(c) QWalk", "vqe_two_local": "(d) VQE-2-Local"}
ann = {
    "bv": r"$N^{*}=30,\ M=14$" "\n" r"$\rho_M=0.467,\ \rho_X=0.023,\ \rho_L=0.143$",
    "qft": r"$N^{*}=30,\ M=30$" "\n" r"$\rho_M=1.000,\ \rho_X=0.000,\ \rho_L=0.052$",
    "qwalk": r"$N^{*}=30,\ M=30$" "\n" r"$\rho_M=1.000,\ \rho_X=0.486,\ \rho_L=0.996$",
    "vqe_two_local": r"$N^{*}=30,\ M=30$" "\n" r"$\rho_M=1.000,\ \rho_X=0.916,\ \rho_L=0.767$",
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


def parse_n(circuit: str) -> int:
    match = re.search(r"_n(\d+)$", circuit)
    if not match:
        raise ValueError(f"cannot parse N from circuit name: {circuit}")
    return int(match.group(1))


def load_result_rows(backend_dir: str, run_id: str, family: str, backend: str, backend_label: str) -> list[dict[str, object]]:
    path = RESULTS_ROOT / backend_dir / run_id / f"{family}.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    rows: list[dict[str, object]] = []
    df = pd.read_csv(path)
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


def build_representative_sweeps() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for backend_dir, run_id, backend, backend_label in REPRESENTATIVE_BACKENDS:
        for family in FAMILIES:
            rows.extend(load_result_rows(backend_dir, run_id, family, backend, backend_label))
    return pd.DataFrame(rows).sort_values(["family", "backend", "N"])


def expected_chunk_count(gate_kind: str, batch_size: int) -> int:
    words_per_gate = 2 if gate_kind.startswith("p-") else 3
    return max(1, math.ceil(batch_size * words_per_gate / DIAG_IR_WORD_CAP))


def peak_bandwidth_from_clock_bus_gib_s(memory_clock_khz: int, memory_bus_width_bits: int) -> float | None:
    if memory_clock_khz <= 0 or memory_bus_width_bits <= 0:
        return None
    bytes_per_second = 2.0 * float(memory_clock_khz) * 1000.0 * (float(memory_bus_width_bits) / 8.0)
    return bytes_per_second / (1024**3)


def query_hbm_peak_bandwidth_gib_s() -> tuple[float, str]:
    for name in filter(None, [ctypes.util.find_library("cudart"), "libcudart.so", "libcudart.so.12", "libcudart.so.11.0"]):
        try:
            cudart = ctypes.CDLL(name)
            device = ctypes.c_int(0)
            if cudart.cudaGetDevice(ctypes.byref(device)) != 0:
                device = ctypes.c_int(0)
            clock = ctypes.c_int(0)
            bus = ctypes.c_int(0)
            err_clock = cudart.cudaDeviceGetAttribute(ctypes.byref(clock), CUDA_ATTR_MEMORY_CLOCK_RATE, device.value)
            err_bus = cudart.cudaDeviceGetAttribute(ctypes.byref(bus), CUDA_ATTR_GLOBAL_MEMORY_BUS_WIDTH, device.value)
            if err_clock == 0 and err_bus == 0:
                peak = peak_bandwidth_from_clock_bus_gib_s(clock.value, bus.value)
                if peak is not None:
                    return peak, "CUDA runtime"
        except Exception:
            pass

    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,clocks.max.memory",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )
        first_line = next((line.strip() for line in output.splitlines() if line.strip()), "")
        if first_line:
            gpu_name, clock_mhz = [part.strip() for part in first_line.rsplit(",", 1)]
            bus_width = next((bits for key, bits in KNOWN_GPU_BUS_WIDTH_BITS.items() if key in gpu_name), 0)
            peak = peak_bandwidth_from_clock_bus_gib_s(int(float(clock_mhz) * 1000.0), bus_width)
            if peak is not None:
                return peak, f"nvidia-smi + known {gpu_name} bus width"
    except Exception:
        pass

    return LOCAL_A100_PCIE_40GB_HBM_PEAK_GIB_S, "fixed A100-PCIE-40GB spec"


def build_kernel_data() -> pd.DataFrame:
    if not P_BATCH_PATH.is_file():
        raise FileNotFoundError(P_BATCH_PATH)
    df = pd.read_csv(P_BATCH_PATH)
    parsed: list[dict[str, object]] = []
    empty_ms: float | None = None
    pattern = re.compile(r"p_batch_n(?P<n>\d+)_(?P<kind>empty|p-low|p-high|cp-hh|cp-hl|cp-ll)_b(?P<batch>\d+)$")
    for _, row in df.iterrows():
        match = pattern.match(str(row["circuit"]))
        if not match or str(row["status"]) != "pass":
            continue
        avg_s = mean_after_warmup(parse_times(row["times"]))
        if avg_s is None:
            continue
        avg_ms = avg_s * 1000.0
        gate_kind = match.group("kind")
        batch_size = int(match.group("batch"))
        if gate_kind == "empty":
            empty_ms = avg_ms
            continue
        parsed.append({"gate_kind": gate_kind, "batch_size": batch_size, "full_ms": avg_ms})
    if empty_ms is None:
        raise RuntimeError(f"empty baseline missing in {P_BATCH_PATH}")

    chunk_bytes = (1 << 30) * COMPLEX_BYTES * READ_WRITE_FACTOR
    rows: list[dict[str, object]] = []
    for item in parsed:
        gate_kind = str(item["gate_kind"])
        batch_size = int(item["batch_size"])
        diag_total_ms = max(0.0, float(item["full_ms"]) - empty_ms)
        diag_ms = diag_total_ms / PATTERN_REPEATS
        chunks = expected_chunk_count(gate_kind, batch_size)
        if batch_size <= 0 or diag_ms <= 0.0:
            continue
        rows.append({
            "gate_kind": gate_kind,
            "batch_size": batch_size,
            "diag_ir_word_cap": DIAG_IR_WORD_CAP,
            "expected_chunk_count": chunks,
            "time_per_diagonal_gate_us": diag_ms * 1000.0 / batch_size,
            "effective_bandwidth_gib_s": (chunk_bytes * chunks / (diag_ms / 1000.0)) / (1024**3),
            "diag_execute_ms_mean": diag_ms,
        })
    return pd.DataFrame(rows).sort_values(["gate_kind", "batch_size"])


def style_axes(ax, *, ylog: bool = False) -> None:
    ax.set_facecolor("white")
    ax.grid(True, axis="both", which="major", color="#d2d2d2", linewidth=0.65, alpha=0.85)
    if ylog:
        ax.grid(True, axis="y", which="minor", color="#ebebeb", linewidth=0.45, alpha=0.85)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_linewidth(0.8)
        ax.spines[spine].set_color("#666666")


def batch_fmt(x, pos):
    vals = {1: "1", 2: "2", 4: "4", 8: "8", 16: "16", 32: "32", 64: "64", 128: "128", 256: "256", 1024: "1K", 4096: "4K"}
    xr = int(round(x))
    return vals.get(xr, "") if abs(x - xr) < 1e-8 else ""


def fmt_timeout_ns(ns: list[int]) -> str:
    ns = sorted(int(n) for n in ns)
    if not ns:
        return ""
    if len(ns) == 1:
        return str(ns[0])
    if ns == list(range(ns[0], ns[-1] + 1)):
        return f"{ns[0]}–{ns[-1]}"
    return ",".join(str(n) for n in ns)


def timeout_notes(sweeps: pd.DataFrame, family: str) -> list[str]:
    notes = []
    for label, short in [("ZXH-Sim", "ZXH"), ("cuQuantum", "cuQ"), ("qblaze", "qblaze"), ("DDSIM", "DDSIM")]:
        ns = sweeps[(sweeps.family == family) & (sweeps.backend_label == label) & (sweeps.status != "pass")]["N"].tolist()
        if ns:
            notes.append(f"{short} TO @{fmt_timeout_ns(ns)}")
    return notes


def plot_kernel(kdf: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(7.05, 2.55), dpi=300)
    max_batch = int(kdf["batch_size"].max())
    hbm_peak_gib_s, hbm_peak_source = query_hbm_peak_bandwidth_gib_s()

    for ax, metric, ttl in zip(
        axes,
        ["time_per_diagonal_gate_us", "effective_bandwidth_gib_s"],
        ["(a) Time per diagonal gate", "(b) Effective bandwidth"],
    ):
        for gate in ["p-low", "p-high", "cp-hh", "cp-hl", "cp-ll"]:
            sub = kdf[kdf["gate_kind"] == gate].sort_values("batch_size")
            if sub.empty:
                continue
            st = gate_style[gate]
            ax.plot(sub["batch_size"], sub[metric], color=st["color"], marker=st["marker"], linestyle=st["linestyle"], linewidth=1.95, markersize=4.4, markerfacecolor=st["color"], markeredgecolor=st["color"], label=st["label"], zorder=3)
        ax.set_xscale("log", base=2)
        ticks = [tick for tick in [1, 2, 4, 8, 16, 32, 64, 128, 256, 1024, 4096] if tick <= max_batch]
        ax.xaxis.set_major_locator(FixedLocator(ticks))
        ax.xaxis.set_major_formatter(FuncFormatter(batch_fmt))
        ax.set_xlabel("Diagonal batch size")
        ax.set_title(ttl, loc="left", pad=3, fontweight="bold")
        style_axes(ax, ylog=(metric == "effective_bandwidth_gib_s"))

    axes[0].set_ylabel("Time per gate ($\\mu$s)")
    axes[0].yaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{int(x):,}" if x >= 1000 else f"{int(x)}"))

    axes[1].set_ylabel("Bandwidth (GiB/s)")
    axes[1].set_yscale("log")
    axes[1].axhline(hbm_peak_gib_s, color="#444444", linestyle=(0, (4, 2)), linewidth=1.05, zorder=1)
    axes[1].yaxis.set_major_locator(LogLocator(base=10, numticks=5))
    axes[1].yaxis.set_minor_locator(LogLocator(base=10, subs=np.arange(2, 10) * 0.1, numticks=12))
    axes[1].yaxis.set_minor_formatter(NullFormatter())

    handles = [Line2D([0], [0], color=gate_style[g]["color"], marker=gate_style[g]["marker"], linestyle=gate_style[g]["linestyle"], linewidth=1.95, markersize=4.8, label=gate_style[g]["label"]) for g in ["p-low", "p-high", "cp-hh", "cp-hl", "cp-ll"]]
    handles.append(Line2D([0], [0], color="#444444", linestyle=(0, (4, 2)), linewidth=1.05, label=f"HBM peak ({hbm_peak_gib_s:.0f} GiB/s)"))
    fig.legend(handles=handles, ncol=6, loc="upper center", bbox_to_anchor=(0.5, 1.01), frameon=False, handlelength=2.1, columnspacing=0.8, handletextpad=0.42)
    fig.subplots_adjust(top=0.78, left=0.09, right=0.995, bottom=0.21, wspace=0.22)
    path = FIGURES_ROOT / "kernel_diag_batch_sc_v4.png"
    fig.savefig(path, dpi=600)
    plt.close(fig)
    print(f"HBM peak roofline: {hbm_peak_gib_s:.3f} GiB/s ({hbm_peak_source})")
    return path


def plot_representative(sweeps: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(2, 2, figsize=(7.05, 5.0), dpi=300)
    axes = axes.ravel()
    for i, (ax, family) in enumerate(zip(axes, FAMILIES)):
        subfam = sweeps[sweeps["family"] == family].copy()
        ax.axvline(30, color="#b0b0b0", linestyle=(0, (2, 3)), linewidth=0.85, zorder=1)
        for backend in ["cuQuantum", "DDSIM", "qblaze", "ZXH-Sim"]:
            sub = subfam[(subfam["backend_label"] == backend) & (subfam["status"] == "pass")].sort_values("N")
            if len(sub):
                st = backend_style[backend]
                ax.plot(sub["N"], sub["end_to_end_ms"], color=st["color"], marker=st["marker"], linestyle=st["linestyle"], linewidth=st["lw"], markersize=4.6 if backend != "ZXH-Sim" else 4.9, alpha=st["alpha"], label=st["label"], zorder=3 if backend == "ZXH-Sim" else 2)
        ax.set_yscale("log")
        ax.set_title(titles[family], loc="left", pad=4, fontweight="bold")
        ax.set_xlim(19.5, 31.5)
        ax.xaxis.set_major_locator(MultipleLocator(2))
        ax.xaxis.set_minor_locator(MultipleLocator(1))
        style_axes(ax, ylog=True)
        yvals = subfam[(subfam["status"] == "pass") & np.isfinite(subfam["end_to_end_ms"])]["end_to_end_ms"]
        if len(yvals):
            ymin = max(10 ** np.floor(np.log10(yvals.min() * 0.75)), yvals.min() * 0.70)
            ymax = 10 ** np.ceil(np.log10(yvals.max() * 1.28))
            ax.set_ylim(ymin, ymax)
        ax.text(0.03, 0.965, ann[family], transform=ax.transAxes, va="top", ha="left", fontsize=8.0, color="#333333", bbox=dict(boxstyle="round,pad=0.16", facecolor="#f8f8f8", edgecolor="#b8b8b8", linewidth=0.68))
        notes = timeout_notes(sweeps, family)
        if notes:
            ax.text(0.97, 0.965, "\n".join(notes), transform=ax.transAxes, va="top", ha="right", fontsize=7.1, color="#555555", bbox=dict(boxstyle="round,pad=0.14", facecolor="white", edgecolor="#d0d0d0", linewidth=0.55, alpha=0.94))
        ax.set_xlabel("" if i < 2 else "Qubits")
        ax.set_ylabel("End-to-end time (ms)" if i % 2 == 0 else "")

    handles = [Line2D([0], [0], color=backend_style[b]["color"], marker=backend_style[b]["marker"], linestyle=backend_style[b]["linestyle"], linewidth=backend_style[b]["lw"], markersize=4.8 if b != "ZXH-Sim" else 5.0, label=backend_style[b]["label"]) for b in ["cuQuantum", "DDSIM", "qblaze", "ZXH-Sim"]]
    fig.legend(handles=handles, ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.01), frameon=False, handlelength=2.1, columnspacing=1.2, handletextpad=0.45)
    fig.subplots_adjust(top=0.87, left=0.10, right=0.995, bottom=0.09, wspace=0.22, hspace=0.27)
    path = FIGURES_ROOT / "representative_families_sc_v4.png"
    fig.savefig(path, dpi=600)
    plt.close(fig)
    return path


def main() -> int:
    FIGURES_ROOT.mkdir(parents=True, exist_ok=True)
    kernel = build_kernel_data()
    sweeps = build_representative_sweeps()
    paths = [plot_kernel(kernel), plot_representative(sweeps)]
    for path in paths:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
