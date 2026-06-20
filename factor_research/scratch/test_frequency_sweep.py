"""Sweep rebalancing frequencies for active strategies to evaluate low-frequency versions.
"""
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
os.chdir(Path(__file__).resolve().parent.parent)
sys.path.insert(0, str(Path.cwd()))

import numpy as np
import pandas as pd

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from strategies.small_cap import load_price_panels, build_rebalance_weights
from factors.small_cap import small_cap_factor, small_cap_timing
from engine.metrics import metrics as get_metrics


def run_sweep(strategy_name, factor_builder, start_date="2018-01-01"):
    print(f"\nRunning frequency sweep for: {strategy_name}")
    print(f"  {'Rebal Days':<12} {'Net Ann':>8} {'Sharpe':>7} {'MaxDD':>8} {'Turnover':>9} {'Cost Drag':>10}")
    print("  " + "-" * 60)

    # Load data
    close, volume, amount = load_price_panels("2010-01-01")
    prices = PricePanel(close=close, volume=volume, amount=amount)

    # Build factor
    factor = factor_builder(close, volume, amount)

    # Get timing
    timing, _, _ = small_cap_timing(close, amount, ma_window=16)

    results = []
    frequencies = [20, 40, 60, 80, 100, 120]

    for freq in frequencies:
        # Build weights for this frequency
        scheduled = build_rebalance_weights(factor, close, top_n=25, rebalance_days=freq)

        # Config with standard costs
        cfg = BacktestConfig(
            start=start_date,
            cost=CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.065),
            leverage=1.25,
        )
        engine = BacktestEngine(prices=prices, config=cfg)
        signal = Signal(
            weights=scheduled,
            timing=timing,
            family=strategy_name,
            version=f"sweep_f{freq}",
        )
        res = engine.run(signal)

        m = res.metrics
        # Annualized turnover = mean daily turnover * 252
        turnover = float(res.detail["turnover"].mean() * 252)
        # Annualized cost drag = mean daily cost * 252
        cost_drag = float(res.detail["cost"].mean() * 252)

        results.append({
            "freq": freq,
            "annual": m["annual"],
            "sharpe": m["sharpe"],
            "maxdd": m["maxdd"],
            "turnover": turnover,
            "cost_drag": cost_drag
        })

        print(f"  {freq:<12d} {m['annual']:>+7.2%} {m['sharpe']:>7.2f} {m['maxdd']:>8.2%} {turnover:>8.1f}x {cost_drag:>9.2%}")

    return pd.DataFrame(results)


def _f_small_cap(close, volume, amount):
    return small_cap_factor(amount, window=60)


def _f_illiquidity(close, volume, amount, n=20):
    ret = close.pct_change(fill_method=None).abs()
    illiq = (ret / (amount.replace(0, np.nan) + 1)).rolling(n).mean()
    from factors.utils import mad_clip, safe_zscore
    return safe_zscore(mad_clip(illiq))


def main():
    print("=" * 80)
    print("  REBALANCING FREQUENCY SWEEP & LOW FREQUENCY ANALYSIS")
    print("=" * 80)

    # 1. Sweep small-cap-size
    run_sweep("small-cap-size", _f_small_cap, "2018-01-01")

    # 2. Sweep illiquidity
    run_sweep("illiquidity", _f_illiquidity, "2018-01-01")


if __name__ == "__main__":
    main()
