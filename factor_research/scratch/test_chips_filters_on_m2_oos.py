"""Research script to test chips filters on M2 during OOS 2023-2026.
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
from factors.large_cap import load_clean_panels_with_growth, build_universe, large_cap_timing_hysteresis

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
    print("  EVALUATING CHIPS FILTERS ON M2 OOS (2023-2026)  ")
    print("=" * 110)

    panels = load_clean_panels_with_growth()
    close = panels["close"]
    amount = panels["amount"]
    raw_close = panels["raw_close"]
    roe = panels["roe"]
    npy = panels["npy"]
    pe = panels["pe"]
    pb = panels["pb"]
    
    daily_all = pd.read_parquet("data_lake/price/daily_all.parquet", columns=["date", "code", "volume"])
    daily_all["date"] = pd.to_datetime(daily_all["date"])
    volume_raw = daily_all.pivot(index="date", columns="code", values="volume")
    
    clean_dates = close.index[close.index < "2026-06-10"]
    close = close.reindex(clean_dates)
    amount = amount.reindex(clean_dates)
    raw_close = raw_close.reindex(clean_dates)
    volume_raw = volume_raw.reindex(clean_dates)
    roe = roe.reindex(clean_dates)
    npy = npy.reindex(clean_dates)
    pe = pe.reindex(clean_dates)
    pb = pb.reindex(clean_dates)
    
    prices = PricePanel(close=close, volume=amount*0, amount=amount, raw_close=raw_close)
    shares = load_shares_outstanding(clean_dates).reindex(columns=close.columns).ffill()
    
    turnover = (volume_raw * 100.0 / shares.replace(0, np.nan)).fillna(0.0)
    turnover = turnover.clip(lower=0.0, upper=0.50)

    # Compute chips cost distribution
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

    # Base M2 Factor (w_cpv_max = 0.25)
    univ_200 = build_universe(panels, 200).reindex(clean_dates)
    
    pe_r = pe.rank(axis=1, pct=True, na_option="bottom")
    pb_r = pb.rank(axis=1, pct=True, na_option="bottom")
    val_r = (pe_r + pb_r) / 2.0
    roe_r = roe.rank(axis=1, pct=True, na_option="bottom")
    npy_r = npy.rank(axis=1, pct=True, na_option="bottom")
    grow_r = (roe_r + npy_r) / 2.0
    
    # CPV rank product
    mean1 = close.rolling(20).mean()
    mean2 = amount.rolling(20).mean()
    mean_prod = (close * amount).rolling(20).mean()
    cov = mean_prod - mean1 * mean2
    std1 = close.rolling(20).std()
    std2 = amount.rolling(20).std()
    cpv = cov / (std1 * std2 + 1e-8)
    
    cpv_raw_r = cpv.rank(axis=1, pct=True, na_option="bottom")
    m_liq = 1.0 / (mean2 + 1.0)
    m_liq_r = m_liq.rank(axis=1, pct=True, na_option="bottom")
    cpv_r = (cpv_raw_r * m_liq_r).rank(axis=1, pct=True, na_option="bottom")
    
    daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    bench_returns = pd.Series(0.0, index=daily_ret.index)
    univ_shifted = univ_200.shift(1)
    for dt in daily_ret.index:
        active = univ_shifted.loc[dt] if dt in univ_shifted.index else pd.Series(False, index=univ_200.columns)
        active = active.fillna(False).astype(bool)
        active_codes = active[active].index
        if len(active_codes) > 0:
            bench_returns.loc[dt] = daily_ret.loc[dt, active_codes].mean()
            
    bench_nav = (1 + bench_returns).cumprod()
    bench_ma = bench_nav.rolling(120).mean()
    is_bull = (bench_nav > bench_ma).astype(float).shift(1).fillna(0.0)
    is_bull_df = pd.DataFrame({col: is_bull for col in close.columns}, index=close.index)
    
    w_cpv = is_bull_df * 0.25
    base_factor = ((val_r + grow_r - w_cpv * cpv_r) / (2.0 + w_cpv)).where(univ_200)

    # Filter 1: Exclude stocks where Profit Ratio < 25% (Falling knives)
    filter_no_falling_knives = profit_ratio >= 0.25
    factor_f1 = base_factor.where(filter_no_falling_knives)

    eval_start_oos = "2023-01-01"
    
    def run_m2_timed_oos(factor):
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
        return r_timed.loc[eval_start_oos:]

    print("\nEvaluating OOS returns...", flush=True)
    ret_base = run_m2_timed_oos(base_factor)
    ret_f1 = run_m2_timed_oos(factor_f1)
    
    m_base = get_metrics(ret_base)
    m_f1 = get_metrics(ret_f1)
    
    print("\n" + "=" * 90)
    print("  M2 OOS PERFORMANCE WITH CHIPS FILTERS (2023-01-01 to 2026-06-09)")
    print("=" * 90)
    print(f"M2 Baseline (No Chips Filter)   | AnnRet: {m_base['annual']:>7.2%} | Sharpe: {m_base['sharpe']:>5.2f} | MaxDD: {m_base['maxdd']:>7.2%} | Calmar: {m_base['calmar']:.2f}")
    print(f"M2 with Filter 1 (No Falling K)  | AnnRet: {m_f1['annual']:>7.2%} | Sharpe: {m_f1['sharpe']:>5.2f} | MaxDD: {m_f1['maxdd']:>7.2%} | Calmar: {m_f1['calmar']:.2f}")
    print("=" * 90)

if __name__ == "__main__":
    main()
