"""industry-neglect-rotation v1.3 归因分层审计(查是否又是 MA16 择时伪装因子 alpha)。

v1.3 = 华西11因子选 top10 行业(ETF:行业内全股等权) + MA16 择时 + 511010 债轮动。
复用 run_industry_rotation_strategy 拿 scheduled_weights+timing(因子逻辑不改),
再自己重跑引擎切层 + 套债,口径与台账一致(ETF 成本 0.0005 双边)。

分层:
  L0 裸因子轮动(无择时/无债)  → 因子本身 alpha
  L1 +MA16 择时(熊市空仓)
  L2 +511010 债轮动(熊市轮债) = 完整 v1.3(台账头条 21.27%/夏普1.28)
判据:若 L0 远低于入册线(年化>15%/回撤<20%)、正收益靠 L1/L2 → 同 illiq/TOC 的择时伪装母题。
"""
import io
import os
import sys
import json
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path("/Users/kiki/astcok/factor_research")
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from engine.metrics import metrics, compute_hit
import strategies.industry_rotation as ir

ETF_COST = CostModel(buy_cost=0.0005, sell_cost=0.0005, financing_rate=0.0)


def run_engine(prices, weights, timing):
    cfg = BacktestConfig(start="2012-01-01", cost=ETF_COST, leverage=1.0)
    return BacktestEngine(prices=prices, config=cfg).run(
        Signal(weights=weights, timing=timing)).returns


def main():
    cfg = ir.StrategyConfig(version="v1.3")
    buf = io.StringIO()
    with redirect_stdout(buf):
        res = ir.run_industry_rotation_strategy(cfg)
        # 重建 price_panel(与函数内一致:stock-level close/amount,clean_dates)
        prices_all = ir.load_all_daily_price_fields()
        clean = prices_all["close"].index[prices_all["close"].index < "2026-06-10"]
        close = prices_all["close"].reindex(clean)
        amount = prices_all["amount"].reindex(clean)
        raw_close = prices_all["raw_close"].reindex(clean)
        bond_ret = ir.load_bond_returns("511010")

    panel = PricePanel(close=close, volume=amount * 0, amount=amount, raw_close=raw_close)
    weights = res["scheduled_weights"]
    timing = res["timing"]

    # L0 无择时,L1 择时
    r_L0 = run_engine(panel, weights, None)
    r_L1 = run_engine(panel, weights, timing)

    # L2 = 套 511010 债轮动(熊市轮债),复刻 industry_rotation.py:388-395
    common = r_L1.index.intersection(bond_ret.index).intersection(timing.index)
    bull = timing.reindex(common).fillna(False).astype(bool)
    r_L2 = pd.Series(np.where(bull, r_L1.reindex(common).fillna(0.0),
                              bond_ret.reindex(common).fillna(0.0)), index=common)

    layers = {"L0_factor_only": r_L0, "L1_+MA16timing": r_L1, "L2_+bond(full_v1.3)": r_L2}
    out = {}
    for k, r in layers.items():
        m = metrics(r.dropna())
        out[k] = {x: m[x] for x in ("annual", "sharpe", "maxdd", "calmar", "hit", "n")}

    report = {"layers": out, "ledger_headline": {"annual": 0.2127, "sharpe": 1.28, "maxdd": -0.1754}}
    with open("scratch/industry_neglect_v13_audit.json", "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)

    print("=== industry-neglect-rotation v1.3 归因分层 ===")
    print(f"{'层':22} {'年化':>8} {'夏普':>7} {'回撤':>8} {'Calmar':>7} {'hit':>5}")
    for k, m in out.items():
        print(f"{k:22} {m['annual']:+8.2%} {m['sharpe']:7.2f} {m['maxdd']:+8.2%} {m['calmar']:7.2f} {str(m['hit']):>5}")
    print(f"\n台账头条(=L2): 年化+21.27% 夏普1.28 回撤-17.54%")
    l0 = out["L0_factor_only"]
    print(f"\n裸因子 L0 是否单体达标(年化>15% 且 回撤<20%): {compute_hit(l0['annual'], l0['maxdd'])}")


if __name__ == "__main__":
    main()
