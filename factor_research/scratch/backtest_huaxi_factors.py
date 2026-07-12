"""Scratch script to backtest Huaxi Securities 11 Volume-Price Industry Rotation with Timing & Bond Rotation."""
import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

# Align to project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
sys.path.append(str(PROJECT_ROOT))

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from strategies.industry_rotation import StrategyConfig, load_industry_groups, vectorized_rolling_corr
from factors.large_cap import load_clean_panels_with_growth
from factors.small_cap import small_cap_timing

def load_all_daily_price_fields(data_lake_path=Path("data_lake")):
    """Load all daily price fields from daily_all.parquet."""
    cal = pd.read_parquet(data_lake_path / "meta/trade_calendar.parquet")
    trade_dates = pd.to_datetime(cal["date"]).sort_values()
    
    daily_all = pd.read_parquet(data_lake_path / "price/daily_all.parquet")
    daily_all["date"] = pd.to_datetime(daily_all["date"])
    
    # We will pivot each field we need
    close = daily_all.pivot(index="date", columns="code", values="close").reindex(trade_dates)
    open_ = daily_all.pivot(index="date", columns="code", values="open").reindex(trade_dates)
    high = daily_all.pivot(index="date", columns="code", values="high").reindex(trade_dates)
    low = daily_all.pivot(index="date", columns="code", values="low").reindex(trade_dates)
    volume = daily_all.pivot(index="date", columns="code", values="volume").reindex(trade_dates)
    amount = daily_all.pivot(index="date", columns="code", values="amount").reindex(trade_dates)
    
    # Load raw_close for execution
    raw_all = pd.read_parquet(data_lake_path / "price/daily_raw_all.parquet")
    raw_all["date"] = pd.to_datetime(raw_all["date"])
    raw_close = raw_all.pivot(index="date", columns="code", values="raw_close").reindex(trade_dates)
    
    return {
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
        "amount": amount,
        "raw_close": raw_close
    }

def load_bond_returns(code="511010"):
    """Loads Gov Bond ETF daily returns."""
    df = pd.read_parquet(f"data_lake/cross_asset/etf/{code}.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").set_index("date")
    return df["close"].pct_change(fill_method=None).dropna()

def aggregate_industry_all_fields(prices, stock_to_ind):
    """Aggregates all price fields to industry level."""
    close = prices["close"]
    open_ = prices["open"]
    high = prices["high"]
    low = prices["low"]
    volume = prices["volume"]
    amount = prices["amount"]
    
    common_codes = close.columns.intersection(amount.columns)
    ind_groups = {}
    for code in common_codes:
        ind = stock_to_ind.get(code)
        if ind:
            ind_groups.setdefault(ind, []).append(code)
            
    trade_dates = close.index
    industries = list(ind_groups.keys())
    
    ind_close = pd.DataFrame(1.0, index=trade_dates, columns=industries)
    ind_open = pd.DataFrame(1.0, index=trade_dates, columns=industries)
    ind_high = pd.DataFrame(1.0, index=trade_dates, columns=industries)
    ind_low = pd.DataFrame(1.0, index=trade_dates, columns=industries)
    ind_volume = pd.DataFrame(0.0, index=trade_dates, columns=industries)
    ind_amount = pd.DataFrame(0.0, index=trade_dates, columns=industries)
    
    # Ratios
    stock_returns = close.pct_change(fill_method=None).fillna(0.0)
    co_ratio = close / open_.replace(0.0, np.nan)
    hc_ratio = high / close.replace(0.0, np.nan)
    lc_ratio = low / close.replace(0.0, np.nan)
    
    for ind, codes in ind_groups.items():
        ind_ret = stock_returns[codes].mean(axis=1)
        ind_close[ind] = (1.0 + ind_ret).cumprod()
        
        mean_co = co_ratio[codes].mean(axis=1).fillna(1.0)
        mean_hc = hc_ratio[codes].mean(axis=1).fillna(1.0)
        mean_lc = lc_ratio[codes].mean(axis=1).fillna(1.0)
        
        ind_open[ind] = ind_close[ind] / mean_co
        ind_high[ind] = ind_close[ind] * mean_hc
        ind_low[ind] = ind_close[ind] * mean_lc
        
        ind_volume[ind] = volume[codes].sum(axis=1)
        ind_amount[ind] = amount[codes].sum(axis=1)
        
    return {
        "open": ind_open,
        "high": ind_high,
        "low": ind_low,
        "close": ind_close,
        "volume": ind_volume,
        "amount": ind_amount,
        "ind_groups": ind_groups
    }

def compute_huaxi_industry_factors(ind_prices):
    """Computes the 11 Huaxi volume-price factors at the industry level."""
    ind_open = ind_prices["open"]
    ind_high = ind_prices["high"]
    ind_low = ind_prices["low"]
    ind_close = ind_prices["close"]
    ind_volume = ind_prices["volume"]
    ind_amount = ind_prices["amount"]
    
    def ewma(df, span):
        return df.ewm(span=span, adjust=False).mean()
        
    # 1. SecondMomentum: w=20, w1=60, w2=20
    mean_close = ind_close.rolling(60).mean()
    ret_mean = (ind_close - mean_close) / (mean_close + 1e-8)
    diff_ret = ret_mean - ret_mean.shift(20)
    f_second_mom = ewma(diff_ret, 20)
    
    # 2. MomentumTermSpread: w1=60, w2=20
    mom_long = ind_close.pct_change(60, fill_method=None)
    mom_short = ind_close.pct_change(20, fill_method=None)
    f_mom_spread = mom_long - mom_short
    
    # 3. AmountVolatility: w=20
    f_amt_vol = -ind_amount.rolling(20).std()
    
    # 4. VolumeVolatility: w=20
    f_vol_vol = -ind_volume.rolling(20).std()
    
    # 5. TurnoverChange: w1=120, w2=20
    f_turnover_chg = ind_volume.rolling(120).mean() / (ind_volume.rolling(20).mean() + 1e-8)
    
    # 6. NetPosition: w=20
    ratio_pos = (ind_close - ind_low) / (ind_high - ind_close + 1e-8)
    f_net_pos = -ratio_pos.rolling(20).sum()
    
    # 7. PositionChange: w1=60, w2=20
    val_pos_chg = ind_volume * ((ind_close - ind_low) - (ind_high - ind_close)) / (ind_high - ind_low + 1e-8)
    f_pos_chg = ewma(val_pos_chg, 60) - ewma(val_pos_chg, 20)
    
    # 8. VolumePriceRankCorr: w=20 (using cross-sectional ranks)
    close_r = ind_close.rank(axis=1, pct=True)
    vol_r = ind_volume.rank(axis=1, pct=True)
    f_vp_rank_corr = -vectorized_rolling_corr(close_r, vol_r, window=20)
    
    # 9. VolumePriceCorr: w=20
    f_vp_corr = -vectorized_rolling_corr(ind_close, ind_volume, window=20)
    
    # 10. FirstOrderDivergence: w=20
    vol_growth = ind_volume / ind_volume.shift(1) - 1.0
    intraday_ret = ind_close / ind_open - 1.0
    vol_growth_r = vol_growth.rank(axis=1, pct=True)
    intraday_ret_r = intraday_ret.rank(axis=1, pct=True)
    f_fod_corr = -vectorized_rolling_corr(vol_growth_r, intraday_ret_r, window=20)
    
    # 11. VolumeAmplitudeCoMovement: w=20
    amplitude = ind_high / ind_low - 1.0
    amplitude_r = amplitude.rank(axis=1, pct=True)
    f_vac_corr = vectorized_rolling_corr(vol_growth_r, amplitude_r, window=20)
    
    return {
        "second_mom": f_second_mom,
        "mom_spread": f_mom_spread,
        "amt_vol": f_amt_vol,
        "vol_vol": f_vol_vol,
        "turnover_chg": f_turnover_chg,
        "net_pos": f_net_pos,
        "pos_chg": f_pos_chg,
        "vp_rank_corr": f_vp_rank_corr,
        "vp_corr": f_vp_corr,
        "fod_corr": f_fod_corr,
        "vac_corr": f_vac_corr
    }

def run_huaxi_rotation_strategy(config=StrategyConfig(), use_timing=False, use_bond_rotation=False):
    """Runs M3 Strategy v1.3 / v1.4 with Huaxi 11 factors."""
    # 1. Load data
    prices = load_all_daily_price_fields()
    close = prices["close"]
    amount = prices["amount"]
    raw_close = prices["raw_close"]
    
    # Clean dates
    clean_dates = close.index[close.index < "2026-06-10"]
    for k in ["open", "high", "low", "close", "volume", "amount", "raw_close"]:
        prices[k] = prices[k].reindex(clean_dates)
    close = prices["close"]
    amount = prices["amount"]
    raw_close = prices["raw_close"]
    
    price_panel = PricePanel(close=close, volume=amount*0, amount=amount, raw_close=raw_close)
    
    # Load quality fields for stock selection (if stock rotation is requested)
    panels_growth = load_clean_panels_with_growth()
    roe = panels_growth["roe"].reindex(clean_dates)
    npy = panels_growth["npy"].reindex(clean_dates)
    
    # 2. Industry Mapping & Aggregation
    stock_to_ind = load_industry_groups()
    ind_prices = aggregate_industry_all_fields(prices, stock_to_ind)
    ind_groups = ind_prices["ind_groups"]
    
    # 3. Compute 11 Huaxi Factors
    factors = compute_huaxi_industry_factors(ind_prices)
    
    # 4. Generate scheduled weights
    start_idx = 120
    rebal_dates = clean_dates[start_idx::config.rebalance_days]
    scheduled_weights = {}
    
    # Optional CPV factor for stock selection version
    cpv = vectorized_rolling_corr(close, amount, window=20)
    cpv_raw_r = cpv.rank(axis=1, pct=True, na_option="bottom")
    m_liq = 1.0 / (amount.rolling(20).mean() + 1.0)
    m_liq_r = m_liq.rank(axis=1, pct=True, na_option="bottom")
    cpv_r = (cpv_raw_r * m_liq_r).rank(axis=1, pct=True, na_option="bottom")
    
    for i in range(len(rebal_dates)):
        dt_current = rebal_dates[i]
        pos = close.index.get_loc(dt_current)
        if pos + 1 >= len(close.index):
            continue
        effective_date = close.index[pos + 1]
        
        # Intersect industries with valid data
        valid_inds = None
        for name, factor_df in factors.items():
            val_df = factor_df.loc[dt_current].dropna()
            if valid_inds is None:
                valid_inds = val_df.index
            else:
                valid_inds = valid_inds.intersection(val_df.index)
                
        if len(valid_inds) == 0:
            continue
            
        # Cross-sectional ranking of the 11 factors
        factor_ranks = []
        for name, factor_df in factors.items():
            factor_val = factor_df.loc[dt_current, valid_inds]
            rank_val = factor_val.rank(pct=True)
            factor_ranks.append(rank_val)
            
        # Composite score
        score = sum(factor_ranks)
        selected_inds = score.nlargest(config.top_k_industries).index.tolist()
        
        selected_stocks = []
        for ind in selected_inds:
            codes = ind_groups.get(ind, [])
            active_codes = [c for c in codes if c in close.columns and not pd.isna(close.loc[dt_current, c])]
            if len(active_codes) == 0:
                continue
                
            if config.version in ["v1.0", "v1.3"]:
                # ETF: Equal-weight active stocks in the selected industries
                selected_stocks.extend(active_codes)
            else:
                # Stock version: Top N stocks by Quality + CPV
                r_val = roe.loc[dt_current, active_codes].fillna(-100.0)
                n_val = npy.loc[dt_current, active_codes].fillna(-100.0)
                stock_score = r_val.rank(pct=True) + n_val.rank(pct=True)
                
                if config.w_cpv > 0:
                    c_val = cpv_r.loc[dt_current, active_codes].fillna(0.5)
                    stock_score = stock_score - config.w_cpv * c_val.rank(pct=True)
                    
                top_stocks = stock_score.nlargest(config.top_n_stocks).index.tolist()
                selected_stocks.extend(top_stocks)
                
        if len(selected_stocks) > 0:
            weight_val = 1.0 / len(selected_stocks)
            scheduled_weights[effective_date] = pd.Series(weight_val, index=selected_stocks)
            
    # 5. Cost Model
    if config.cost_mode == "etf":
        cost_model = CostModel(buy_cost=0.0005, sell_cost=0.0005, financing_rate=0.0)
    else:
        cost_model = CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.0)
        
    # 6. Run Engine with Optional Timing
    engine_config = BacktestConfig(
        start=config.start,
        cost=cost_model,
        leverage=1.0
    )
    engine = BacktestEngine(prices=price_panel, config=engine_config)
    
    timing_signal = None
    if use_timing:
        timing_raw, _, timing_dist = small_cap_timing(close, amount, ma_window=16)
        timing_signal = timing_raw
        
    signal = Signal(weights=scheduled_weights, timing=timing_signal, family="industry-huaxi-rotation", version=config.version)
    result = engine.run(signal)
    
    r_final = result.returns
    if use_timing and use_bond_rotation:
        # Load bonds
        bond_ret = load_bond_returns("511010")
        common = r_final.index.intersection(bond_ret.index).intersection(timing_signal.index)
        r_stock_aligned = r_final.reindex(common).fillna(0.0)
        bond_ret_aligned = bond_ret.reindex(common).fillna(0.0)
        bull_mask = timing_signal.reindex(common).fillna(False)
        r_final = pd.Series(np.where(bull_mask, r_stock_aligned, bond_ret_aligned), index=common)
        
    return {
        "returns": r_final,
        "close": close,
        "scheduled_weights": scheduled_weights,
        "engine_result": result,
    }

def print_metrics(label, returns):
    nav = (1 + returns.fillna(0)).cumprod()
    ann_ret = nav.iloc[-1] ** (252 / len(returns)) - 1
    max_dd = (nav / nav.cummax() - 1).min()
    vol = returns.std() * np.sqrt(252)
    sharpe = ann_ret / vol if vol > 0 else 0.0
    calmar = ann_ret / abs(max_dd) if max_dd < 0 else 0.0
    print(f"  {label}:")
    print(f"    Annualized Return: {ann_ret:+.2%}")
    print(f"    Volatility: {vol:.2%}")
    print(f"    Sharpe Ratio: {sharpe:.2f}")
    print(f"    Max Drawdown: {max_dd:.2%}")
    print(f"    Calmar Ratio: {calmar:.2f}")

def main():
    print("=" * 60)
    print("Running Backtest for Huaxi 11-Factor Industry Rotation Strategy")
    print("=" * 60)
    
    # 1. Backtest v1.3 (Huaxi ETF version, no timing)
    print("\n[1/4] Backtesting v1.3 (Huaxi ETF, No Timing, 2012-2026)...")
    config_v13 = StrategyConfig(
        family="industry-huaxi-rotation",
        version="v1.3",
        start="2012-01-01",
        rebalance_days=20,
        top_k_industries=10,
        cost_mode="etf"
    )
    res_v13 = run_huaxi_rotation_strategy(config_v13, use_timing=False)
    print_metrics("v1.3 (No Timing)", res_v13["returns"])
    
    # 2. Backtest v1.3 + Timing + Bond Rotation
    print("\n[2/4] Backtesting v1.3 (Huaxi ETF + MA16 Timing + 511010 Bond Rotation, 2012-2026)...")
    res_v13_rot = run_huaxi_rotation_strategy(config_v13, use_timing=True, use_bond_rotation=True)
    print_metrics("v1.3 + Timing + Bond Rotation", res_v13_rot["returns"])
    
    # 3. Backtest v1.4 (Huaxi Stock version, no timing)
    print("\n[3/4] Backtesting v1.4 (Huaxi Stock, No Timing, 2012-2026)...")
    config_v14 = StrategyConfig(
        family="industry-huaxi-rotation",
        version="v1.4",
        start="2012-01-01",
        rebalance_days=20,
        top_k_industries=10,
        top_n_stocks=2,
        w_cpv=0.5,
        cost_mode="stock"
    )
    res_v14 = run_huaxi_rotation_strategy(config_v14, use_timing=False)
    print_metrics("v1.4 (No Timing)", res_v14["returns"])
    
    # 4. Backtest v1.4 + Timing + Bond Rotation
    print("\n[4/4] Backtesting v1.4 (Huaxi Stock + MA16 Timing + 511010 Bond Rotation, 2012-2026)...")
    res_v14_rot = run_huaxi_rotation_strategy(config_v14, use_timing=True, use_bond_rotation=True)
    print_metrics("v1.4 + Timing + Bond Rotation", res_v14_rot["returns"])

if __name__ == "__main__":
    main()
