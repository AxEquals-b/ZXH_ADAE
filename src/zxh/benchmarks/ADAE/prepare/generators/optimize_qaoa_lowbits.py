#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
import math
import re
from dataclasses import dataclass
from pathlib import Path


QREG_RE = re.compile(r"^qreg\s+q\[(\d+)\]\s*;\s*$")
RZZ_RE = re.compile(r"^rzz\(([^)]+)\)\s+q\[(\d+)\],q\[(\d+)\]\s*;\s*$")


@dataclass
class QaoaGraph:
    n_qubits: int
    # undirected weighted adjacency
    w: list[list[int]]
    deg: list[int]
    total_weight: int


def parse_qaoa_rzz_graph(qasm_path: Path) -> QaoaGraph:
    n_qubits: int | None = None
    edges: list[tuple[int, int]] = []

    for raw in qasm_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("//"):
            continue

        if n_qubits is None:
            m_qreg = QREG_RE.match(line)
            if m_qreg:
                n_qubits = int(m_qreg.group(1))
                continue

        m_rzz = RZZ_RE.match(line)
        if not m_rzz:
            continue

        q0 = int(m_rzz.group(2))
        q1 = int(m_rzz.group(3))
        if q0 == q1:
            continue
        if q0 > q1:
            q0, q1 = q1, q0
        edges.append((q0, q1))

    if n_qubits is None:
        raise ValueError(f"未在 {qasm_path} 中找到 qreg q[N];")
    if not edges:
        raise ValueError(f"未在 {qasm_path} 中找到 rzz(...) 门。")

    w = [[0 for _ in range(n_qubits)] for _ in range(n_qubits)]
    for u, v in edges:
        w[u][v] += 1
        w[v][u] += 1

    deg = [sum(w[u]) for u in range(n_qubits)]
    total_weight = len(edges)
    return QaoaGraph(n_qubits=n_qubits, w=w, deg=deg, total_weight=total_weight)


def evaluate_subset_cut(graph: QaoaGraph, subset: tuple[int, ...]) -> int:
    # cross = sum_{u in S} deg(u) - 2 * sum_{u<v, u,v in S} w(u,v)
    deg_sum = 0
    for u in subset:
        deg_sum += graph.deg[u]

    intra = 0
    for i in range(len(subset)):
        u = subset[i]
        row = graph.w[u]
        for j in range(i + 1, len(subset)):
            intra += row[subset[j]]

    return deg_sum - 2 * intra


def find_best_lowbits_subset(graph: QaoaGraph, low_bits: int) -> tuple[tuple[int, ...], int, int]:
    n = graph.n_qubits
    if low_bits < 0 or low_bits > n:
        raise ValueError(f"low_bits={low_bits} 超出范围 [0, {n}]")

    total_comb = math.comb(n, low_bits)
    best_subset: tuple[int, ...] | None = None
    best_cut: int | None = None

    for subset in itertools.combinations(range(n), low_bits):
        cut = evaluate_subset_cut(graph, subset)
        if best_cut is None or cut < best_cut:
            best_cut = cut
            best_subset = subset

    assert best_subset is not None
    assert best_cut is not None

    isolated_weight = graph.total_weight - best_cut
    return best_subset, isolated_weight, total_comb


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "在 QAOA QASM 的 RZZ 加权图上，精确求解低位 qubit 选择，"
            "使 isolated 比例（同侧边占比）最大。"
        )
    )
    parser.add_argument("--qasm", type=Path, required=True, help="QAOA QASM 路径")
    parser.add_argument("--low-bits", type=int, default=8, help="低位 qubit 个数，默认 8")
    args = parser.parse_args()

    graph = parse_qaoa_rzz_graph(args.qasm)
    best_subset, isolated_weight, total_comb = find_best_lowbits_subset(graph, args.low_bits)
    ratio = isolated_weight / graph.total_weight

    print(f"qasm={args.qasm}")
    print(f"n_qubits={graph.n_qubits}")
    print(f"low_bits={args.low_bits}")
    print(f"rzz_total={graph.total_weight}")
    print(f"searched_combinations={total_comb}")
    print(f"best_low_qubits={list(best_subset)}")
    print(f"best_isolated={isolated_weight}")
    print(f"best_related={graph.total_weight - isolated_weight}")
    print(f"best_isolated_ratio={ratio:.6f}")


if __name__ == "__main__":
    main()
