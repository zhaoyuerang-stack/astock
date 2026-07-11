"""救活 value:真 IC 但被构造杀死 → 试 4 种构造找「可交易 + 与 illiq 低相关」的第二腿。

诊断:value_bp/ep IC t>2.5(真信号)但等权 top25 L0 夏普~0.2。根因假设=size/流动性污染
(最便宜的扎堆小盘/特定行业=价值陷阱)。救法核心=size 中性化:既可能救活,又剥离与
illiquidity 相关的部分(一石二鸟)。全程金库纪律(搜索 <boundary)+ 量 corr(illiq)。

构造:
  C1 composite_top25     : ep/bp/sp 复合排名 top25(基线复合)
  C2 composite_top60     : 放宽到 top60(value 是宽效应)
  C3 size_neutral_top60  : 复合 value 对 ln(ADV) 截面残差化 → 纯 value
  C4 value_quality_top60 : 复合 value ∩ ROE>中位(避陷阱)
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
from engine.metrics import metrics
from strategy_truth_screen import _run, independent_ic, capacity_est
from illiq_largecap_audit import build_weights
from governance import holdout as HO
from lake.load_lake import load_fina_indicator_panel, load_daily_basic_panel

START = "2018-01-01"
COST = CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.0)


def _clean(df):
    return df.replace([np.inf, -np.inf], np.nan)


def _rank(df):
    return df.rank(axis=1, pct=True)


def size_neutralize(factor, size):
    """每个截面(行)对 size 做单元 OLS,返回残差 = 纯 factor(去 size)。"""
    fm = factor.sub(factor.mean(axis=1), axis=0)
    sm = size.sub(size.mean(axis=1), axis=0)
    denom = (sm ** 2).sum(axis=1).replace(0, np.nan)
    beta = (fm * sm).sum(axis=1) / denom
    return fm.sub(sm.mul(beta, axis=0))


def screen(name, factor, prices, timing, illiq_l0, top_n=25):
    b = HO.boundary()
    w = build_weights(factor, prices.close, prices.amount, top_n=top_n, rebal=20, universe=10**9)
    if w.empty:
        return None
    L0f = _run(prices, w, None, 1.0, COST, START)
    L1f = _run(prices, w, timing, 1.0, COST, START)
    L0 = L0f[L0f.index < b].dropna()
    L1 = L1f[L1f.index < b].dropna()
    if len(L0) < 100:
        return None
    m0, m1 = metrics(L0), metrics(L1)
    ic = independent_ic(factor, prices.close[prices.close.index < b])
    cap = capacity_est(prices, w)
    data_fp = HO.current_data_fingerprint()
    spec_hash = hashlib.sha256(f"valrescue::{name}".encode()).hexdigest()
    ho = HO.validate_on_holdout(
        HO.candidate_identity(f"valrescue::{name}", spec_hash, data_fp),
        L1f,
        spec_hash=spec_hash,
        data_fingerprint=data_fp,
    )
    ho_sh = float(ho.get("sharpe", 0) or 0)
    common = illiq_l0.index.intersection(L0.index)
    corr = float(illiq_l0.reindex(common).corr(L0.reindex(common)))
    ic_ok = ic["ic_mean"] > 0 and abs(ic["ic_mean"]) >= 0.02
    real = m0["sharpe"] >= 0.8 and ic_ok
    return {"name": name, "L0_annual": round(m0["annual"], 4), "L0_sharpe": round(m0["sharpe"], 3),
            "L0_maxdd": round(m0["maxdd"], 4), "ic_t": round(ic["t_stat"], 2),
            "cap_亿": cap.get("capacity_aum_亿"), "ho_sharpe": round(ho_sh, 2),
            "corr_illiq": round(corr, 2), "real_alpha": bool(real), "ho_ok": ho_sh >= 0.6,
            "pass": bool(real and ho_sh >= 0.6)}


def main():
    from strategies.small_cap import load_price_panels
    from factors.small_cap import small_cap_timing
    buf = io.StringIO()
    with redirect_stdout(buf):
        close, volume, amount = load_price_panels(START)
        timing, _, _ = small_cap_timing(close, amount, 16)
        codes = list(close.columns)
        db = load_daily_basic_panel(close.index, codes=codes, fields=["pe_ttm", "pb", "ps_ttm"])
        fina = load_fina_indicator_panel(close.index, codes=codes, fields=["roe"])
    prices = PricePanel(close=close, volume=volume, amount=amount)
    b = HO.boundary()
    adv = amount.rolling(20).mean()
    size = np.log(adv + 1.0)

    # 复合 value = ep/bp/sp 排名均值(越高越便宜)
    comp = (_rank(_clean(1.0 / db["pe_ttm"])) + _rank(_clean(1.0 / db["pb"]))
            + _rank(_clean(1.0 / db["ps_ttm"]))) / 3.0
    comp_sn = size_neutralize(comp, size)
    roe = _clean(fina["roe"])
    roe_med = roe.median(axis=1)
    comp_q = comp.where(roe.gt(roe_med, axis=0))  # value ∩ ROE>中位

    # illiq L0(搜索窗)做相关基准
    amihud = (close.pct_change(fill_method=None).abs() / (amount + 1.0)).rolling(20).mean()
    wi = build_weights(amihud, close, amount, top_n=25, rebal=20, universe=10**9)
    illiq_l0 = _run(prices, wi, None, 1.0, COST, START)
    illiq_l0 = illiq_l0[illiq_l0.index < b].dropna()

    constructions = [
        ("C1_composite_top25", comp, 25),
        ("C2_composite_top60", comp, 60),
        ("C3_size_neutral_top60", comp_sn, 60),
        ("C4_value_quality_top60", comp_q, 60),
    ]
    rows = [r for r in (screen(n, f, prices, timing, illiq_l0, top_n=tn) for n, f, tn in constructions) if r]

    print("="*104)
    print(f"value 救活实验(金库纪律,搜索 <{b.date()};illiq L0 作相关基准)")
    print(f"{'构造':24} {'L0年化':>8} {'L0夏普':>7} {'L0回撤':>8} {'IC_t':>6} {'容量亿':>7} {'金库夏普':>7} {'corr(illiq)':>11} {'通过':>5}")
    print("-"*104)
    for r in rows:
        print(f"{r['name']:24} {r['L0_annual']:+8.1%} {r['L0_sharpe']:7.2f} {r['L0_maxdd']:+8.1%} "
              f"{r['ic_t']:6.2f} {str(r['cap_亿']):>7} {r['ho_sharpe']:7.2f} {r['corr_illiq']:+11.2f} "
              f"{'✅' if r['pass'] else '✗':>5}")
    winners = [r for r in rows if r["pass"] and abs(r["corr_illiq"]) < 0.5]
    print("\n→ 低相关(|corr|<0.5)且通过验真的第二腿候选:",
          [r["name"] for r in winners] or "无")
    with open("scratch/value_rescue.json", "w") as f:
        json.dump({"constructions": rows, "low_corr_winners": [r["name"] for r in winners]},
                  f, ensure_ascii=False, indent=2, default=float)


if __name__ == "__main__":
    main()
