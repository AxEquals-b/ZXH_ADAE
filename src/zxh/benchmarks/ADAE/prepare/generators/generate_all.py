#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from mqt_workflow.analyze import run_analyze
from mqt_workflow.canonicalize import run_canonicalize
from mqt_workflow.filter import run_filter
from mqt_workflow.scan import run_scan
from mqt_workflow.sweep import run_sweep


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="可复现地生成、筛选、canonicalize 并分析 MQT Bench workload。"
    )
    parser.add_argument("--n-min", type=int, default=20, help="扫描范围下界，默认 20。")
    parser.add_argument("--n-max", type=int, default=32, help="扫描范围上界，默认 32。")
    parser.add_argument("--opt-level", type=int, choices=range(4), default=2, help="INDEP 生成时的 opt_level。")
    parser.add_argument(
        "--representative-max-n",
        type=int,
        default=30,
        help="29 个 representative family 的生成规模上限。默认 30。",
    )
    parser.add_argument(
        "--dev-max-n",
        type=int,
        default=24,
        help="开发期快速检查点的生成规模上限。默认 24。",
    )
    parser.add_argument(
        "--gate-count-budget",
        type=int,
        default=1_000_000,
        help="pass2 使用估计 gate count 做初筛时的阈值。默认 1000000。",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help="输出根目录。默认写到 benchmarks/ADAE/results/prepare/workflow/。",
    )
    parser.add_argument(
        "--no-size-cache",
        action="store_true",
        help="不要使用仓库内已有的 20..32 valid-size cache，改为现场探测。",
    )
    parser.add_argument(
        "--count-max-definition-depth",
        type=int,
        default=32,
        help="pass2 递归展开 instruction definition 的最大深度。默认 32。",
    )
    parser.add_argument(
        "--skip-sweep",
        action="store_true",
        help="跳过 pass5 的 representative-family sweep 生成。",
    )
    parser.add_argument(
        "--zxh-backend",
        choices=["cuda"],
        default="cuda",
        help="pass4 analyze 使用的 staged ZXH backend。当前固定为 cuda。",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    output_root = args.output_root
    if output_root is not None and not output_root.is_absolute():
        output_root = (_repo_root() / output_root).resolve()

    # Pass 1: scan all families, keep those with valid instances in 20..32,
    # pick the largest valid instance, and materialize one representative case per family.
    scan_result = run_scan(
        output_dir=(None if output_root is None else output_root / "01_pass1_scan"),
        n_min=args.n_min,
        n_max=args.n_max,
        opt_level=args.opt_level,
        use_known_size_cache=not args.no_size_cache,
    )

    # Pass 2: parse each QASM3 case once, estimate gate counts, apply the
    # static-circuit filter, and emit the retained-case manifest.
    filter_result = run_filter(
        pass1_json_path=_repo_root() / scan_result["json_path"],
        output_dir=(None if output_root is None else output_root / "02_pass2_filter"),
        gate_count_budget=args.gate_count_budget,
        max_definition_depth=args.count_max_definition_depth,
    )

    # Pass 3: materialize the retained representative circuits in both raw
    # and canonical QASM3 forms. This experiment-side canonical IR is shared
    # across analysis and all benchmark backends as the single normalized
    # circuit representation.
    canonicalize_result = run_canonicalize(
        selected_manifest_json_path=_repo_root() / filter_result["selected_json_path"],
        output_dir=(None if output_root is None else output_root / "03_pass3_canonicalize"),
        representative_max_n=args.representative_max_n,
        dev_max_n=args.dev_max_n,
    )

    # Pass 4: replay the canonical circuits through ZXH's analysis frontend
    # and extract structure metrics such as M, rho_X, rho_M, and rho_L.
    analyze_result = run_analyze(
        canonical_manifest_json_path=_repo_root() / canonicalize_result["canonical_manifest_json_path"],
        output_dir=(None if output_root is None else output_root / "04_pass4_analyze"),
        zxh_backend=args.zxh_backend,
    )

    sweep_result = None
    if not args.skip_sweep:
        sweep_result = run_sweep(
            representative_candidates_json_path=_repo_root() / analyze_result["representative_candidates_json_path"],
            output_dir=(None if output_root is None else output_root / "05_pass5_sweep"),
            n_min=args.n_min,
            n_max=args.n_max,
            opt_level=args.opt_level,
        )

    print("pass1=scan")
    print(f"output_dir={scan_result['output_dir']}")
    print(f"cases_dir={scan_result['cases_dir']}")
    print(f"json={scan_result['json_path']}")
    print(f"csv={scan_result['csv_path']}")
    print(f"md={scan_result['md_path']}")
    print()
    print("pass2=filter")
    print(f"output_dir={filter_result['output_dir']}")
    print(f"json={filter_result['json_path']}")
    print(f"csv={filter_result['csv_path']}")
    print(f"md={filter_result['md_path']}")
    print(f"selected_json={filter_result['selected_json_path']}")
    print(f"selected_csv={filter_result['selected_csv_path']}")
    print()
    print("pass3=canonicalize")
    print(f"output_dir={canonicalize_result['output_dir']}")
    print(f"json={canonicalize_result['json_path']}")
    print(f"csv={canonicalize_result['csv_path']}")
    print(f"md={canonicalize_result['md_path']}")
    print(f"raw_output_dir={canonicalize_result['raw_output_dir']}")
    print(f"canonical_output_dir={canonicalize_result['canonical_output_dir']}")
    print(f"canonical_manifest_json={canonicalize_result['canonical_manifest_json_path']}")
    print(f"canonical_manifest_csv={canonicalize_result['canonical_manifest_csv_path']}")
    print(f"dev_raw_output_dir={canonicalize_result['dev_raw_output_dir']}")
    print(f"dev_canonical_output_dir={canonicalize_result['dev_canonical_output_dir']}")
    print(f"dev_canonical_manifest_json={canonicalize_result['dev_canonical_manifest_json_path']}")
    print(f"dev_canonical_manifest_csv={canonicalize_result['dev_canonical_manifest_csv_path']}")
    print()
    print("pass4=analyze")
    print(f"output_dir={analyze_result['output_dir']}")
    print(f"json={analyze_result['json_path']}")
    print(f"csv={analyze_result['csv_path']}")
    print(f"md={analyze_result['md_path']}")
    print(f"zxh_backend={analyze_result['zxh_backend']}")
    print(f"zxh_stage_dir={analyze_result['zxh_stage_dir']}")
    print(f"representative_candidates_json={analyze_result['representative_candidates_json_path']}")
    print(f"representative_candidates_csv={analyze_result['representative_candidates_csv_path']}")
    if sweep_result is not None:
        print()
        print("pass5=sweep")
        print(f"output_dir={sweep_result['output_dir']}")
        print(f"json={sweep_result['json_path']}")
        print(f"csv={sweep_result['csv_path']}")
        print(f"md={sweep_result['md_path']}")
        print(f"raw_output_dir={sweep_result['raw_output_dir']}")
        print(f"canonical_output_dir={sweep_result['canonical_output_dir']}")
        print(f"sweep_manifest_json={sweep_result['sweep_manifest_json_path']}")
        print(f"sweep_manifest_csv={sweep_result['sweep_manifest_csv_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
