import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.engine import PricePanel
from strategies.small_cap import load_price_panels
from factors.alpha.builtins.illiq import AmihudIlliq
from factors.alpha import transforms
from lake.load_lake import load_daily_basic_panel, load_fundamental_panel

def main():
    close, volume, amount = load_price_panels("2018-01-01")
    from factors.alpha.base import FactorData
    data = FactorData(close=close, volume=volume, amount=amount)
    factor_df = AmihudIlliq(window=20).mad_clip(5).zscore().shift(1).compute(data)
    
    dates = factor_df.index
    codes = factor_df.columns
    
    db_basic = load_daily_basic_panel(dates, fields=["total_mv"])
    total_mv = db_basic.get("total_mv", pd.DataFrame())
    print("total_mv empty:", total_mv.empty)
    if not total_mv.empty:
        print("total_mv shape:", total_mv.shape)
        print("total_mv non-nan count:", total_mv.notna().sum().sum())
    
    db_fund = load_fundamental_panel(dates, fields=["industry"])
    industry = db_fund.get("industry", pd.DataFrame())
    print("industry empty:", industry.empty)
    if not industry.empty:
        print("industry shape:", industry.shape)
        print("industry non-nan count:", industry.notna().sum().sum())
        
    log_size = np.log(total_mv.replace(0, np.nan))
    
    # Check for a specific sample date
    dt = dates[len(dates)//2]
    y = factor_df.loc[dt].dropna()
    print("y length:", len(y))
    
    sz = log_size.loc[dt].reindex(y.index)
    print("sz non-nan:", sz.notna().sum())
    
    ind = pd.Series(dtype=object)
    if not industry.empty and dt in industry.index:
        ind = industry.loc[dt].reindex(y.index).fillna("Unknown")
    else:
        ind = pd.Series("Unknown", index=y.index)
    print("ind length:", len(ind))
    
    ind_dummies = pd.get_dummies(ind, drop_first=True)
    print("ind_dummies shape:", ind_dummies.shape)
    
    X = pd.DataFrame({"constant": 1.0, "size": sz})
    X = pd.concat([X, ind_dummies], axis=1).dropna()
    print("X shape after dropna:", X.shape)
    
    common = y.index.intersection(X.index)
    print("common length:", len(common))
    
    if len(common) >= 30:
        y_clean = y.loc[common].values
        X_clean = X.loc[common].values
        try:
            b, _, _, _ = np.linalg.lstsq(X_clean, y_clean, rcond=None)
            residuals = y_clean - X_clean @ b
            print("b shape:", b.shape)
            print("residuals shape:", residuals.shape)
            print("residuals non-nan:", np.isnan(residuals).sum())
        except Exception as e:
            print("OLS Error:", e)

if __name__ == "__main__":
    main()
