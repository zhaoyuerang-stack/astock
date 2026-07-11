"""illiquidity-large-cap v1.0 独立审计:归因分层 + 自有宇宙 9-Gate(IC/DSR/PBO)。

动机:台账条目=拼装(净值来自无 veto 的 Top800 脚本;IC/DSR 照抄小盘版;config 虚标 veto)。
本脚本在 Top-800 自己的宇宙独立重算,口径全透明:
  归因分层(long-only top25, 20D):
    L0 裸因子(无择时/无杠杆/无veto)  → 因子本身 alpha
    L1 +MA16 择时
    L2 +杠杆1.25
    L3 +salience veto(剔底30%)        → 台账声称但生成码没用的层,测它是否真有用
  独立统计:Top800 截面 IC / IC-IR / 单调性;各层 Sharpe 喂 canonical DSR(诚实 n_trials 曲线);
           候选族 PBO(CSCV)。
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
from scipy.stats import spearmanr

from strategies.small_cap import load_price_panels
from core.engine import Signal, PricePanel, BacktestConfig, BacktestEngine, CostModel
from engine.metrics import metrics
from factors.veto import salience_covariance_veto
from core.analysis.walk_forward import deflated_sharpe, pbo_cscv

TOP_N, REBAL, UNIV = 25, 20, 800
COST = CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.065)


def build_weights(factor, close, amount, veto_score=None, veto_frac=0.30,
                  top_n=TOP_N, rebal=REBAL, universe=UNIV):
    adv = amount.rolling(20).mean()
    fdates = factor.dropna(how="all").index.intersection(close.index)
    rows = []
    for rd in list(fdates[::rebal]):
        pos = close.index.get_loc(rd)
        if pos + 1 >= len(close.index):
            continue
        effective = close.index[pos + 1]
        f = factor.loc[rd].reindex(close.loc[rd].dropna().index).dropna()
        adv_day = adv.loc[rd].reindex(f.index).dropna()
        if len(adv_day) == 0:
            continue
        pool = adv_day.rank(ascending=False) <= universe
        f = f.reindex(pool[pool].index).dropna()
        if veto_score is not None and rd in veto_score.index:
            vs = veto_score.loc[rd].reindex(f.index).dropna()
            if len(vs) > top_n:
                keep = vs.rank(ascending=False) > (veto_frac * len(vs))  # 剔底 veto_frac
                f = f.reindex(keep[keep].index).dropna()
        if len(f) < top_n:
            continue
        sel = f.nlargest(top_n).index
        rows.append(pd.Series(1.0 / top_n, index=sel, name=effective))
    return pd.DataFrame(rows).fillna(0.0)


def run(prices, weights, timing, leverage):
    cfg = BacktestConfig(start="2018-01-01", cost=COST, leverage=leverage)
    return BacktestEngine(prices=prices, config=cfg).run(
        Signal(weights=weights, timing=timing)).returns


def ic_stats(factor, close, amount, universe=UNIV, rebal=REBAL, fwd=REBAL):
    """Top800 宇宙截面 IC:factor vs 前向 fwd 日收益。"""
    adv = amount.rolling(20).mean()
    fdates = factor.dropna(how="all").index.intersection(close.index)
    fwd_ret = close.shift(-fwd) / close - 1.0
    ics = []
    for rd in list(fdates[::rebal]):
        pos = close.index.get_loc(rd)
        if pos + fwd >= len(close.index):
            continue
        f = factor.loc[rd].reindex(close.loc[rd].dropna().index).dropna()
        adv_day = adv.loc[rd].reindex(f.index).dropna()
        pool = adv_day.rank(ascending=False) <= universe
        f = f.reindex(pool[pool].index).dropna()
        y = fwd_ret.loc[rd].reindex(f.index)
        ok = f.notna() & y.notna()
        if ok.sum() >= 30:
            ic, _ = spearmanr(f[ok], y[ok])
            if not np.isnan(ic):
                ics.append(ic)
    ics = np.array(ics)
    return {"ic_mean": float(ics.mean()), "ic_ir": float(ics.mean() / ics.std()) if ics.std() else 0.0,
            "ic_win": float((ics > 0).mean()), "n_ic": len(ics)}


def main():
    buf = io.StringIO()
    with redirect_stdout(buf):
        close, volume, amount = load_price_panels("2018-01-01")
    prices = PricePanel(close=close, volume=volume, amount=amount)

    amihud = (close.pct_change(fill_method=None).abs() / (amount + 1.0)).rolling(20).mean()
    veto = salience_covariance_veto(close)

    mkt = (1 + close.pct_change(fill_method=None).fillna(0.0).mean(axis=1)).cumprod()
    timing = (mkt > mkt.rolling(16).mean()).astype(float)
    flat = pd.Series(1.0, index=timing.index)  # 无择时=恒满仓

    w = build_weights(amihud, close, amount)
    w_veto = build_weights(amihud, close, amount, veto_score=veto)

    # 归因分层
    layers = {
        "L0_factor_only": run(prices, w, flat, 1.0),
        "L1_+MA16timing": run(prices, w, timing, 1.0),
        "L2_+lev1.25":    run(prices, w, timing, 1.25),
        "L3_+veto30pct":  run(prices, w_veto, timing, 1.25),
    }
    attrib = {k: {m: metrics(v)[m] for m in ("annual", "sharpe", "maxdd", "calmar", "skew")}
              for k, v in layers.items()}

    # 独立 IC
    ic = ic_stats(amihud, close, amount)

    # DSR 诚实 n_trials 曲线(用 L2 头条层)
    head = layers["L2_+lev1.25"].dropna()
    hm = metrics(head)
    dsr_curve = {}
    for nt in [1, 6, 24, 96]:
        rep = deflated_sharpe(observed_sr=hm["sharpe"], n_trials=nt, n_periods=hm["n"],
                              skew=hm["skew"], kurt=hm["kurtosis_excess"] + 3.0, annualized=True)
        dsr_curve[nt] = {"p": round(rep["p_value"], 4), "sig": rep["significant_05"]}

    # PBO:候选族(宇宙×择时×veto)
    cand = {
        "u800_t_nov": layers["L1_+MA16timing"],
        "u800_t_veto": run(prices, w_veto, timing, 1.0),
        "u800_notime": layers["L0_factor_only"],
        "u300_t": run(prices, build_weights(amihud, close, amount, universe=300), timing, 1.0),
        "u300_notime": run(prices, build_weights(amihud, close, amount, universe=300), flat, 1.0),
        "u500_t": run(prices, build_weights(amihud, close, amount, universe=500), timing, 1.0),
    }
    cand_df = pd.DataFrame({k: v for k, v in cand.items()}).dropna()
    try:
        pbo_res = pbo_cscv(cand_df, n_splits=10)
        pbo_val = float(pbo_res.get("pbo", pbo_res) if isinstance(pbo_res, dict) else pbo_res)
    except Exception as e:
        pbo_val = f"err:{e}"

    report = {"attribution": attrib, "independent_ic_top800": ic,
              "ledger_copied_ic": {"ic_mean": 0.0779, "ic_ir": 0.126},
              "dsr_honest_curve": dsr_curve, "pbo_candidate_family": pbo_val,
              "head_sharpe": hm["sharpe"], "head_annual": hm["annual"]}
    with open("scratch/illiq_largecap_audit.json", "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)

    print("=== 归因分层(Top800, long-only) ===")
    print(f"{'层':18} {'年化':>8} {'夏普':>7} {'回撤':>8} {'Calmar':>7} {'skew':>6}")
    for k, m in attrib.items():
        print(f"{k:18} {m['annual']:+8.1%} {m['sharpe']:7.2f} {m['maxdd']:+8.1%} {m['calmar']:7.2f} {m['skew']:+6.2f}")
    print(f"\n=== 独立 IC(Top800 自有宇宙) ===")
    print(f"  本脚本: ic_mean={ic['ic_mean']:+.4f} ic_ir={ic['ic_ir']:.3f} win={ic['ic_win']:.1%} (n={ic['n_ic']})")
    print(f"  台账照抄: ic_mean=+0.0779 ic_ir=0.126  ← 若差异大=证据照抄坐实")
    print(f"\n=== DSR 诚实 n_trials(头条 L2 夏普={hm['sharpe']:.2f}) ===")
    for nt, r in dsr_curve.items():
        print(f"  n_trials={nt:3}: p={r['p']:.4f} {'显著*' if r['sig'] else '不显著'}")
    print(f"\n=== 候选族 PBO(CSCV) = {pbo_val}  (台账 large-cap: 未算/None;小盘同胞: 0.76 高) ===")


if __name__ == "__main__":
    main()
