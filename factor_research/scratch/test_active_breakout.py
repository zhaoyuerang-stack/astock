"""Research script to test the Active Breakout chips factor.
"""
import os
import sys
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import norm

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

def load_shares_outstanding(trade_dates, data_lake_path=Path("data_lake")):
    fund = pd.read_parquet(data_lake_path / "fundamental_batch.parquet")
    fund["avail_date"] = pd.to_datetime(fund["avail_date"])
    fund = fund.dropna(subset=["eps", "net_profit"])
    fund = fund[fund["eps"] != 0]
    fund["shares"] = fund["net_profit"] / fund["eps"]
    
    trade_idx = pd.DatetimeIndex(trade_dates)
    sub = fund[["avail_date", "code", "shares"]].dropna()
    sub = sub.sort_values("avail_date").drop_duplicates(["code", "avail_date"], keep="last")
    pivot = sub.pivot(index="avail_date", columns="code", values="shares")
    aligned = pivot.reindex(pivot.index.union(trade_idx)).ffill().reindex(trade_idx)
    return aligned

def main():
    print("=" * 110)
    print("  ACTIVE BREAKOUT CHIPS FACTOR BACKTEST  ")
    print("=" * 110)

    panels = load_clean_panels_with_growth()
    close = panels["close"]
    amount = panels["amount"]
    raw_close = panels["raw_close"]
    
    daily_all = pd.read_parquet("data_lake/price/daily_all.parquet", columns=["date", "code", "volume"])
    daily_all["date"] = pd.to_datetime(daily_all["date"])
    volume_raw = daily_all.pivot(index="date", columns="code", values="volume")
    
    clean_dates = close.index[close.index < "2026-06-10"]
    close = close.reindex(clean_dates)
    amount = amount.reindex(clean_dates)
    raw_close = raw_close.reindex(clean_dates)
    volume_raw = volume_raw.reindex(clean_dates)
    
    prices = PricePanel(close=close, volume=amount*0, amount=amount, raw_close=raw_close)
    shares = load_shares_outstanding(clean_dates).reindex(columns=close.columns).ffill()
    
    turnover = (volume_raw * 100.0 / shares.replace(0, np.nan)).fillna(0.0)
    turnover = turnover.clip(lower=0.0, upper=0.50)

    # Compute cost distribution
    close_arr = close.values
    turnover_arr = turnover.values
    avg_cost_arr = np.empty_like(close_arr)
    cost_var_arr = np.empty_like(close_arr)
    
    avg_cost_arr[0] = close_arr[0]
    cost_var_arr[0] = 0.0
    
    for t in range(1, len(clean_dates)):
        trn = turnover_arr[t]
        cls = close_arr[t]
        prev_avg = avg_cost_arr[t-1]
        prev_var = cost_var_arr[t-1]
        new_avg = (1.0 - trn) * prev_avg + trn * cls
        new_avg = np.where(np.isnan(new_avg), cls, new_avg)
        avg_cost_arr[t] = new_avg
        
        new_var = (1.0 - trn) * (prev_var + (new_avg - prev_avg)**2) + trn * (cls - new_avg)**2
        new_var = np.where(np.isnan(new_var), 0.0, new_var)
        cost_var_arr[t] = new_var
        
    avg_cost = pd.DataFrame(avg_cost_arr, index=clean_dates, columns=close.columns)
    cost_var = pd.DataFrame(cost_var_arr, index=clean_dates, columns=close.columns)
    cost_std = np.sqrt(cost_var)

    concentration = avg_cost / (cost_std + 1e-8)
    z_score = (close - avg_cost) / (cost_std + 1e-8)
    profit_ratio = pd.DataFrame(norm.cdf(z_score), index=clean_dates, columns=close.columns)

    # Build Top 800 Universe
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

    # Define Active Breakout variants:
    # 1. Rank-based: Profit Ratio rank - Concentration rank
    prof_r = profit_ratio.rank(axis=1, pct=True, na_option="bottom")
    conc_r = concentration.rank(axis=1, pct=True, na_option="bottom")
    
    factors = {
        "active_breakout_diff": (prof_r - conc_r).where(univ_800),
        "active_breakout_prod": (prof_r * (1.0 - conc_r)).where(univ_800)
    }

    eval_start = "2012-01-01"
    cost = CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.0)
    config = BacktestConfig(start="2010-01-01", cost=cost, leverage=1.0)
    
    results = []
    
    for name, factor in factors.items():
        scheduled = build_rebalance_weights(factor, close, top_n=25, rebalance_days=20)
        engine = BacktestEngine(prices=prices, config=config)
        res_lo = engine.run(Signal(weights=scheduled, timing=None))
        ret_lo = res_lo.returns.loc[eval_start:]
        
        # Hedged Return (1.5% annual hedging cost)
        common_idx = ret_lo.index.intersection(bench_returns.index)
        r_long = ret_lo.loc[common_idx]
        r_bench = bench_returns.loc[common_idx]
        r_neutral = r_long - r_bench - (0.015 / 252.0)
        
        m_long = get_metrics(r_long)
        m_hedged = get_metrics(r_neutral)
        results.append((name, m_long, m_hedged))

    print("\n" + "=" * 95)
    print(f"  ACTIVE BREAKOUT STRATEGY RESULTS COMPARISON (2012-01-01 to 2026-06-09)")
    print("=" * 95)
    print(f"{'Strategy Variant':<25} | {'Long AnnRet':<12} | {'Hedged AnnRet':<13} | {'Hedged Sharpe':<13} | {'Hedged MaxDD':<12}")
    print("-" * 95)
    for name, ml, mh in results:
        print(f"{name:<25} | {ml['annual']:>12.2%} | {mh['annual']:>13.2%} | {mh['sharpe']:>13.2f} | {mh['maxdd']:>12.2%}")
    print("=" * 95)

if __name__ == "__main__":
    main()
