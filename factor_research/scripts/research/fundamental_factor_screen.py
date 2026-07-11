"""基本面因子池验真(金库纪律)+ 与 illiquidity 相关性 → 找低相关第二腿。

北极星:小盘 illiquidity 已确认真 alpha,但单腿回撤高、与 size 同质。要组合,缺一个
与「小/不流动」**低相关**的真 alpha。本脚本在金库纪律下(搜索 <boundary)扫基本面源
(价值/质量/成长),严格 PIT(财务 ann_date ffill、估值用 daily_basic 不复权 pe/pb),
对每个出 L0 归因 + 独立 IC + 容量 + 金库样本外,并算与 illiq L0 的相关。
"""
import io
import os
import sys
import json
import hashlib
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
from engine.metrics import metrics, compute_hit
from strategy_truth_screen import _run, independent_ic, capacity_est
from illiq_largecap_audit import build_weights
from governance import holdout as HO
from lake.load_lake import load_fina_indicator_panel, load_daily_basic_panel

START = "2018-01-01"
COST = CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.0)


def clean(df):
    return df.replace([np.inf, -np.inf], np.nan)


def fundamental_factors(close, fina, db):
    """name -> (factor_df, direction). PIT:fina 已 ann_date ffill,db 不复权估值。"""
    reg = {}
    reg["value_ep_ttm"] = (clean(1.0 / db["pe_ttm"]), +1)        # 盈利收益率(便宜=买)
    reg["value_bp"] = (clean(1.0 / db["pb"]), +1)                # 账面收益率
    reg["value_sp_ttm"] = (clean(1.0 / db["ps_ttm"]), +1)        # 销售收益率
    reg["quality_roe"] = (clean(fina["roe"]), +1)                # 高质量
    reg["quality_npmargin"] = (clean(fina["netprofit_margin"]), +1)
    reg["growth_np_yoy"] = (clean(fina["netprofit_yoy"]), +1)    # 利润增速
    return reg


def screen(name, factor, direction, prices, timing):
    b = HO.boundary()
    weights = build_weights(factor, prices.close, prices.amount, top_n=25, rebal=20, universe=10**9)
    if weights.empty:
        return None, None
    L0f = _run(prices, weights, None, 1.0, COST, START)
    L1f = _run(prices, weights, timing, 1.0, COST, START)
    L0 = L0f[L0f.index < b].dropna()
    L1 = L1f[L1f.index < b].dropna()
    if len(L0) < 100:
        return None, None
    m0, m1 = metrics(L0), metrics(L1)
    ic = independent_ic(factor if direction > 0 else -factor, prices.close[prices.close.index < b])
    cap = capacity_est(prices, weights)
    data_fp = HO.current_data_fingerprint()
    spec_hash = hashlib.sha256(f"fund::{name}".encode()).hexdigest()
    ho = HO.validate_on_holdout(
        HO.candidate_identity(f"fund::{name}", spec_hash, data_fp),
        L1f,
        spec_hash=spec_hash,
        data_fingerprint=data_fp,
    )
    ic_ok = (ic["ic_mean"] > 0) and abs(ic["ic_mean"]) >= 0.02
    real_alpha = (m0["sharpe"] >= 0.8) and ic_ok
    ho_sh = ho.get("sharpe", 0) or 0
    row = {
        "name": name, "L0_annual": round(m0["annual"], 4), "L0_sharpe": round(m0["sharpe"], 3),
        "L0_maxdd": round(m0["maxdd"], 4), "ic_mean": round(ic["ic_mean"], 4), "ic_t": round(ic["t_stat"], 2),
        "cap_亿": cap.get("capacity_aum_亿"), "ho_sharpe": round(float(ho_sh), 2),
        "real_alpha": bool(real_alpha), "ho_ok": bool(ho_sh >= 0.6),
    }
    return row, (L0 if real_alpha else None)


def illiq_L0_search(prices, timing, b):
    amihud = (prices.close.pct_change(fill_method=None).abs() / (prices.amount + 1.0)).rolling(20).mean()
    w = build_weights(amihud, prices.close, prices.amount, top_n=25, rebal=20, universe=10**9)
    L0 = _run(prices, w, None, 1.0, COST, START)
    return L0[L0.index < b].dropna()


def main():
    from strategies.small_cap import load_price_panels
    from factors.small_cap import small_cap_timing
    buf = io.StringIO()
    with redirect_stdout(buf):
        close, volume, amount = load_price_panels(START)
        timing, _, _ = small_cap_timing(close, amount, 16)
        codes = list(close.columns)
        fina = load_fina_indicator_panel(close.index, codes=codes,
                                         fields=["roe", "netprofit_margin", "netprofit_yoy"])
        db = load_daily_basic_panel(close.index, codes=codes, fields=["pe_ttm", "pb", "ps_ttm"])
    prices = PricePanel(close=close, volume=volume, amount=amount)
    b = HO.boundary()

    reg = fundamental_factors(close, fina, db)
    rows, winners = [], {}
    for name, (f, d) in reg.items():
        row, l0 = screen(name, f, d, prices, timing)
        if row is None:
            continue
        rows.append(row)
        if l0 is not None:
            winners[name] = l0

    illiq_l0 = illiq_L0_search(prices, timing, b)

    print("="*100)
    print(f"基本面因子池(金库纪律,搜索 <{b.date()}):")
    print(f"{'因子':18} {'L0年化':>8} {'L0夏普':>7} {'L0回撤':>8} {'IC':>7} {'IC_t':>6} {'容量亿':>7} {'金库夏普':>7} {'真alpha':>7}")
    print("-"*100)
    for r in sorted(rows, key=lambda x: -x["L0_sharpe"]):
        print(f"{r['name']:18} {r['L0_annual']:+8.1%} {r['L0_sharpe']:7.2f} {r['L0_maxdd']:+8.1%} "
              f"{r['ic_mean']:+7.3f} {r['ic_t']:6.2f} {str(r['cap_亿']):>7} {r['ho_sharpe']:7.2f} "
              f"{'✅' if (r['real_alpha'] and r['ho_ok']) else '✗':>6}")

    # 与 illiquidity 相关性(L0 搜索窗)
    print("\n通过验真的因子 与 illiquidity L0 相关性(目标:低相关第二腿):")
    deployable = {k: v for k, v in winners.items()
                  if next(r for r in rows if r["name"] == k)["ho_ok"]}
    if deployable:
        for k, v in deployable.items():
            common = illiq_l0.index.intersection(v.index)
            c = illiq_l0.reindex(common).corr(v.reindex(common))
            tag = "✅低相关候选第二腿" if abs(c) < 0.5 else "同质(与illiq冗余)"
            print(f"  {k:18} corr(illiq)={c:+.2f}  {tag}")
    else:
        print("  无通过验真(真alpha且金库未崩)的基本面因子。")

    with open("scratch/fundamental_factor_screen.json", "w") as f:
        json.dump({"factors": rows, "deployable": list(deployable)}, f, ensure_ascii=False, indent=2, default=float)


if __name__ == "__main__":
    main()
