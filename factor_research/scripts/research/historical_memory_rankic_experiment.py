"""Conservative test of historical similar cross-section memory.

This is a research-only experiment inspired by MTMD-style memory, not a model
replication and not registry evidence. It asks one narrow question:

    Does a simple memory factor improve rolling OOS RankIC over an existing
    shifted factor, after using matured labels only?

Run:
    cd factor_research
    python3 scripts/research/historical_memory_rankic_experiment.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.engine import BacktestConfig, BacktestEngine, CostModel, PricePanel, Signal  # noqa: E402
from factors.alpha.base import FactorData  # noqa: E402
from factors.alpha.builtins import AmihudIlliq  # noqa: E402
from factors.utils import mad_clip, safe_zscore  # noqa: E402
from governance.holdout import assert_search_clean, boundary  # noqa: E402
from research_toolkit import build_historical_memory_factor, rank_ic_series  # noqa: E402
from strategies.small_cap import _drop_star, build_rebalance_weights, load_price_panels  # noqa: E402


def _forward_returns(close: pd.DataFrame, horizon: int) -> pd.DataFrame:
    return close.pct_change(horizon, fill_method=None).shift(-horizon)


def _metrics(result) -> dict:
    m = result.metrics
    return {
        "annual": float(m.get("annual_return", m.get("annual", np.nan))),
        "sharpe": float(m.get("sharpe", np.nan)),
        "maxdd": float(m.get("max_drawdown", m.get("maxdd", np.nan))),
        "turnover_mean": float(result.turnover.mean()),
        "cost_annual": float(result.cost.mean() * 252),
    }


def _backtest_factor(
    factor: pd.DataFrame,
    prices: PricePanel,
    *,
    start: str,
    top_n: int,
    rebalance_days: int,
    family: str,
    version: str,
):
    weights = build_rebalance_weights(factor, prices.close, top_n, rebalance_days)
    engine = BacktestEngine(
        prices,
        BacktestConfig(start=start, cost=CostModel(), leverage=1.0),
    )
    return engine.run(Signal(weights=weights, family=family, version=version))


def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    if isinstance(obj, (pd.Timestamp,)):
        return str(obj.date())
    return obj


def _rolling_rankic_summary(
    factor: pd.DataFrame,
    memory_factor: pd.DataFrame,
    forward_ret: pd.DataFrame,
    *,
    train_days: int,
    test_days: int,
    step_days: int,
) -> dict:
    dates = factor.index.intersection(forward_ret.index)
    base_ic = rank_ic_series(factor.shift(1), forward_ret)
    memory_ic = rank_ic_series(memory_factor, forward_ret)
    windows = []
    for pos in range(train_days, max(train_days, len(dates) - test_days + 1), step_days):
        wdates = dates[pos: pos + test_days]
        b = base_ic.reindex(wdates).dropna()
        m = memory_ic.reindex(wdates).dropna()
        if len(b) == 0 or len(m) == 0:
            continue
        windows.append({
            "start": str(wdates[0].date()),
            "end": str(wdates[-1].date()),
            "base_rankic": float(b.mean()),
            "memory_rankic": float(m.mean()),
            "rankic_delta": float(m.mean() - b.mean()),
            "base_count": int(len(b)),
            "memory_count": int(len(m)),
        })

    delta = [w["rankic_delta"] for w in windows]
    base = [w["base_rankic"] for w in windows]
    memory = [w["memory_rankic"] for w in windows]
    return {
        "summary": {
            "method": "historical_similar_cross_section_memory",
            "windows": len(windows),
            "base_rankic": float(np.mean(base)) if base else float("nan"),
            "memory_rankic": float(np.mean(memory)) if memory else float("nan"),
            "rankic_delta": float(np.mean(delta)) if delta else float("nan"),
            "positive_delta_ratio": float(np.mean([d > 0 for d in delta])) if delta else float("nan"),
        },
        "windows": windows,
    }


def run(args) -> dict:
    close, volume, amount = load_price_panels(args.start)
    close, volume, amount = _drop_star(close, volume, amount)

    holdout = boundary()
    mask = close.index < holdout
    close, volume, amount = close.loc[mask], volume.loc[mask], amount.loc[mask]
    assert_search_clean(close.index, label="historical_memory_rankic_experiment")

    if args.max_stocks:
        liquid = amount.tail(min(60, len(amount))).median().sort_values(ascending=False)
        cols = liquid.head(args.max_stocks).index
        close, volume, amount = close[cols], volume[cols], amount[cols]

    prices = PricePanel(close=close, volume=volume, amount=amount)
    data = FactorData(close=close, volume=volume, amount=amount)
    base_factor = safe_zscore(mad_clip(AmihudIlliq(window=args.factor_window).compute(data)))
    forward_ret = _forward_returns(close, args.horizon)

    memory_factor = build_historical_memory_factor(
        base_factor,
        forward_ret,
        horizon=args.horizon,
        lookback=args.lookback,
        n_neighbors=args.neighbors,
        min_history=args.min_history,
    )
    rankic = _rolling_rankic_summary(
        base_factor,
        memory_factor,
        forward_ret,
        train_days=args.train_days,
        test_days=args.test_days,
        step_days=args.step_days,
    )

    bt_start = rankic["windows"][0]["start"] if rankic["windows"] else args.backtest_start
    base_bt = _backtest_factor(
        base_factor.shift(1),
        prices,
        start=bt_start,
        top_n=args.top_n,
        rebalance_days=args.rebalance_days,
        family="historical-memory-experiment",
        version="base-shifted-amihud",
    )
    memory_bt = _backtest_factor(
        memory_factor,
        prices,
        start=bt_start,
        top_n=args.top_n,
        rebalance_days=args.rebalance_days,
        family="historical-memory-experiment",
        version="memory-amihud",
    )

    payload = {
        "experiment": "historical_similar_cross_section_memory",
        "status": "research_only_not_registry_evidence",
        "data": {
            "start": str(close.index[0].date()),
            "end": str(close.index[-1].date()),
            "holdout_boundary_excluded": str(holdout.date()),
            "stocks": int(close.shape[1]),
            "dates": int(close.shape[0]),
            "max_stocks": int(args.max_stocks) if args.max_stocks else None,
        },
        "params": {
            "factor": f"AmihudIlliq(window={args.factor_window}).mad_clip.zscore",
            "horizon": args.horizon,
            "lookback": args.lookback,
            "neighbors": args.neighbors,
            "min_history": args.min_history,
            "train_days": args.train_days,
            "test_days": args.test_days,
            "step_days": args.step_days,
            "top_n": args.top_n,
            "rebalance_days": args.rebalance_days,
            "cost_model": "core.engine.CostModel()",
            "signal_alignment": "base uses factor.shift(1); memory uses internal shift(1) and matured labels only",
        },
        "rankic": {
            "summary": rankic["summary"],
            "windows": rankic["windows"],
        },
        "backtest_costed": {
            "start": bt_start,
            "base_shifted_factor": _metrics(base_bt),
            "memory_factor": _metrics(memory_bt),
        },
    }

    out = ROOT / "reports" / "experiments" / "historical_memory_rankic_experiment.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    payload["output_path"] = str(out.relative_to(ROOT))
    return payload


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--backtest-start", default="2020-01-01")
    parser.add_argument("--factor-window", type=int, default=20)
    parser.add_argument("--horizon", type=int, default=20)
    parser.add_argument("--lookback", type=int, default=756)
    parser.add_argument("--neighbors", type=int, default=20)
    parser.add_argument("--min-history", type=int, default=20)
    parser.add_argument("--train-days", type=int, default=756)
    parser.add_argument("--test-days", type=int, default=252)
    parser.add_argument("--step-days", type=int, default=126)
    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument("--rebalance-days", type=int, default=20)
    parser.add_argument("--max-stocks", type=int, default=0, help="Optional smoke-test stock cap; 0 means full universe.")
    return parser.parse_args()


if __name__ == "__main__":
    result = run(parse_args())
    print(json.dumps(_jsonable(result["rankic"]["summary"]), ensure_ascii=False, indent=2))
    print(f"saved: {result['output_path']}")
