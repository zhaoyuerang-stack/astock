"""CLI wrapper for the canonical workflow Nine-Gate runner.

The reusable implementation lives in ``workflow.nine_gate_runner`` so workflow
code never imports from ``scripts.research``.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from workflow import nine_gate_runner as _runner

TrialCountUnknown = _runner.TrialCountUnknown
VERSION_OVERRIDES = _runner.VERSION_OVERRIDES


def _family_n_trials(*args, **kwargs):
    return _runner._family_n_trials(*args, **kwargs)


def _load_spec_from_registry(*args, **kwargs):
    return _runner._load_spec_from_registry(*args, **kwargs)


def audit_stale_registered(*args, **kwargs):
    return _runner.audit_stale_registered(*args, **kwargs)


def record_nine_gate_research_run(*args, **kwargs):
    return _runner.record_nine_gate_research_run(*args, **kwargs)


def run_evaluation(*args, **kwargs):
    original = _runner._family_n_trials
    _runner._family_n_trials = _family_n_trials
    try:
        return _runner.run_evaluation(*args, **kwargs)
    finally:
        _runner._family_n_trials = original


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run 9-Gate Strategy Evaluator")
    parser.add_argument("--strategy", help="Strategy name to run evaluation on")
    parser.add_argument(
        "--audit-stale",
        action="store_true",
        help="自动补审:扫描所有未审计的在册版本,对配置已知者自动跑并落台账",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=None,
        help="多重检验试验数 N；缺省自动取该母策略台账迭代数（逐家族搜索广度）",
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="把 DSR/PSR/多重检验摘要写回台账对应版本的 nine_gate 字段",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="审计指定台账版本（如 v1.1 / v1.0-full）；自动套用该版本真实 config",
    )
    parser.add_argument("--start", default=None, help="覆盖回测起始（如全历史变体 2012-01-01）")
    args = parser.parse_args(argv)

    if args.audit_stale:
        audit_stale_registered(persist=args.persist)
        return 0
    if args.strategy:
        run_evaluation(
            args.strategy,
            args.trials,
            persist=args.persist,
            version=args.version,
            start=args.start,
        )
        return 0
    parser.error("需指定 --strategy <name> 或 --audit-stale")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
