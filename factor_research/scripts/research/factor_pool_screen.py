"""因子池批量验真 + 真 alpha 组合(个人级可实战组合 v0)。

复用 strategy_truth_screen 的电池(L0 去 overlay 归因 / 独立 IC+t / 容量)。
1. 一次载面板,跑一池价量因子(全市场 top25 等权 20D,小盘倾斜固有)。
2. 每因子出判决:真 alpha = L0 裸因子夏普≥0.8 且独立 IC 方向对、|IC|≥0.02。
3. 通过验真的取 L0 收益,算两两相关 + 逆波动率组合 + 组合层 MA16 overlay → 看组合回撤能否压进满意线。
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
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "research"))

import numpy as np
import pandas as pd

from core.engine import PricePanel, CostModel
from engine.metrics import metrics
from strategy_truth_screen import _run, independent_ic, capacity_est
from illiq_largecap_audit import build_weights

START = "2018-01-01"
COST = CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.0)


def factor_registry(close, amount):
    """name -> (factor_df, direction). 全部仅用 close/amount,方向=+1 表示高值买入。"""
    ret = close.pct_change(fill_method=None)
    adv = amount.rolling(20).mean()
    reg = {}
    reg["illiq_amihud20"] = ((ret.abs() / (amount + 1.0)).rolling(20).mean(), +1)
    reg["size_neg_adv"] = (-np.log(adv + 1.0), +1)                       # 小盘
    reg["reversal_20"] = (-close.pct_change(20, fill_method=None), +1)   # 短期反转
    reg["reversal_5"] = (-close.pct_change(5, fill_method=None), +1)
    reg["momentum_120_20"] = (close.shift(20) / close.shift(120) - 1.0, +1)  # 12-1 动量
    reg["lowvol_20"] = (-ret.rolling(20).std(), +1)                     # 低波
    reg["vol_neglect"] = (-(adv / (amount.rolling(120).mean() + 1.0)), +1)  # 成交冷落
    return reg


def screen_factor(name, factor, direction, prices, timing):
    weights = build_weights(factor, prices.close, prices.amount, top_n=25, rebal=20, universe=10**9)
    if weights.empty:
        return None, None
    r_L0 = _run(prices, weights, None, 1.0, COST, START).dropna()
    r_L1 = _run(prices, weights, timing, 1.0, COST, START).dropna()
    m0, m1 = metrics(r_L0), metrics(r_L1)
    ic = independent_ic(factor if direction > 0 else -factor, prices.close)
    cap = capacity_est(prices, weights)
    ic_ok = (ic["ic_mean"] > 0) and abs(ic["ic_mean"]) >= 0.02
    real_alpha = (m0["sharpe"] >= 0.8) and ic_ok
    row = {
        "name": name,
        "L0_annual": round(m0["annual"], 4), "L0_sharpe": round(m0["sharpe"], 3),
        "L0_maxdd": round(m0["maxdd"], 4),
        "L1_sharpe": round(m1["sharpe"], 3), "L1_maxdd": round(m1["maxdd"], 4),
        "ic_mean": round(ic["ic_mean"], 4), "ic_t": round(ic["t_stat"], 2),
        "cap_亿": cap.get("capacity_aum_亿"),
        "real_alpha": bool(real_alpha),
    }
    return row, (r_L0 if real_alpha else None)


def main():
    from strategies.small_cap import load_price_panels
    from factors.small_cap import small_cap_timing
    buf = io.StringIO()
    with redirect_stdout(buf):
        close, volume, amount = load_price_panels(START)
        timing, _, _ = small_cap_timing(close, amount, 16)
    prices = PricePanel(close=close, volume=volume, amount=amount)

    reg = factor_registry(close, amount)
    rows, winners = [], {}
    for name, (f, d) in reg.items():
        row, l0 = screen_factor(name, f, d, prices, timing)
        if row is None:
            continue
        rows.append(row)
        if l0 is not None:
            winners[name] = l0

    print("="*92)
    print(f"{'因子':18} {'L0年化':>8} {'L0夏普':>7} {'L0回撤':>8} {'L1夏普':>7} {'IC':>7} {'IC_t':>6} {'容量亿':>6} {'真alpha':>7}")
    print("-"*92)
    for r in sorted(rows, key=lambda x: -x["L0_sharpe"]):
        print(f"{r['name']:18} {r['L0_annual']:+8.1%} {r['L0_sharpe']:7.2f} {r['L0_maxdd']:+8.1%} "
              f"{r['L1_sharpe']:7.2f} {r['ic_mean']:+7.3f} {r['ic_t']:6.2f} "
              f"{str(r['cap_亿']):>6} {'✅' if r['real_alpha'] else '✗':>6}")

    # ---- 组合:通过验真的真 alpha,逆波动率权重 ----
    if len(winners) >= 2:
        df = pd.DataFrame(winners).dropna()
        corr = df.corr()
        inv_vol = 1.0 / df.std()
        w = inv_vol / inv_vol.sum()
        port = (df * w).sum(axis=1)
        pm = metrics(port)
        # 组合层 MA16 overlay(熊市空仓)
        port_t = pd.Series(np.where(timing.reindex(port.index).fillna(False), port, 0.0), index=port.index)
        pmt = metrics(port_t.dropna())

        print("\n" + "="*60)
        print(f"真 alpha 组合(逆波动率权重,{len(winners)}腿): {list(winners)}")
        print("逆波动率权重:", {k: round(float(v), 3) for k, v in w.items()})
        print("\n两两相关(L0):")
        print(corr.round(2).to_string())
        print(f"\n组合 L0(无择时): 年化{pm['annual']:+.1%} 夏普{pm['sharpe']:.2f} 回撤{pm['maxdd']:+.1%} Calmar{pm['calmar']:.2f}")
        print(f"组合 +MA16择时 : 年化{pmt['annual']:+.1%} 夏普{pmt['sharpe']:.2f} 回撤{pmt['maxdd']:+.1%} Calmar{pmt['calmar']:.2f}")
        out = {"factors": rows, "winners": list(winners),
               "inv_vol_weights": {k: float(v) for k, v in w.items()},
               "corr": corr.round(3).to_dict(),
               "portfolio_L0": {k: pm[k] for k in ("annual","sharpe","maxdd","calmar")},
               "portfolio_timed": {k: pmt[k] for k in ("annual","sharpe","maxdd","calmar")}}
    else:
        out = {"factors": rows, "winners": list(winners), "note": "真alpha不足2腿,无法组合"}

    with open("scratch/factor_pool_screen.json", "w") as f:
        json.dump(out, f, ensure_ascii=False, indent=2, default=float)


if __name__ == "__main__":
    main()
