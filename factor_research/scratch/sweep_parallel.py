import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import logging

# Align to project root
PROJECT_ROOT = Path("/Users/kiki/astcok/factor_research")
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from strategies.d_le_sc import StrategyConfig, run_d_le_sc_strategy, build_d_le_sc_weights
import factors.d_le_sc
from lake.load_lake import load_prices, load_raw_close
from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel

def run_single_combination(net_type, method, reb):
    """Computes the factor once, then runs standard and reversed backtests."""
    # Suppress worker logs to keep output clean
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

    # Compute base factor (direction = 1)
    factor, univ = factors.d_le_sc.build_d_le_sc_factor(
        panels,
        universe_size=800,
        lookback=60,
        network_type=net_type,
        correlation_method=method,
        rebalance_days=reb,
    )

    results = []
    for direction in [1, -1]:
        # Compute weights
        adj_factor = direction * factor
        scheduled = build_d_le_sc_weights(adj_factor, close, top_n=25)

        # Configure engine
        prices = PricePanel(close=close, volume=volume, amount=amount, raw_close=raw_close)
        engine_config = BacktestConfig(
            start="2023-01-01",
            cost=CostModel(buy_cost=0.0, sell_cost=0.0, financing_rate=0.0),
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

        common_idx = res_long.returns.index.intersection(bench_returns.index)
        r_long = res_long.returns.loc[common_idx]
        r_bench = bench_returns.loc[common_idx]
        r_neutral = r_long - r_bench

        returns = r_neutral.loc[start_dt:]
        nav = (1 + returns.fillna(0)).cumprod()
        ann_ret = returns.mean() * 252
        max_dd = (nav / nav.cummax() - 1).min()
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0.0

        dir_str = "std" if direction == 1 else "rev"
        results.append({
            "net_type": net_type,
            "method": method,
            "reb": reb,
            "dir": dir_str,
            "ann_ret": ann_ret,
            "sharpe": sharpe,
            "max_dd": max_dd
        })
    return results

def main():
    network_types = ["overnight_lead_daytime", "daytime_lead_overnight", "preclose_lead_close"]
    methods = ["pearson", "spearman"]
    rebalances = [1, 5, 20]

    tasks = []
    for net_type in network_types:
        for method in methods:
            for reb in rebalances:
                tasks.append((net_type, method, reb))

    print("=" * 110)
    print(f"{'Network Type':<26}{'Method':<10}{'Reb':<5}{'Dir':<5}{'Ann Return':<15}{'Sharpe':<10}{'Max DD':<10}")
    print("=" * 110)

    results_list = []
    num_workers = min(multiprocessing.cpu_count(), 8)
    print(f"Starting parallel sweep with {num_workers} workers...", flush=True)

    with ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = {executor.submit(run_single_combination, net_type, method, reb): (net_type, method, reb) for net_type, method, reb in tasks}
        for future in as_completed(futures):
            net_type, method, reb = futures[future]
            try:
                res = future.result()
                for r in res:
                    print(f"{r['net_type']:<26}{r['method']:<10}{r['reb']:<5}{r['dir']:<5}{r['ann_ret']:>13.2%}{r['sharpe']:>10.2f}{r['max_dd']:>10.2%}", flush=True)
                    results_list.append(r)
            except Exception as e:
                print(f"Error for {net_type}/{method}/reb={reb}: {e}", flush=True)

    print("=" * 110)
    print("\nTop 10 configurations sorted by Sharpe ratio:")
    print("=" * 110)
    print(f"{'Network Type':<26}{'Method':<10}{'Reb':<5}{'Dir':<5}{'Ann Return':<15}{'Sharpe':<10}{'Max DD':<10}")
    print("=" * 110)
    sorted_results = sorted(results_list, key=lambda x: x["sharpe"], reverse=True)
    for r in sorted_results[:10]:
        print(f"{r['net_type']:<26}{r['method']:<10}{r['reb']:<5}{r['dir']:<5}{r['ann_ret']:>13.2%}{r['sharpe']:>10.2f}{r['max_dd']:>10.2%}")
    print("=" * 110)

if __name__ == "__main__":
    main()
