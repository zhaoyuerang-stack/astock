"""Scratch script to register strategy versions v3.0 and v3.1 into the ledger strategy_versions.json.
"""
import os
import sys
from pathlib import Path

# Set path
ROOT = Path("/Users/kiki/astcok/factor_research").resolve()
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from strategy_registry import register

def main():
    print("Registering strategy versions in ledger...")
    
    # 1. Register v3.0
    register(
        family="illiquidity",
        version="v3.0",
        desc="Amihud illiquidity 20d + PureTrend MA16 Band Timing + 511010 Bond Rotation",
        config={
            "factor": "Amihud illiquidity (|ret|/amount).rolling(20)",
            "timing": "PureTrend MA16 Band Timing (dynamic leverage 0-1.5x)",
            "rotation": "511010 Gov Bond ETF (in BEAR regime)",
            "top_n": 25,
            "rebal_days": 20
        },
        data_scope={
            "source": "data_lake",
            "period": "2018-2026",
            "wf_validated": True
        },
        metrics={
            "annual": 0.3703,
            "maxdd": -0.1249,
            "sharpe": 2.08,
            "calmar": 2.96,
            "hit": True
        },
        status="参考",
        notes="旧生产版本。已全区间压力测试 +37.0%/-12.5%/2.08，被 v3.1 替代。"
    )
    
    # 2. Register v3.1
    register(
        family="illiquidity",
        version="v3.1",
        desc="Amihud illiquidity 20d + Salience Veto 30% + PureTrend MA16 Band Timing + 511010 Bond Rotation",
        config={
            "factor": "Amihud illiquidity (|ret|/amount).rolling(20)",
            "veto": "Faded Salience Covariance (-ST_cov) bottom 30% excluded",
            "timing": "PureTrend MA16 Band Timing (dynamic leverage 0-1.5x)",
            "rotation": "511010 Gov Bond ETF (in BEAR regime)",
            "top_n": 25,
            "rebal_days": 20
        },
        data_scope={
            "source": "data_lake",
            "period": "2018-2026",
            "wf_validated": True
        },
        metrics={
            "annual": 0.3777,
            "maxdd": -0.1195,
            "sharpe": 2.12,
            "calmar": 3.16,
            "hit": True
        },
        status="在册",
        notes="当前 LIVE 生产版本。引入 30% 凸显性一票否决风控层后，相较 v3.0 实现了年化收益微增（+0.7%）、最大回撤缩减（从-12.5%降至-11.9%）与卡玛比率上升（从 2.96 升至 3.16）。"
    )
    
    print("Strategy versions registered successfully!")

if __name__ == "__main__":
    main()
