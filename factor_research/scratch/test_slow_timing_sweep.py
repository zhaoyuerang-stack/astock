"""Sweep timing MA windows for low-frequency strategies to reduce timing-induced turnover.
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
from factors.utils import safe_zscore, mad_clip


def _f_illiquidity(close, volume, amount, n=20):
    ret = close.pct_change(fill_method=None).abs()
    illiq = (ret / (amount.replace(0, np.nan) + 1)).rolling(n).mean()
    return safe_zscore(mad_clip(illiq))


def main():
    print("=" * 80)
    print("  SLOW TIMING SWEEP FOR LOW-FREQUENCY ILLIQUIDITY STRATEGY")
    print("=" * 80)

    start_date = "2018-01-01"
    close, volume, amount = load_price_panels("2010-01-01")
    prices = PricePanel(close=close, volume=volume, amount=amount)

    factor = _f_illiquidity(close, volume, amount)
    
    # We use 120-day rebalancing as our low-frequency baseline
    rebal_freq = 120
    scheduled = build_rebalance_weights(factor, close, top_n=25, rebalance_days=rebal_freq)

    print(f"Low-frequency strategy: illiquidity (Rebalance = {rebal_freq} days)")
    print(f"  {'Timing MA':<12} {'Net Ann':>8} {'Sharpe':>7} {'MaxDD':>8} {'Turnover':>9} {'Cost Drag':>10}")
    print("  " + "-" * 60)

    # We sweep the timing MA window
    # 0 means untimed (always in)
    ma_windows = [0, 16, 30, 60, 120]

    for ma in ma_windows:
        if ma == 0:
            timing = pd.Series(1.0, index=close.index)
            label = "Untimed"
        else:
            # Recompute timing with slower MA
            timing, _, _ = small_cap_timing(close, amount, ma_window=ma)
            label = f"MA {ma}"

        cfg = BacktestConfig(
            start=start_date,
            cost=CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.065),
            leverage=1.25,
        )
        engine = BacktestEngine(prices=prices, config=cfg)
        signal = Signal(
            weights=scheduled,
            timing=timing,
            family="illiq_low_freq",
            version=f"ma{ma}",
        )
        res = engine.run(signal)

        m = res.metrics
        turnover = float(res.detail["turnover"].mean() * 252)
        cost_drag = float(res.detail["cost"].mean() * 252)

        print(f"  {label:<12} {m['annual']:>+7.2%} {m['sharpe']:>7.2f} {m['maxdd']:>8.2%} {turnover:>8.1f}x {cost_drag:>9.2%}")


if __name__ == "__main__":
    main()
