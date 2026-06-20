import pandas as pd
import numpy as np
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from strategies.small_cap import load_price_panels
from factors.small_cap import small_cap_factor
from factors.fundamental import revenue_yoy
from factors.momentum import mom_n
from factors.utils import safe_zscore, mad_clip
from lake.load_lake import load_daily_basic_panel

def main():
    print("Loading price panels...")
    close, volume, amount = load_price_panels("2018-01-01")
    trade_dates = close.index
    codes = list(close.columns)

    print("Loading daily basic panel (total_mv)...")
    db_panel = load_daily_basic_panel(trade_dates, codes=codes, fields=["total_mv"])
    total_mv = db_panel["total_mv"] # date x code (in 10k CNY)

    print("Computing factors...")
    # 1. small_cap
    f_size = small_cap_factor(amount, window=60)
    
    # 2. illiquidity
    ret = close.pct_change(fill_method=None).abs()
    illiq = (ret / (amount.replace(0, np.nan) + 1)).rolling(20).mean()
    f_illiq = safe_zscore(mad_clip(illiq))

    # 3. fundamental_momentum
    mom = mom_n(close, 60)
    rev = revenue_yoy(close)
    f_fund_mom = safe_zscore(mad_clip(0.5 * safe_zscore(mad_clip(mom)) + 0.5 * safe_zscore(mad_clip(rev))))

    factors = {
        "Small Cap Size": f_size,
        "Illiquidity": f_illiq,
        "Fundamental Momentum": f_fund_mom
    }

    # Analyze selected stocks
    top_n = 25
    rebalance_days = 20
    fdates = list(close.index[::rebalance_days])

    results = []
    for name, factor in factors.items():
        mv_list = []
        amount_list = []
        for d in fdates:
            if d not in factor.index:
                continue
            f_val = factor.loc[d].dropna()
            active = close.loc[d].dropna().index
            f_val = f_val.reindex(active).dropna()
            if len(f_val) < top_n:
                continue
            selected = f_val.nlargest(top_n).index
            
            # Get total_mv and trading amount for the selected stocks on day d
            mv_val = total_mv.loc[d, selected].dropna()
            amt_val = amount.loc[d, selected].dropna()
            
            mv_list.extend(mv_val.tolist())
            amount_list.extend(amt_val.tolist())
            
        mv_arr = np.array(mv_list)
        amt_arr = np.array(amount_list)
        
        # total_mv is in 10k CNY, so total_mv / 10000 is in 100 Million (亿) CNY
        # amount is volume(手) * 100 * raw_close, which is in Yuan (CNY) since volume is hands, so volume * 100 is shares.
        # Let's show Median Market Cap in 亿 CNY, Average Market Cap in 亿 CNY
        # And ADV in 万 CNY (amount / 10000.0)
        
        results.append({
            "Strategy": name,
            "Median MV (亿 CNY)": round(np.median(mv_arr) / 10000.0, 3),
            "Mean MV (亿 CNY)": round(np.mean(mv_arr) / 10000.0, 3),
            "Median ADV (万 CNY)": round(np.median(amt_arr) / 10000.0, 2),
            "Mean ADV (万 CNY)": round(np.mean(amt_arr) / 10000.0, 2)
        })

    df_res = pd.DataFrame(results)
    print("\n" + "="*80)
    print("Capacity & Liquidity Comparison (2018-2026)")
    print("="*80)
    print(df_res.to_markdown(index=False))
    print("="*80)

if __name__ == "__main__":
    main()
