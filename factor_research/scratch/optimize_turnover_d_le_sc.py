import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np

# Align to project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
import factors.d_le_sc
from strategies.d_le_sc import build_d_le_sc_weights
from lake.load_lake import load_prices, load_raw_close

def build_d_le_sc_weights_buffered(factor: pd.DataFrame, close: pd.DataFrame, top_n: int, buffer_n: int) -> dict:
    """Weight builder with a hysteresis rank buffer to control turnover.
    
    A stock currently in the portfolio is kept as long as it remains in the top `buffer_n` ranks.
    New stocks are added only to fill empty slots.
    """
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
            
        # Ranks: rank 1 is the highest factor value (best expected return)
        ranks = f.rank(ascending=False)
        
        # Check which existing holdings can be kept (rank <= buffer_n)
        keep_stocks = []
        for stock in current_portfolio:
            if stock in ranks.index and ranks.loc[stock] <= buffer_n:
                keep_stocks.append(stock)
                
        # Fill remaining slots with the highest-ranked new stocks
        slots_needed = top_n - len(keep_stocks)
        if slots_needed > 0:
            # Sort candidate index by rank ascending (best first)
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

def run_backtest_with_opts(panels, close, volume, amount, raw_close, factor, univ, 
                           rebalance_days, direction, top_n, buffer_n=None, start_str="2023-01-01"):
    start_dt = pd.Timestamp(start_str)
    
    # 1. Apply direction to factor
    adj_factor = direction * factor
    
    # 2. Build weights (standard vs buffered)
    if buffer_n is not None:
        scheduled = build_d_le_sc_weights_buffered(adj_factor, close, top_n, buffer_n)
    else:
        scheduled = build_d_le_sc_weights(adj_factor, close, top_n)
        
    # 3. Configure backtest engine with standard costs
    prices = PricePanel(close=close, volume=volume, amount=amount, raw_close=raw_close)
    engine_config = BacktestConfig(
        start=start_str,
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

    # 4. Compute Universe Benchmark (Shifted 1 Day to avoid leak)
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

    # Hedged return (including annual hedge cost of 1.5%)
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
    import logging
    logging.getLogger("factors.d_le_sc").setLevel(logging.WARNING)
    
    print("=" * 115)
    print("Optimizing d-LE-SC Turnover: Factor Smoothing & Rank Buffering")
    print("=" * 115)

    start_str = "2023-01-01"
    start_dt = pd.Timestamp(start_str)
    load_start_dt = start_dt - pd.Timedelta(days=120)
    load_start_str = load_start_dt.strftime("%Y-%m-%d")

    # Load data once
    print("Loading data lake...")
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

    # Define base strategy configuration
    net_type = "preclose_lead_close"
    method = "pearson"
    direction = -1
    
    # We will test two rebalance intervals: 5 days and 20 days
    for reb in [5, 20]:
        print(f"\n--- Running tests for rebalance_days = {reb} ---")
        
        # Calculate raw factor (no smoothing)
        print("Calculating base factor...")
        raw_factor, univ = factors.d_le_sc.build_d_le_sc_factor(
            panels,
            universe_size=800,
            lookback=60,
            network_type=net_type,
            correlation_method=method,
            rebalance_days=reb,
        )
        
        # Test configurations
        tests = [
            ("Baseline (No Opts)", raw_factor, None),
            ("Rank Buffer (Top 25, Buf 35)", raw_factor, 35),
            ("Rank Buffer (Top 25, Buf 45)", raw_factor, 45),
            ("Rank Buffer (Top 25, Buf 50)", raw_factor, 50),
        ]
        
        # Also compute smoothed factors
        for w in [3, 5, 10]:
            smoothed = raw_factor.rolling(window=w, min_periods=1).mean()
            tests.append((f"Factor Smoothing (SMA {w}d)", smoothed, None))
            # Test combined
            tests.append((f"Smoothed SMA {w}d + Buf 45", smoothed, 45))
            
        print("=" * 115)
        print(f"{'Configuration':<45}{'Ann Return':<15}{'Sharpe':<10}{'Max DD':<10}{'Ann Turnover':<15}")
        print("=" * 115)
        
        for label, factor_df, buf_n in tests:
            res = run_backtest_with_opts(
                panels, close, volume, amount, raw_close, factor_df, univ,
                rebalance_days=reb, direction=direction, top_n=25, buffer_n=buf_n, start_str=start_str
            )
            print(f"{label:<45}{res['ann_ret']:>13.2%}{res['sharpe']:>10.2f}{res['max_dd']:>10.2%}{res['turnover']:>15.2f}")
        print("=" * 115)

if __name__ == "__main__":
    main()
