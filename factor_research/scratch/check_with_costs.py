import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Align to project root
PROJECT_ROOT = Path("/Users/kiki/astcok/factor_research")
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from strategies.d_le_sc import StrategyConfig, run_d_le_sc_strategy, build_d_le_sc_weights
import factors.d_le_sc
from lake.load_lake import load_prices, load_raw_close
from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel

def run_test_with_costs(net_type, method, reb, direction):
    # Suppress worker logs
    import logging
    logging.getLogger("factors.d_le_sc").setLevel(logging.WARNING)
    
    start_dt = pd.Timestamp("2023-01-01")
    load_start_dt = start_dt - pd.Timedelta(days=120)
    load_start_str = load_start_dt.strftime("%Y-%m-%d")

    px = load_prices(start=load_start_str, fields=("open", "close", "volume", "amount"))
    raw_close = load_raw_close(start=load_start_str)

    close = px["close"]
    volume = px["volume"]
    amount = px["amount"]
    open_px = px["open"]

    common_idx = close.index
    if not raw_close.empty:
        raw_close = raw_close.reindex(index=common_idx, columns=close.columns)
    else:
        raw_close = close.copy()

    panels = {
        "open": open_px.reindex(index=common_idx, columns=close.columns),
        "close": close,
        "volume": volume,
        "amount": amount,
        "raw_close": raw_close,
    }

    # Compute factor
    factor, univ = factors.d_le_sc.build_d_le_sc_factor(
        panels,
        universe_size=800,
        lookback=60,
        network_type=net_type,
        correlation_method=method,
        rebalance_days=reb,
    )

    # Apply direction
    factor = direction * factor
    scheduled = build_d_le_sc_weights(factor, close, top_n=25)

    # Configure engine with standard costs
    prices = PricePanel(close=close, volume=volume, amount=amount, raw_close=raw_close)
    engine_config = BacktestConfig(
        start="2023-01-01",
        cost=CostModel(
            buy_cost=0.00225,
            sell_cost=0.00275,
            financing_rate=0.0,
        ),
        leverage=1.0,
    )

    engine = BacktestEngine(prices=prices, config=engine_config)
    long_signal = Signal(weights=scheduled, timing=None)
    res_long = engine.run(long_signal)

    # Compute Universe Benchmark (Shifted 1 Day to avoid leak)
    daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    bench_returns = pd.Series(0.0, index=daily_ret.index)
    univ_shifted = univ.shift(1)
    for dt in daily_ret.index:
        active = univ_shifted.loc[dt] if dt in univ_shifted.index else pd.Series(False, index=univ.columns)
        active = active.fillna(False).astype(bool)
        active_codes = active[active].index
        if len(active_codes) > 0:
            bench_returns.loc[dt] = daily_ret.loc[dt, active_codes].mean()

    # Align dates
    common_idx = res_long.returns.index.intersection(bench_returns.index)
    r_long = res_long.returns.loc[common_idx]
    r_bench = bench_returns.loc[common_idx]

    # Hedged long-short return (including annual hedge cost of 1.5%)
    daily_hedge_cost = 0.015 / 252.0
    r_neutral = r_long - r_bench - daily_hedge_cost

    returns = r_neutral.loc[start_dt:]
    nav = (1 + returns.fillna(0)).cumprod()
    ann_ret = returns.mean() * 252
    max_dd = (nav / nav.cummax() - 1).min()
    sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0.0
    
    # Calculate average annual turnover
    turnover = res_long.turnover.loc[start_dt:]
    annual_turnover = turnover.mean() * 252

    return {
        "ann_ret": ann_ret,
        "sharpe": sharpe,
        "max_dd": max_dd,
        "turnover": annual_turnover
    }

def main():
    configs = [
        # net_type, method, reb, direction
        ("daytime_lead_overnight", "spearman", 1, 1),
        ("daytime_lead_overnight", "spearman", 5, 1),
        ("daytime_lead_overnight", "spearman", 20, 1),
        ("preclose_lead_close", "pearson", 20, -1),
        ("overnight_lead_daytime", "pearson", 5, -1),
        ("daytime_lead_overnight", "pearson", 1, 1),
        ("daytime_lead_overnight", "pearson", 5, 1),
        ("daytime_lead_overnight", "pearson", 20, 1),
    ]

    print("=" * 115)
    print(f"{'Network Type':<26}{'Method':<10}{'Reb':<5}{'Dir':<5}{'Ann Return':<15}{'Sharpe':<10}{'Max DD':<10}{'Ann Turnover':<15}")
    print("=" * 115)

    for net_type, method, reb, direction in configs:
        res = run_test_with_costs(net_type, method, reb, direction)
        dir_str = "std" if direction == 1 else "rev"
        print(f"{net_type:<26}{method:<10}{reb:<5}{dir_str:<5}{res['ann_ret']:>13.2%}{res['sharpe']:>10.2f}{res['max_dd']:>10.2%}{res['turnover']:>15.2f}")
    
    print("=" * 115)

if __name__ == "__main__":
    main()
