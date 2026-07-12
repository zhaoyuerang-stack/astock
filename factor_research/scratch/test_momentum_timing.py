"""Research script to test timing on the optimized High-Quality Momentum strategy.
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
from factors.large_cap import load_clean_panels_with_growth, large_cap_timing_hysteresis

def get_metrics(ret):
    if len(ret) == 0:
        return {"annual": 0.0, "sharpe": 0.0, "maxdd": 0.0, "calmar": 0.0}
    nav = (1 + ret.fillna(0)).cumprod()
    ann = nav.iloc[-1] ** (252 / len(ret)) - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0
    maxdd = float((nav / nav.cummax() - 1).min())
    calmar = ann / abs(maxdd) if maxdd != 0 else 0.0
    return {"annual": ann, "sharpe": sharpe, "maxdd": maxdd, "calmar": calmar}

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
    print("=" * 110)
    print("  TIMED HIGH-QUALITY MOMENTUM STRATEGY EVALUATION  ")
    print("=" * 110)

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

    # 1. Build Top 800 Universe
    cap = amount.rolling(20).mean() * raw_close
    univ_800 = cap.rank(axis=1, ascending=False, pct=False) <= 800
    
    # Benchmark returns
    daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    bench_returns = pd.Series(0.0, index=daily_ret.index)
    univ_shifted = univ_800.shift(1)
    for dt in daily_ret.index:
        active = univ_shifted.loc[dt] if dt in univ_shifted.index else pd.Series(False, index=univ_800.columns)
        active = active.fillna(False).astype(bool)
        active_codes = active[active].index
        if len(active_codes) > 0:
            bench_returns.loc[dt] = daily_ret.loc[dt, active_codes].mean()

    # 2. Compute factors (Best setup: Lookback 60 days, Filter 40% Quality)
    momentum = close.pct_change(60, fill_method=None).shift(20)
    mom_r = momentum.rank(axis=1, pct=True, na_option="bottom")
    
    price_change = (close - close.shift(60)).abs()
    path_len = close.diff().abs().rolling(60).sum()
    er = price_change / (path_len + 1e-8)
    er_r = er.rank(axis=1, pct=True, na_option="bottom")
    
    smooth_mom = (mom_r * er_r).rank(axis=1, pct=True, na_option="bottom")
    
    roe_r = roe.rank(axis=1, pct=True, na_option="bottom")
    margin_r = gross_margin.rank(axis=1, pct=True, na_option="bottom")
    cf_r = cfo_yield.rank(axis=1, pct=True, na_option="bottom")
    quality = (roe_r + margin_r + cf_r) / 3.0
    
    q_filter = quality.where(univ_800).rank(axis=1, pct=True) >= 0.60
    factor = smooth_mom.where(univ_800 & q_filter)

    # 3. Backtest
    rebal = 20
    top_n = 25
    eval_start = "2012-01-01"
    
    cost = CostModel(buy_cost=0.0, sell_cost=0.0, financing_rate=0.0)
    config = BacktestConfig(start="2010-01-01", cost=cost, leverage=1.0)
    
    scheduled = build_rebalance_weights(factor, close, top_n=top_n, rebalance_days=rebal)
    engine = BacktestEngine(prices=prices, config=config)
    res_lo = engine.run(Signal(weights=scheduled, timing=None))
    
    ret_lo = res_lo.returns.loc[eval_start:]
    common_idx = ret_lo.index.intersection(bench_returns.index)
    r_long = ret_lo.loc[common_idx]
    r_bench = bench_returns.loc[common_idx]
    
    # Untimed Hedged Return (1.5% annual hedging cost)
    r_neutral = r_long - r_bench - (0.015 / 252.0)
    m_neutral = get_metrics(r_neutral)
    
    # 4. Apply Hysteresis Timing on Hedged NAV
    nav_neutral = (1 + r_neutral).cumprod()
    # Test timing with window 120 and buffer 0.01
    timing_signal = large_cap_timing_hysteresis(nav_neutral, window=120, buffer=0.01)
    
    # Timed returns (including 0.25% switch cost)
    transitions = timing_signal.diff().fillna(0.0) != 0.0
    r_timed = r_neutral * timing_signal - 0.0025 * transitions
    m_timed = get_metrics(r_timed)
    
    print("\n" + "=" * 90)
    print("  STRATEGY RESULTS SUMMARY (2012-01-01 to 2026-06-09)")
    print("=" * 90)
    print(f"Top 800 Benchmark Index | AnnRet: {get_metrics(bench_returns.loc[eval_start:])['annual']:>7.2%} | Sharpe: {get_metrics(bench_returns.loc[eval_start:])['sharpe']:>5.2f} | MaxDD: {get_metrics(bench_returns.loc[eval_start:])['maxdd']:>7.2%}")
    print("-" * 90)
    print(f"Untimed HQ Momentum     | AnnRet: {m_neutral['annual']:>7.2%} | Sharpe: {m_neutral['sharpe']:>5.2f} | MaxDD: {m_neutral['maxdd']:>7.2%} | Calmar: {m_neutral['calmar']:.2f}")
    print(f"Timed HQ Momentum       | AnnRet: {m_timed['annual']:>7.2%} | Sharpe: {m_timed['sharpe']:>5.2f} | MaxDD: {m_timed['maxdd']:>7.2%} | Calmar: {m_timed['calmar']:.2f}")
    print("=" * 90)

if __name__ == "__main__":
    main()
