#!/usr/bin/env python3
from __future__ import annotations

import csv
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[1]
SUITES_ROOT = SRC_ROOT / "suites"

SUITE_CSVS: dict[str, Path] = {
    "near30": SUITES_ROOT / "near30.csv",
    "qwalk_sweep": SUITES_ROOT / "qwalk_sweep.csv",
    "qft_sweep": SUITES_ROOT / "qft_sweep.csv",
    "bv_sweep": SUITES_ROOT / "bv_sweep.csv",
    "vqe_two_local_sweep": SUITES_ROOT / "vqe_two_local_sweep.csv",
}

SWEEP_FAMILY_TO_SUITE: dict[str, str] = {
    "qwalk": "qwalk_sweep",
    "qft": "qft_sweep",
    "bv": "bv_sweep",
    "vqe_two_local": "vqe_two_local_sweep",
}


def all_suites() -> list[str]:
    return list(SUITE_CSVS)


def suite_csv_path(suite_name: str) -> Path:
    try:
        return SUITE_CSVS[suite_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported suite: {suite_name}. supported={all_suites()}") from exc


def circuit_stem(family: str, num_qubits: int) -> str:
    return f"{family}_n{num_qubits}"


def load_suite_cases(suite_name: str) -> list[dict[str, str]]:
    path = suite_csv_path(suite_name)
    with path.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise RuntimeError(f"No rows found in suite CSV: {path}")

    cases: list[dict[str, str]] = []
    for row in rows:
        family = str(row["family"])
        num_qubits = int(row["selected_n"])
        cases.append(
            {
                "circuit": circuit_stem(family, num_qubits),
                "family": family,
                "N": str(num_qubits),
            }
        )
    return cases


def all_sweep_families() -> list[str]:
    return list(SWEEP_FAMILY_TO_SUITE)


def sweep_suite_name(family: str) -> str:
    try:
        return SWEEP_FAMILY_TO_SUITE[family]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported sweep family: {family}. supported={all_sweep_families()}"
        ) from exc
