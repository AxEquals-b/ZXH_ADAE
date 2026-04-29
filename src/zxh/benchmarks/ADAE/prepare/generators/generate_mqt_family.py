#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _import_mqt_bench():
    repo_root = _repo_root()
    local_src = repo_root / "workspace" / "external" / "mqt-bench" / "src"
    if local_src.is_dir():
        sys.path.insert(0, str(local_src))

    try:
        from mqt.bench import BenchmarkLevel, get_benchmark
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "无法导入 `mqt.bench`。请先确保本地副本存在于 "
            f"`{local_src}`，或在当前环境中安装 `mqt-bench`。"
        ) from exc

    return BenchmarkLevel, get_benchmark


def _import_qft_builder():
    try:
        from qiskit.synthesis.qft import synth_qft_full
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "生成 full QFT 需要 `qiskit.synthesis.qft.synth_qft_full`。"
        ) from exc
    return synth_qft_full


def _import_qasm2_dump():
    try:
        from qiskit.qasm2 import dump
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "导出 OpenQASM 2 需要 qiskit.qasm2。请先安装可用的 `qiskit`。"
        ) from exc
    return dump


def _default_output_dir(family: str) -> Path:
    return _repo_root() / "benchmarks" / "ADAE" / "results" / "prepare" / "generated_qasm" / "mqt_bench_indep" / family


def _resolve_path(path: Path) -> Path:
    if path.is_absolute():
        return path.resolve()
    return (Path.cwd() / path).resolve()


def _build_full_qft_no_swaps(num_qubits: int):
    synth_qft_full = _import_qft_builder()
    qc = synth_qft_full(num_qubits, do_swaps=False)
    qc.measure_all()
    return qc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="使用本地 MQT Bench 生成一个 benchmark family，并导出为 OpenQASM 2 文件。"
    )
    parser.add_argument("--family", required=True, help="MQT Bench benchmark 名称，例如 qft、qpeexact、ghz。")
    parser.add_argument("--n-min", type=int, required=True, help="family 的最小规模。")
    parser.add_argument("--n-max", type=int, required=True, help="family 的最大规模。")
    parser.add_argument("--step", type=int, default=1, help="规模步长，默认 1。")
    parser.add_argument(
        "--level",
        choices=["alg", "indep"],
        default="indep",
        help="MQT Bench abstraction level。默认 `indep`，用于避免保留类似 `qft` 这样的算法级复合门。",
    )
    parser.add_argument(
        "--opt-level",
        type=int,
        choices=range(4),
        default=2,
        help="MQT Bench transpile optimization level，默认 2。",
    )
    parser.add_argument(
        "--qft-full-no-swaps",
        action="store_true",
        help="仅对 `--family qft --level indep` 生效：直接生成 full QFT（保留全部 CP），且不包含末尾 SWAP。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="输出目录。默认写入 benchmarks/ADAE/results/prepare/generated_qasm/mqt_bench_indep/<family>/",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="若目标文件已存在，则覆盖写入。",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.n_min <= 0 or args.n_max <= 0:
        raise ValueError("`n-min` 和 `n-max` 都必须为正整数。")
    if args.n_min > args.n_max:
        raise ValueError("`n-min` 不能大于 `n-max`。")
    if args.step <= 0:
        raise ValueError("`step` 必须为正整数。")
    if args.qft_full_no_swaps:
        if args.family != "qft":
            raise ValueError("`--qft-full-no-swaps` 仅支持 `--family qft`。")
        if args.level != "indep":
            raise ValueError("`--qft-full-no-swaps` 仅支持 `--level indep`。")

    BenchmarkLevel, get_benchmark = _import_mqt_bench()
    dump_qasm2 = _import_qasm2_dump()
    level = BenchmarkLevel.INDEP if args.level == "indep" else BenchmarkLevel.ALG

    output_dir = _resolve_path(args.output_dir) if args.output_dir is not None else _default_output_dir(args.family)
    output_dir.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []
    for n in range(args.n_min, args.n_max + 1, args.step):
        if args.qft_full_no_swaps:
            qc = _build_full_qft_no_swaps(n)
        else:
            qc = get_benchmark(args.family, level, n, opt_level=args.opt_level)
        out_path = output_dir / f"{args.family}_n{n}.qasm"
        if out_path.exists() and not args.overwrite:
            raise FileExistsError(
                f"目标文件已存在：{out_path}。若要覆盖，请添加 `--overwrite`。"
            )
        with out_path.open("w", encoding="utf-8") as f:
            dump_qasm2(qc, f)
        generated.append(out_path)

    print(f"family={args.family}")
    print(f"level={level.name}")
    print(f"generator={'full_qft_no_swaps' if args.qft_full_no_swaps else 'mqt_bench'}")
    print(f"opt_level={args.opt_level}")
    print(f"range=[{args.n_min}, {args.n_max}], step={args.step}")
    print(f"output_dir={output_dir}")
    print(f"generated={len(generated)}")
    repo_root = _repo_root()
    for path in generated:
        try:
            print(path.relative_to(repo_root))
        except ValueError:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
