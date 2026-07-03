"""Full-universe grid for historical similar cross-section memory.

Research-only. The search data is truncated to < holdout boundary and the
reported n_trials is the full parameter grid size, not just the best row.

Run:
    cd factor_research
    python3 scripts/research/historical_memory_grid.py
"""
from __future__ import annotations

import argparse
import itertools
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from core.engine import PricePanel  # noqa: E402
from factors.alpha.base import FactorData  # noqa: E402
from factors.alpha.builtins import AmihudIlliq  # noqa: E402
from factors.utils import mad_clip, safe_zscore  # noqa: E402
from governance.holdout import assert_search_clean, boundary  # noqa: E402
from research_toolkit import build_historical_memory_factor_fast  # noqa: E402
from strategies.small_cap import _drop_star, load_price_panels  # noqa: E402

from scripts.research.historical_memory_rankic_experiment import (  # noqa: E402
    _backtest_factor,
    _forward_returns,
    _jsonable,
    _metrics,
    _rolling_rankic_summary,
)


def _parse_ints(raw: str) -> list[int]:
    return [int(x.strip()) for x in raw.split(",") if x.strip()]


def run_grid(args) -> dict:
    t0 = time.time()
    close, volume, amount = load_price_panels(args.start)
    close, volume, amount = _drop_star(close, volume, amount)

    holdout = boundary()
    mask = close.index < holdout
    close, volume, amount = close.loc[mask], volume.loc[mask], amount.loc[mask]
    assert_search_clean(close.index, label="historical_memory_grid")

    prices_data = FactorData(close=close, volume=volume, amount=amount)
    base_factor = safe_zscore(mad_clip(AmihudIlliq(window=args.factor_window).compute(prices_data)))

    horizons = _parse_ints(args.horizons)
    lookbacks = _parse_ints(args.lookbacks)
    neighbors = _parse_ints(args.neighbors)
    combos = list(itertools.product(horizons, lookbacks, neighbors))

    rows = []
    prices = PricePanel(close=close, volume=volume, amount=amount)
    for i, (horizon, lookback, n_neighbors) in enumerate(combos, start=1):
        c0 = time.time()
        forward_ret = _forward_returns(close, horizon)
        memory_factor = build_historical_memory_factor_fast(
            base_factor,
            forward_ret,
            horizon=horizon,
            lookback=lookback,
            n_neighbors=n_neighbors,
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
            family="historical-memory-grid",
            version="base-shifted-amihud",
        )
        memory_bt = _backtest_factor(
            memory_factor,
            prices,
            start=bt_start,
            top_n=args.top_n,
            rebalance_days=args.rebalance_days,
            family="historical-memory-grid",
            version=f"memory-h{horizon}-lb{lookback}-nn{n_neighbors}",
        )
        base_m = _metrics(base_bt)
        mem_m = _metrics(memory_bt)
        row = {
            "combo": i,
            "horizon": horizon,
            "lookback": lookback,
            "neighbors": n_neighbors,
            "min_history": args.min_history,
            "rankic_windows": rankic["summary"]["windows"],
            "base_rankic": rankic["summary"]["base_rankic"],
            "memory_rankic": rankic["summary"]["memory_rankic"],
            "rankic_delta": rankic["summary"]["rankic_delta"],
            "positive_delta_ratio": rankic["summary"]["positive_delta_ratio"],
            "base_annual": base_m["annual"],
            "memory_annual": mem_m["annual"],
            "annual_delta": mem_m["annual"] - base_m["annual"],
            "base_sharpe": base_m["sharpe"],
            "memory_sharpe": mem_m["sharpe"],
            "sharpe_delta": mem_m["sharpe"] - base_m["sharpe"],
            "base_maxdd": base_m["maxdd"],
            "memory_maxdd": mem_m["maxdd"],
            "base_turnover": base_m["turnover_mean"],
            "memory_turnover": mem_m["turnover_mean"],
            "base_cost_annual": base_m["cost_annual"],
            "memory_cost_annual": mem_m["cost_annual"],
            "cost_annual_delta": mem_m["cost_annual"] - base_m["cost_annual"],
            "elapsed_sec": time.time() - c0,
        }
        rows.append(row)
        print(
            f"[{i:02d}/{len(combos)}] h={horizon} lb={lookback} nn={n_neighbors} "
            f"rankic_delta={row['rankic_delta']:+.4f} "
            f"sharpe_delta={row['sharpe_delta']:+.2f} "
            f"elapsed={row['elapsed_sec']:.1f}s",
            flush=True,
        )

    df = pd.DataFrame(rows).sort_values(["rankic_delta", "memory_sharpe"], ascending=False)
    out_dir = ROOT / "reports" / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "historical_memory_grid.csv"
    json_path = out_dir / "historical_memory_grid.json"
    df.to_csv(csv_path, index=False)

    payload = {
        "experiment": "historical_memory_full_universe_grid",
        "status": "research_only_not_registry_evidence",
        "n_trials": len(combos),
        "data": {
            "start": str(close.index[0].date()),
            "end": str(close.index[-1].date()),
            "holdout_boundary_excluded": str(holdout.date()),
            "stocks": int(close.shape[1]),
            "dates": int(close.shape[0]),
        },
        "params": {
            "factor": f"AmihudIlliq(window={args.factor_window}).mad_clip.zscore",
            "horizons": horizons,
            "lookbacks": lookbacks,
            "neighbors": neighbors,
            "min_history": args.min_history,
            "train_days": args.train_days,
            "test_days": args.test_days,
            "step_days": args.step_days,
            "top_n": args.top_n,
            "rebalance_days": args.rebalance_days,
            "cost_model": "core.engine.CostModel()",
        },
        "elapsed_sec": time.time() - t0,
        "best_by_rankic_delta": df.head(5).to_dict(orient="records"),
        "all_rows": df.to_dict(orient="records"),
        "outputs": {
            "csv": str(csv_path.relative_to(ROOT)),
            "json": str(json_path.relative_to(ROOT)),
        },
    }
    json_path.write_text(json.dumps(_jsonable(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--backtest-start", default="2020-01-01")
    parser.add_argument("--factor-window", type=int, default=20)
    parser.add_argument("--horizons", default="5,10,20")
    parser.add_argument("--lookbacks", default="252,504,756")
    parser.add_argument("--neighbors", default="5,10,20")
    parser.add_argument("--min-history", type=int, default=5)
    parser.add_argument("--train-days", type=int, default=756)
    parser.add_argument("--test-days", type=int, default=252)
    parser.add_argument("--step-days", type=int, default=126)
    parser.add_argument("--top-n", type=int, default=25)
    parser.add_argument("--rebalance-days", type=int, default=20)
    return parser.parse_args()


if __name__ == "__main__":
    result = run_grid(parse_args())
    best = result["best_by_rankic_delta"][0] if result["best_by_rankic_delta"] else {}
    print(json.dumps(_jsonable({
        "n_trials": result["n_trials"],
        "elapsed_sec": result["elapsed_sec"],
        "best": best,
        "outputs": result["outputs"],
    }), ensure_ascii=False, indent=2))
