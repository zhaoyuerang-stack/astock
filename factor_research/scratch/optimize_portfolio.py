import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from scipy.optimize import minimize

# Align to project root
PROJECT_ROOT = Path("/Users/kiki/astcok/factor_research")
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from portfolio.strategy_runners import run_active, _load_panels
from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
import factors.d_le_sc
from lake.load_lake import load_prices, load_raw_close

def build_d_le_sc_weights_buffered(factor: pd.DataFrame, close: pd.DataFrame, top_n: int, buffer_n: int) -> dict:
    fdates = factor.dropna(how="all").index.intersection(close.index)
    weights = {}
    current_portfolio = []
    
    for rd in fdates:
        pos = close.index.get_loc(rd)
        if pos + 1 >= len(close.index):
            continue
        effective = close.index[pos + 1]
        
        f = factor.loc[rd].dropna()
        active = close.loc[rd].dropna().index
        f = f.reindex(active).dropna()
        
        if len(f) < top_n:
            continue
            
        ranks = f.rank(ascending=False)
        
        keep_stocks = []
        for stock in current_portfolio:
            if stock in ranks.index and ranks.loc[stock] <= buffer_n:
                keep_stocks.append(stock)
                
        slots_needed = top_n - len(keep_stocks)
        if slots_needed > 0:
            candidates = ranks.sort_values().index
            new_additions = []
            for cand in candidates:
                if cand not in keep_stocks:
                    new_additions.append(cand)
                    if len(new_additions) == slots_needed:
                        break
            current_portfolio = keep_stocks + new_additions
        else:
            current_portfolio = keep_stocks[:top_n]
            
        weights[effective] = pd.Series(1.0 / top_n, index=current_portfolio)
        
    return weights

def run_d_le_sc_returns(start_str="2018-01-01"):
    start_dt = pd.Timestamp(start_str)
    load_start_dt = start_dt - pd.Timedelta(days=120)
    load_start_str = load_start_dt.strftime("%Y-%m-%d")
    
    px = load_prices(start=load_start_str, fields=("open", "close", "volume", "amount"))
    raw_close = load_raw_close(start=load_start_str)

    close = px["close"]
    volume = px["volume"]
    amount = px["amount"]

    common_idx = close.index
    if not raw_close.empty:
        raw_close = raw_close.reindex(index=common_idx, columns=close.columns)
    else:
        raw_close = close.copy()

    panels = {
        "open": px["open"].reindex(index=common_idx, columns=close.columns),
        "close": close,
        "volume": volume,
        "amount": amount,
        "raw_close": raw_close,
    }

    factor, univ = factors.d_le_sc.build_d_le_sc_factor(
        panels,
        universe_size=800,
        lookback=60,
        network_type="preclose_lead_close",
        correlation_method="pearson",
        rebalance_days=20,
    )

    factor = -1.0 * factor
    # Use the optimized rank buffer weight builder (Top 25, Buf 50)
    scheduled = build_d_le_sc_weights_buffered(factor, close, top_n=25, buffer_n=50)

    prices = PricePanel(close=close, volume=volume, amount=amount, raw_close=raw_close)
    engine_config = BacktestConfig(
        start=start_str,
        cost=CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.0),
        leverage=1.0,
    )

    engine = BacktestEngine(prices=prices, config=engine_config)
    long_signal = Signal(weights=scheduled, timing=None)
    res_long = engine.run(long_signal)

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
    
    daily_hedge_cost = 0.015 / 252.0
    r_neutral = r_long - r_bench - daily_hedge_cost

    return r_neutral.loc[start_dt:].dropna()

def optimize_sharpe(returns_df):
    """Finds weights that maximize portfolio Sharpe ratio."""
    mean_rets = returns_df.mean() * 252
    cov_matrix = returns_df.cov() * 252
    
    def neg_sharpe(weights):
        p_ret = np.dot(weights, mean_rets)
        p_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
        return -p_ret / p_vol if p_vol > 0 else 0.0

    n = len(mean_rets)
    constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0})
    bounds = tuple((0.0, 1.0) for _ in range(n))
    init_weights = np.ones(n) / n
    
    res = minimize(neg_sharpe, init_weights, method='SLSQP', bounds=bounds, constraints=constraints)
    return res.x, -res.fun

def run_backtest_performance(returns_df, weights):
    p_returns = returns_df.dot(weights)
    ann_ret = p_returns.mean() * 252
    vol = p_returns.std() * np.sqrt(252)
    sharpe = ann_ret / vol if vol > 0 else 0.0
    
    cum = (1 + p_returns).cumprod()
    max_dd = (cum / cum.cummax() - 1).min()
    return ann_ret, vol, sharpe, max_dd

def main():
    import logging
    logging.getLogger("factors.d_le_sc").setLevel(logging.WARNING)

    print("=" * 75)
    print("Portfolio Optimization & Spanning Test with Optimized d-LE-SC (Buf 50)")
    print("=" * 75)

    # 1. Load active strategies
    print("[1/3] Running active live strategies...")
    existing_live = run_active(start="2018-01-01")
    
    # 2. Run candidate strategy
    print("[2/3] Running candidate strategy d-le-sc-hedged v1.1 (Optimized)...")
    dlesc_ret = run_d_le_sc_returns("2018-01-01")
    
    # Align dates
    common_idx = dlesc_ret.index
    for r in existing_live.values():
        common_idx = common_idx.intersection(r.index)
        
    df = pd.DataFrame({
        "small_cap": existing_live["small-cap-size.v2.0"].loc[common_idx],
        "illiquidity": existing_live["illiquidity.v1.0"].loc[common_idx],
        "dlesc_m5_opt": dlesc_ret.loc[common_idx]
    })

    print(f"\nAligned history: {df.index[0].date()} to {df.index[-1].date()} ({len(df)} trading days)")
    print("\nCorrelation Matrix:")
    print(df.corr())
    
    # 3. Optimize Baseline Portfolio (without M5)
    print("\n[3/3] Optimizing weights...")
    baseline_df = df[["small_cap", "illiquidity"]]
    w_base, sh_base = optimize_sharpe(baseline_df)
    ann_b, vol_b, sharpe_b, dd_b = run_backtest_performance(baseline_df, w_base)
    
    # Optimize Combined Portfolio (with M5)
    w_comb, sh_comb = optimize_sharpe(df)
    ann_c, vol_c, sharpe_c, dd_c = run_backtest_performance(df, w_comb)
    
    print("\n" + "=" * 75)
    print("PORTFOLIO OPTIMIZATION SUMMARY (OPTIMIZED M5)")
    print("=" * 75)
    print("1. Baseline Portfolio (small_cap + illiquidity):")
    print(f"   - Optimal Weights: small_cap={w_base[0]:.1%}, illiquidity={w_base[1]:.1%}")
    print(f"   - Annual Return:   {ann_b:.2%}")
    print(f"   - Volatility:      {vol_b:.2%}")
    print(f"   - Sharpe Ratio:    {sharpe_b:.3f}")
    print(f"   - Max Drawdown:    {dd_b:.2%}")
    
    print("\n2. Optimized Portfolio with Optimized d-LE-SC (M5) added:")
    print(f"   - Optimal Weights: small_cap={w_comb[0]:.1%}, illiquidity={w_comb[1]:.1%}, dlesc_m5_opt={w_comb[2]:.1%}")
    print(f"   - Annual Return:   {ann_c:.2%}")
    print(f"   - Volatility:      {vol_c:.2%}")
    print(f"   - Sharpe Ratio:    {sharpe_c:.3f}")
    print(f"   - Max Drawdown:    {dd_c:.2%}")
    
    print("\n3. Spanning Test Results:")
    print(f"   - Sharpe Ratio Improvement: {sharpe_c - sharpe_b:+.3f}")
    print(f"   - Max Drawdown Improvement: {dd_c - dd_b:+.2%}")
    print(f"   - Optimal Allocation to M5: {w_comb[2]:.1%}")
    print("=" * 75)

if __name__ == "__main__":
    main()
