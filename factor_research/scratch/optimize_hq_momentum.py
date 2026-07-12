"""Research script to optimize High-Quality Momentum parameters and universe.
"""
import os
import sys
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
sys.path.append(str(PROJECT_ROOT))

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from strategies.small_cap import build_rebalance_weights
from factors.large_cap import load_clean_panels_with_growth

def get_metrics(ret):
    if len(ret) == 0:
        return {"annual": 0.0, "sharpe": 0.0, "maxdd": 0.0}
    nav = (1 + ret.fillna(0)).cumprod()
    ann = nav.iloc[-1] ** (252 / len(ret)) - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0
    maxdd = float((nav / nav.cummax() - 1).min())
    return {"annual": ann, "sharpe": sharpe, "maxdd": maxdd}

def load_quality_fundamentals(trade_dates, data_lake_path=Path("data_lake")):
    fund = pd.read_parquet(data_lake_path / "fundamental_batch.parquet")
    fund["avail_date"] = pd.to_datetime(fund["avail_date"])
    
    raw_all = pd.read_parquet(data_lake_path / "price/daily_raw_all.parquet")
    raw_all["date"] = pd.to_datetime(raw_all["date"])
    raw_close = raw_all.pivot(index="date", columns="code", values="raw_close").reindex(trade_dates).ffill()
    
    trade_idx = pd.DatetimeIndex(trade_dates)
    panels = {}
    for f in ["roe", "gross_margin", "cfo_ps"]:
        sub = fund[["avail_date", "code", f]].dropna()
        sub = sub.sort_values("avail_date").drop_duplicates(["code", "avail_date"], keep="last")
        pivot = sub.pivot(index="avail_date", columns="code", values=f)
        aligned = pivot.reindex(pivot.index.union(trade_idx)).ffill().reindex(trade_idx)
        aligned = aligned.reindex(columns=raw_close.columns)
        panels[f] = aligned
        
    cfo_yield = panels["cfo_ps"] / raw_close.replace(0, np.nan)
    return panels["roe"], panels["gross_margin"], cfo_yield, raw_close

def main():
    print("=" * 115)
    print("  GRID SEARCH OPTIMIZATION FOR HIGH-QUALITY MOMENTUM STRATEGY  ")
    print("=" * 115)

    panels = load_clean_panels_with_growth()
    close = panels["close"]
    amount = panels["amount"]
    raw_close = panels["raw_close"]
    
    clean_dates = close.index[close.index < "2026-06-10"]
    close = close.reindex(clean_dates)
    amount = amount.reindex(clean_dates)
    raw_close = raw_close.reindex(clean_dates)
    
    prices = PricePanel(close=close, volume=amount*0, amount=amount, raw_close=raw_close)
    roe, gross_margin, cfo_yield, _ = load_quality_fundamentals(clean_dates)

    # Pre-compute fundamental quality ranks
    roe_r = roe.rank(axis=1, pct=True, na_option="bottom")
    margin_r = gross_margin.rank(axis=1, pct=True, na_option="bottom")
    cf_r = cfo_yield.rank(axis=1, pct=True, na_option="bottom")
    quality = (roe_r + margin_r + cf_r) / 3.0
    quality_r = quality.rank(axis=1, pct=True, na_option="bottom")

    daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # Grid search parameters
    universe_sizes = [200, 500, 800]
    lookbacks = [40, 60, 120]
    combination_methods = ["filter_40", "filter_20", "rank_sum"]

    results = []

    cost = CostModel(buy_cost=0.0, sell_cost=0.0, financing_rate=0.0)
    config = BacktestConfig(start="2010-01-01", cost=cost, leverage=1.0)

    print(f"{'Univ Size':<9} | {'Lookback':<8} | {'Method':<10} | {'Long AnnRet':<12} | {'Hedged AnnRet':<13} | {'Hedged Sharpe':<13} | {'Hedged MaxDD':<12}")
    print("-" * 115)

    for u_size in universe_sizes:
        # Build universe benchmark
        cap = amount.rolling(20).mean() * raw_close
        univ = cap.rank(axis=1, ascending=False, pct=False) <= u_size
        
        # Benchmark returns
        bench_returns = pd.Series(0.0, index=daily_ret.index)
        univ_shifted = univ.shift(1)
        for dt in daily_ret.index:
            active = univ_shifted.loc[dt] if dt in univ_shifted.index else pd.Series(False, index=univ.columns)
            active = active.fillna(False).astype(bool)
            active_codes = active[active].index
            if len(active_codes) > 0:
                bench_returns.loc[dt] = daily_ret.loc[dt, active_codes].mean()

        for lb in lookbacks:
            # Momentum: lb-day return lagged 20 days
            momentum = close.pct_change(lb, fill_method=None).shift(20)
            mom_r = momentum.rank(axis=1, pct=True, na_option="bottom")
            
            # Smoothness: Kaufman's ER over lb days
            price_change = (close - close.shift(lb)).abs()
            path_len = close.diff().abs().rolling(lb).sum()
            er = price_change / (path_len + 1e-8)
            er_r = er.rank(axis=1, pct=True, na_option="bottom")
            
            smooth_mom = (mom_r * er_r).rank(axis=1, pct=True, na_option="bottom")
            
            for method in combination_methods:
                if method == "filter_40":
                    q_filter = quality.where(univ).rank(axis=1, pct=True) >= 0.60
                    factor = smooth_mom.where(univ & q_filter)
                elif method == "filter_20":
                    q_filter = quality.where(univ).rank(axis=1, pct=True) >= 0.80
                    factor = smooth_mom.where(univ & q_filter)
                elif method == "rank_sum":
                    factor = (quality_r + smooth_mom).rank(axis=1, pct=True).where(univ)
                
                # Backtest long portfolio
                scheduled = build_rebalance_weights(factor, close, top_n=25, rebalance_days=20)
                engine = BacktestEngine(prices=prices, config=config)
                res_lo = engine.run(Signal(weights=scheduled, timing=None))
                
                # Slice to OOS-aligned period (2012-01-01 to 2026-06-09)
                eval_start = "2012-01-01"
                ret_lo = res_lo.returns.loc[eval_start:]
                
                common_idx = ret_lo.index.intersection(bench_returns.index)
                r_long = ret_lo.loc[common_idx]
                r_bench = bench_returns.loc[common_idx]
                
                # Hedged Return (including 1.5% annual cost)
                r_neutral = r_long - r_bench - (0.015 / 252.0)
                
                m_long = get_metrics(r_long)
                m_hedged = get_metrics(r_neutral)
                
                print(f"{u_size:>9} | {lb:>8} | {method:<10} | {m_long['annual']:>12.2%} | {m_hedged['annual']:>13.2%} | {m_hedged['sharpe']:>13.2f} | {m_hedged['maxdd']:>12.2%}")
                results.append((u_size, lb, method, m_long, m_hedged))
                
    # Sort and find best hedged Sharpe
    results.sort(key=lambda x: x[4]["sharpe"], reverse=True)
    best = results[0]
    print("\n" + "=" * 115)
    print(f"  BEST HEDGED HQ MOMENTUM CONFIGURATION:")
    print(f"  Universe Size: {best[0]} | Lookback: {best[1]} days | Method: {best[2]}")
    print(f"  Long Leg Annual Return: {best[3]['annual']:.2%}")
    print(f"  Hedged Leg Annual Return: {best[4]['annual']:.2%} | Sharpe: {best[4]['sharpe']:.2f} | MaxDD: {best[4]['maxdd']:.2%}")
    print("=" * 115)

if __name__ == "__main__":
    main()
