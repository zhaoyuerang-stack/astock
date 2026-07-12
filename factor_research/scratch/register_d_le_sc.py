import os
import sys
from pathlib import Path

# Align to project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from strategy_registry import register_family, register

def main():
    # Register family
    register_family(
        "d-le-sc-hedged", "有向似然谱聚类领先滞后对冲策略",
        hypothesis="利用日内/隔夜收益分解与有向似然估计谱聚类（d-LE-SC），构建 Leader-Lagger 领先-滞后网络。做多受 Leader 引导、预期日内收益最高的 Lagger 股票，对冲 Beta，捕捉日内/隔夜信息外溢超额。",
        regime="信息流传导顺畅、隔夜投机与日间修正效应明显的市场环境；月频/周频对 Top 25 股票进行轮动对冲。",
        decay_signal="Leader 与 Lagger 组别分类混沌（eta 接近 0.5）/ 隔夜投机效应消失 / 日度换手成本完全吞噬超额",
        status="active"
    )

    # Register v1.0 (academic baseline, zero cost)
    register(
        "d-le-sc-hedged", "v1.0", "学术理论版：日频调仓+零交易成本",
        config={
            "network_type": "daytime_lead_overnight",
            "correlation_method": "spearman",
            "rebalance_days": 1,
            "direction": 1,
            "top_n": 25,
            "cost": {"buy": 0.0, "sell": 0.0, "hedge_cost_annual": 0.0}
        },
        data_scope={"source": "data_lake", "period": "2023-2026", "survivorship_bias": False},
        metrics={"annual": 0.1394, "maxdd": -0.0931, "sharpe": 1.23, "calmar": 1.50, "hit": False},
        status="参考",
        notes="❌学术理论版：日频调仓在零成本下夏普达 1.23，但未考虑摩擦成本。实际执行会因年换手率 >300 倍而导致严重亏损（净回报 -64.37%）。"
    )

    # Register v1.1 (realistic low frequency version)
    register(
        "d-le-sc-hedged", "v1.1", "实盘优化版：慢速 20 日调仓+标准摩擦成本",
        config={
            "network_type": "preclose_lead_close",
            "correlation_method": "pearson",
            "rebalance_days": 20,
            "direction": -1,
            "top_n": 25,
            "cost": {"buy": 0.00225, "sell": 0.00275, "hedge_cost_annual": 0.015}
        },
        data_scope={"source": "data_lake", "period": "2023-2026", "survivorship_bias": False},
        metrics={"annual": 0.0511, "maxdd": -0.2616, "sharpe": 0.33, "calmar": 0.20, "hit": False},
        status="参考",
        notes="✅考虑标准交易摩擦与 1.5% 对冲成本后的实盘优化版（引入了 Top 25/Buf 50 滞后秩缓冲控制换手）。调仓为 20 日（年化换手 20.65 倍），净超额年化 +5.11%，夏普 0.33。由于单体夏普较低，MVO Spanning 检验分配权重为 0%，归为参考档。"
    )
    print("Successfully registered family 'd-le-sc-hedged' and its versions in strategy_versions.json!")

if __name__ == "__main__":
    main()
