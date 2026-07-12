"""Research script to backtest and optimize High-Quality Momentum strategy.
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
    
    # Fields to load: roe, gross_margin, cfo_ps
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
    print("  HIGH-QUALITY MOMENTUM STRATEGY OPTIMIZATION AND BACKTEST  ")
    print("=" * 110)

    # 1. Load data
    print("\n[1/4] Loading price and fundamental panels...", flush=True)
    panels = load_clean_panels_with_growth()
    close = panels["close"]
    amount = panels["amount"]
    raw_close = panels["raw_close"]
    
    clean_dates = close.index[close.index < "2026-06-10"]
    close = close.reindex(clean_dates)
    amount = amount.reindex(clean_dates)
    raw_close = raw_close.reindex(clean_dates)
    
    prices = PricePanel(close=close, volume=amount*0, amount=amount, raw_close=raw_close)
    
    # Load fundamental quality metrics
    q_data = load_quality_fundamentals(clean_dates)
    roe = q_data["roe"]
    gross_margin = q_data["gross_margin"]
    cfo_yield = q_data["cfo_yield"]

    # 2. Build Top 800 Universe
    cap = amount.rolling(20).mean() * raw_close
    univ_800 = cap.rank(axis=1, ascending=False, pct=False) <= 800
    
    print("\n[2/4] Computing factor components...", flush=True)
    
    # A. Momentum: 120-day return lagged 20 days
    momentum = close.pct_change(120, fill_method=None).shift(20)
    mom_r = momentum.rank(axis=1, pct=True, na_option="bottom")
    
    # B. Path Smoothness: Kaufman's Efficiency Ratio (ER) over 120 days
    price_change = (close - close.shift(120)).abs()
    path_len = close.diff().abs().rolling(120).sum()
    er = price_change / (path_len + 1e-8)
    er_r = er.rank(axis=1, pct=True, na_option="bottom")
    
    # Smooth Momentum (Rank Product)
    smooth_mom = (mom_r * er_r).rank(axis=1, pct=True, na_option="bottom")
    
    # C. Fundamental Quality Score
    roe_r = roe.rank(axis=1, pct=True, na_option="bottom")
    margin_r = gross_margin.rank(axis=1, pct=True, na_option="bottom")
    cf_r = cfo_yield.rank(axis=1, pct=True, na_option="bottom")
    quality = (roe_r + margin_r + cf_r) / 3.0
    quality_r = quality.rank(axis=1, pct=True, na_option="bottom")
    
    # 3. Construct Strategy Variants
    print("\n[3/4] Constructing strategy factor variants...", flush=True)
    factors = {}
    
    # Variant 1: Raw Momentum (Baseline)
    factors["raw_mom"] = momentum.where(univ_800)
    
    # Variant 2: Smooth Momentum
    factors["smooth_mom"] = smooth_mom.where(univ_800)
    
    # Variant 3: High-Quality Momentum (Filter + Rank)
    # Only keep stocks in top 40% quality of universe, then rank by smooth momentum
    quality_filter = quality.where(univ_800).rank(axis=1, pct=True) >= 0.60
    factors["hq_mom_filter"] = smooth_mom.where(univ_800 & quality_filter)
    
    # Variant 4: High-Quality Momentum (Rank Sum)
    # Add quality rank and smooth momentum rank
    hq_mom_ranksum = (quality_r + smooth_mom).rank(axis=1, pct=True)
    factors["hq_mom_ranksum"] = hq_mom_ranksum.where(univ_800)

    # Market trend timing: equal-weighted market index above its 200-day moving average
    daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    mkt_returns = daily_ret.mean(axis=1).fillna(0.0)
    mkt_nav = (1 + mkt_returns).cumprod()
    mkt_ma = mkt_nav.rolling(200).mean()
    trend_on = (mkt_nav > mkt_ma).astype(float).shift(1, fill_value=0.0)

    # 4. Backtest all configurations
    print("\n[4/4] Running backtests (2012-2026, rebalanced every 20 days, top 25 holdings)...", flush=True)
    
    rebal = 20
    top_n = 25
    eval_start = "2012-01-01"
    
    results = []
    
    # Setup costs: A-share standard (0.225% buy, 0.275% sell)
    cost = CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.0)
    config = BacktestConfig(start="2010-01-01", cost=cost, leverage=1.0)
    
    for name, factor in factors.items():
        # A. Long-Only (No Timing)
        scheduled = build_rebalance_weights(factor, close, top_n=top_n, rebalance_days=rebal)
        engine = BacktestEngine(prices=prices, config=config)
        res_lo = engine.run(Signal(weights=scheduled, timing=None))
        ret_lo = res_lo.returns.loc[eval_start:]
        m_lo = get_metrics(ret_lo)
        results.append((name, "Long-Only", m_lo))
        
        # B. Trend Timed
        engine_timed = BacktestEngine(prices=prices, config=config)
        res_ti = engine_timed.run(Signal(weights=scheduled, timing=trend_on))
        ret_ti = res_ti.returns.loc[eval_start:]
        m_ti = get_metrics(ret_ti)
        results.append((name, "Trend-Timed", m_ti))

    # Print Comparison Table
    print("\n" + "=" * 95)
    print(f"  STRATEGY RESULTS COMPARISON (2012-01-01 to 2026-06-09)")
    print("=" * 95)
    print(f"{'Strategy Variant':<25} | {'Timing Mode':<12} | {'Ann. Return':<13} | {'Sharpe':<7} | {'Max Drawdown':<12} | {'Calmar':<6}")
    print("-" * 95)
    
    for name, mode, m in results:
        name_lbl = {
            "raw_mom": "1. Raw Momentum",
            "smooth_mom": "2. Smooth Momentum",
            "hq_mom_filter": "3. HQ Mom (Filter)",
            "hq_mom_ranksum": "4. HQ Mom (RankSum)"
        }[name]
        print(f"{name_lbl:<25} | {mode:<12} | {m['annual']:>13.2%} | {m['sharpe']:>7.2f} | {m['maxdd']:>12.2%} | {m['calmar']:>6.2f}")
    print("=" * 95)

if __name__ == "__main__":
    main()
