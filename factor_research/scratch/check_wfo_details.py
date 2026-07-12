"""Detailed validation script to inspect all candidate Sharpe ratios and metrics across folds.
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
from factors.large_cap import load_clean_panels_with_growth, build_universe, large_cap_timing_hysteresis
from strategies.small_cap import build_rebalance_weights

def vectorized_rolling_corr(df1, df2, window=20):
    mean1 = df1.rolling(window).mean()
    mean2 = df2.rolling(window).mean()
    mean_prod = (df1 * df2).rolling(window).mean()
    cov = mean_prod - mean1 * mean2
    std1 = df1.rolling(window).std()
    std2 = df2.rolling(window).std()
    return cov / (std1 * std2 + 1e-8)

def get_metrics(ret):
    if len(ret) == 0:
        return {"annual": 0.0, "sharpe": 0.0, "maxdd": 0.0}
    nav = (1 + ret.fillna(0)).cumprod()
    ann = nav.iloc[-1] ** (252 / len(ret)) - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0
    maxdd = float((nav / nav.cummax() - 1).min())
    return {"annual": ann, "sharpe": sharpe, "maxdd": maxdd}

def main():
    print("=" * 110)
    print("  DETAILED PARAMETER SENSITIVITY AND WFO ANALYSIS  ")
    print("=" * 110)

    panels = load_clean_panels_with_growth()
    close = panels["close"]
    amount = panels["amount"]
    raw_close = panels["raw_close"]
    roe = panels["roe"]
    npy = panels["npy"]
    pe = panels["pe"]
    pb = panels["pb"]
    
    clean_dates = close.index[close.index < "2026-06-10"]
    close = close.reindex(clean_dates)
    amount = amount.reindex(clean_dates)
    raw_close = raw_close.reindex(clean_dates)
    roe = roe.reindex(clean_dates)
    npy = npy.reindex(clean_dates)
    pe = pe.reindex(clean_dates)
    pb = pb.reindex(clean_dates)
    
    prices = PricePanel(close=close, volume=amount*0, amount=amount, raw_close=raw_close)
    univ = build_universe(panels, 200).reindex(clean_dates)
    
    # Pre-compute candidate factors
    pe_r = pe.rank(axis=1, pct=True, na_option="bottom")
    pb_r = pb.rank(axis=1, pct=True, na_option="bottom")
    val_r = (pe_r + pb_r) / 2.0
    roe_r = roe.rank(axis=1, pct=True, na_option="bottom")
    npy_r = npy.rank(axis=1, pct=True, na_option="bottom")
    grow_r = (roe_r + npy_r) / 2.0
    
    cpv = vectorized_rolling_corr(close, amount, window=20)
    cpv_raw_r = cpv.rank(axis=1, pct=True, na_option="bottom")
    m_liq = 1.0 / (amount.rolling(20).mean() + 1.0)
    m_liq_r = m_liq.rank(axis=1, pct=True, na_option="bottom")
    cpv_r = (cpv_raw_r * m_liq_r).rank(axis=1, pct=True, na_option="bottom")
    
    daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    bench_returns = pd.Series(0.0, index=daily_ret.index)
    univ_shifted = univ.shift(1)
    for dt in daily_ret.index:
        active = univ_shifted.loc[dt] if dt in univ_shifted.index else pd.Series(False, index=univ.columns)
        active = active.fillna(False).astype(bool)
        active_codes = active[active].index
        if len(active_codes) > 0:
            bench_returns.loc[dt] = daily_ret.loc[dt, active_codes].mean()
            
    bench_nav = (1 + bench_returns).cumprod()
    bench_ma = bench_nav.rolling(120).mean()
    is_bull = (bench_nav > bench_ma).astype(float).shift(1).fillna(0.0)
    is_bull_df = pd.DataFrame({col: is_bull for col in close.columns}, index=close.index)
    
    w_candidates = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5]
    factors = {}
    for w in w_candidates:
        w_cpv = is_bull_df * w
        factors[w] = ((val_r + grow_r - w_cpv * cpv_r) / (2.0 + w_cpv)).where(univ)

    folds = [
        ("2011-01-01", "2015-12-31", "2016-01-01", "2017-12-31"),
        ("2013-01-01", "2017-12-31", "2018-01-01", "2019-12-31"),
        ("2015-01-01", "2019-12-31", "2020-01-01", "2021-12-31"),
        ("2017-01-01", "2021-12-31", "2022-01-01", "2023-12-31"),
        ("2019-01-01", "2023-12-31", "2024-01-01", "2026-06-09")
    ]

    def run_backtest_for_period(factor, start_dt, end_dt):
        scheduled = build_rebalance_weights(factor, close, top_n=25, rebalance_days=40)
        engine_config = BacktestConfig(
            start="2010-01-01",
            cost=CostModel(buy_cost=0.0, sell_cost=0.0, financing_rate=0.0),
            leverage=1.0,
        )
        engine = BacktestEngine(prices=prices, config=engine_config)
        long_signal = Signal(weights=scheduled, timing=None)
        res_long = engine.run(long_signal)
        
        common_idx = res_long.returns.index.intersection(bench_returns.index)
        r_long = res_long.returns.loc[common_idx]
        r_bench = bench_returns.loc[common_idx]
        r_neutral = r_long - r_bench - (0.015 / 252.0)
        
        nav_neutral = (1 + r_neutral).cumprod()
        timing_signal = large_cap_timing_hysteresis(nav_neutral, window=120, buffer=0.01)
        
        transitions = timing_signal.diff().fillna(0.0) != 0.0
        r_timed = r_neutral * timing_signal - 0.0025 * transitions
        
        return r_timed.loc[pd.Timestamp(start_dt):pd.Timestamp(end_dt)]

    print(f"{'Fold':<6} | {'w':<6} | {'IS AnnRet':<10} | {'IS Sharpe':<9} | {'IS MaxDD':<9} | {'OOS AnnRet':<10} | {'OOS Sharpe':<10} | {'OOS MaxDD':<10}")
    print("-" * 110)
    
    for idx, (tr_start, tr_end, te_start, te_end) in enumerate(folds):
        for w in w_candidates:
            ret_is = run_backtest_for_period(factors[w], tr_start, tr_end)
            m_is = get_metrics(ret_is)
            ret_oos = run_backtest_for_period(factors[w], te_start, te_end)
            m_oos = get_metrics(ret_oos)
            print(f"Fold {idx+1} | {w:>5.2f} | {m_is['annual']:>10.2%} | {m_is['sharpe']:>9.3f} | {m_is['maxdd']:>9.2%} | {m_oos['annual']:>10.2%} | {m_oos['sharpe']:>10.3f} | {m_oos['maxdd']:>10.2%}")
        print("-" * 110)

if __name__ == "__main__":
    main()
