"""Research script to analyze hedged (market-neutral) returns of momentum variants.
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
    
    return {
        "roe": panels["roe"],
        "gross_margin": panels["gross_margin"],
        "cfo_yield": cfo_yield,
        "raw_close": raw_close
    }

def main():
    print("=" * 110)
    print("  HEDGED (MARKET-NEUTRAL) HIGH-QUALITY MOMENTUM STRATEGY  ")
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
    
    q_data = load_quality_fundamentals(clean_dates)
    roe = q_data["roe"]
    gross_margin = q_data["gross_margin"]
    cfo_yield = q_data["cfo_yield"]

    cap = amount.rolling(20).mean() * raw_close
    univ_800 = cap.rank(axis=1, ascending=False, pct=False) <= 800
    
    # 1. Compute benchmark returns
    daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    bench_returns = pd.Series(0.0, index=daily_ret.index)
    univ_shifted = univ_800.shift(1)
    for dt in daily_ret.index:
        active = univ_shifted.loc[dt] if dt in univ_shifted.index else pd.Series(False, index=univ_800.columns)
        active = active.fillna(False).astype(bool)
        active_codes = active[active].index
        if len(active_codes) > 0:
            bench_returns.loc[dt] = daily_ret.loc[dt, active_codes].mean()
            
    bench_nav = (1 + bench_returns).cumprod()
    m_bench = get_metrics(bench_returns.loc["2012-01-01":])
    print(f"\nTop 800 Benchmark Index | AnnRet: {m_bench['annual']:>7.2%} | Sharpe: {m_bench['sharpe']:>5.2f} | MaxDD: {m_bench['maxdd']:>7.2%}")
    
    # 2. Compute factor components
    momentum = close.pct_change(120, fill_method=None).shift(20)
    mom_r = momentum.rank(axis=1, pct=True, na_option="bottom")
    
    price_change = (close - close.shift(120)).abs()
    path_len = close.diff().abs().rolling(120).sum()
    er = price_change / (path_len + 1e-8)
    er_r = er.rank(axis=1, pct=True, na_option="bottom")
    
    smooth_mom = (mom_r * er_r).rank(axis=1, pct=True, na_option="bottom")
    
    roe_r = roe.rank(axis=1, pct=True, na_option="bottom")
    margin_r = gross_margin.rank(axis=1, pct=True, na_option="bottom")
    cf_r = cfo_yield.rank(axis=1, pct=True, na_option="bottom")
    quality = (roe_r + margin_r + cf_r) / 3.0
    quality_r = quality.rank(axis=1, pct=True, na_option="bottom")
    
    factors = {}
    factors["raw_mom"] = momentum.where(univ_800)
    factors["smooth_mom"] = smooth_mom.where(univ_800)
    
    # We test filter bounds from 40% to 60%
    quality_filter_40 = quality.where(univ_800).rank(axis=1, pct=True) >= 0.60
    factors["hq_mom_filter_40"] = smooth_mom.where(univ_800 & quality_filter_40)
    
    quality_filter_20 = quality.where(univ_800).rank(axis=1, pct=True) >= 0.80
    factors["hq_mom_filter_20"] = smooth_mom.where(univ_800 & quality_filter_20)
    
    hq_mom_ranksum = (quality_r + smooth_mom).rank(axis=1, pct=True)
    factors["hq_mom_ranksum"] = hq_mom_ranksum.where(univ_800)

    # 3. Backtest
    rebal = 20
    top_n = 25
    eval_start = "2012-01-01"
    
    results = []
    
    # 0.25% switch friction, 1.5% annual hedging cost
    cost = CostModel(buy_cost=0.0, sell_cost=0.0, financing_rate=0.0)
    config = BacktestConfig(start="2010-01-01", cost=cost, leverage=1.0)
    
    for name, factor in factors.items():
        scheduled = build_rebalance_weights(factor, close, top_n=top_n, rebalance_days=rebal)
        engine = BacktestEngine(prices=prices, config=config)
        res_lo = engine.run(Signal(weights=scheduled, timing=None))
        ret_lo = res_lo.returns.loc[eval_start:]
        
        # Hedged Return: Long Return - Benchmark Return - 1.5% annual hedging cost
        common_idx = ret_lo.index.intersection(bench_returns.index)
        r_long = ret_lo.loc[common_idx]
        r_bench = bench_returns.loc[common_idx]
        
        # Long-Short Return
        r_neutral = r_long - r_bench - (0.015 / 252.0)
        m_neutral = get_metrics(r_neutral)
        
        results.append((name, m_neutral))

    print("\n" + "=" * 95)
    print(f"  HEDGED STRATEGY RESULTS COMPARISON (2012-01-01 to 2026-06-09)")
    print("=" * 95)
    print(f"{'Strategy Variant':<25} | {'Ann. Return':<13} | {'Sharpe':<7} | {'Max Drawdown':<12} | {'Calmar':<6}")
    print("-" * 95)
    
    for name, m in results:
        name_lbl = {
            "raw_mom": "1. Raw Momentum",
            "smooth_mom": "2. Smooth Momentum",
            "hq_mom_filter_40": "3. HQ Mom (Filter Top 40% Q)",
            "hq_mom_filter_20": "4. HQ Mom (Filter Top 20% Q)",
            "hq_mom_ranksum": "5. HQ Mom (RankSum)"
        }[name]
        print(f"{name_lbl:<25} | {m['annual']:>13.2%} | {m['sharpe']:>7.2f} | {m['maxdd']:>12.2%} | {m['calmar']:>6.2f}")
    print("=" * 95)

if __name__ == "__main__":
    main()
