"""illiquidity 干净登记证据包(全套防自欺纪律)。

注册形态 = 全市场 Amihud top25 + MA16 择时(lev 1.0,L1)。证据三段(金库纪律):
  压力 2010~2026 / 搜索 2018~<2025(唯一用于选择)/ 金库 2025~2026(从未搜过)。
附:L0 去 overlay 归因(因子自身)、独立 IC+t、择时依赖、容量、诚实 DSR、金库校验。
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
from core.analysis.walk_forward import deflated_sharpe
from strategy_truth_screen import _run, independent_ic, capacity_est
from illiq_largecap_audit import build_weights
from governance import holdout as HO

COST = CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.0)


def seg(r, lo, hi):
    s = r[(r.index >= lo) & (r.index < hi)].dropna()
    m = metrics(s)
    return {k: round(m[k], 4) for k in ("annual", "sharpe", "maxdd", "calmar")} | {
        "hit": compute_hit(m["annual"], m["maxdd"]), "n": int(m["n"])}


def main():
    from strategies.small_cap import load_price_panels
    from factors.small_cap import small_cap_timing
    b = HO.boundary()
    buf = io.StringIO()
    with redirect_stdout(buf):
        close, volume, amount = load_price_panels("2010-01-01")  # 含压力段+预热
        timing, _, _ = small_cap_timing(close, amount, 16)
        amihud = (close.pct_change(fill_method=None).abs() / (amount + 1.0)).rolling(20).mean()
        weights = build_weights(amihud, close, amount, top_n=25, rebal=20, universe=10**9)
    prices = PricePanel(close=close, volume=volume, amount=amount)

    L0 = _run(prices, weights, None, 1.0, COST, "2010-01-01")   # 裸因子
    L1 = _run(prices, weights, timing, 1.0, COST, "2010-01-01")  # 注册形态:因子+MA16

    # 三段(金库纪律):压力全样本 / 搜索<2025 / 金库>=2025
    segments = {
        "stress_2010_2026": seg(L1, "2010-01-01", "2027-01-01"),
        "search_2018_pre2025": seg(L1, "2018-01-01", str(b.date())),
        "holdout_2025_2026": seg(L1, str(b.date()), "2027-01-01"),
    }
    # 裸因子(L0)同段,证明 alpha 不靠 overlay
    l0_search = seg(L0, "2018-01-01", str(b.date()))

    # 归因 / IC / 容量(搜索窗)
    L1s = L1[(L1.index >= "2018-01-01") & (L1.index < b)].dropna()
    L0s = L0[(L0.index >= "2018-01-01") & (L0.index < b)].dropna()
    m1s, m0s = metrics(L1s), metrics(L0s)
    timing_dep = round((m1s["sharpe"] - m0s["sharpe"]) / abs(m1s["sharpe"]), 3) if m1s["sharpe"] else None
    ic = independent_ic(amihud, close[close.index < b])
    cap = capacity_est(prices, weights)
    data_fp = HO.current_data_fingerprint()
    spec_hash = hashlib.sha256(b"illiquidity-clean-v1").hexdigest()
    ho = HO.validate_on_holdout(
        HO.candidate_identity("illiquidity-clean-v1", spec_hash, data_fp),
        L1,
        spec_hash=spec_hash,
        data_fingerprint=data_fp,
    )

    # 诚实 DSR(肥尾下偏弱;主显著性靠 IC t + 金库)
    dsr = {nt: round(deflated_sharpe(observed_sr=m1s["sharpe"], n_trials=nt, n_periods=m1s["n"],
                                     skew=m1s["skew"], kurt=m1s["kurtosis_excess"] + 3.0)["p_value"], 4)
           for nt in [1, 7]}

    pack = {
        "identity": {"family": "illiquidity", "version": "clean-v1",
                     "name": "小盘 Amihud 非流动性溢价(干净登记)",
                     "hypothesis": "A股散户偏好高流动性→低流动性股被系统性低估,需更高预期收益补偿。文献:Amihud(2002)。"},
        "config": {"factor": "Amihud illiquidity = (|ret|/amount).rolling(20)", "universe": "全市场(小盘倾斜固有)",
                   "top_n": 25, "rebal_days": 20, "overlay": "PureTrend MA16 择时(风控,非alpha)", "leverage": 1.0,
                   "cost": "buy 0.225% / sell 0.275%"},
        "segments_L1_registered": segments,
        "L0_bare_search": l0_search,
        "anti_self_deception": {
            "L0_real_alpha": bool(m0s["sharpe"] >= 0.8),
            "L0_search_sharpe": round(m0s["sharpe"], 3), "L0_search_annual": round(m0s["annual"], 4),
            "independent_ic_mean": round(ic["ic_mean"], 4), "independent_ic_t": round(ic["t_stat"], 2),
            "timing_dependence": timing_dep,
            "capacity_亿": cap.get("capacity_aum_亿"),
            "holdout_oos": {k: ho.get(k) for k in ("annual", "sharpe", "maxdd", "n", "peek_count")},
            "dsr_honest": dsr,
        },
    }
    with open("scratch/illiquidity_evidence_pack.json", "w") as f:
        json.dump(pack, f, ensure_ascii=False, indent=2, default=float)

    print("=== illiquidity 干净登记证据包 ===")
    print("三段(注册形态 L1=因子+MA16,lev1.0):")
    for k, v in segments.items():
        print(f"  {k:22} 年化{v['annual']:+.1%} 夏普{v['sharpe']:.2f} 回撤{v['maxdd']:+.1%} Calmar{v['calmar']:.2f} hit={v['hit']} n={v['n']}")
    a = pack["anti_self_deception"]
    print(f"\n防自欺证据:")
    print(f"  L0裸因子(搜索)  : 夏普{a['L0_search_sharpe']} 年化{a['L0_search_annual']:+.1%} real_alpha={a['L0_real_alpha']}")
    print(f"  独立IC          : {a['independent_ic_mean']:+.4f} t={a['independent_ic_t']}(真显著性)")
    print(f"  择时依赖        : {a['timing_dependence']:.0%}(overlay=风控非alpha)")
    print(f"  容量            : {a['capacity_亿']}亿")
    print(f"  金库样本外      : 年化{a['holdout_oos']['annual']:+.1%} 夏普{a['holdout_oos']['sharpe']:.2f} 回撤{a['holdout_oos']['maxdd']:+.1%}(偷看{a['holdout_oos']['peek_count']}次)")
    print(f"  诚实DSR         : {a['dsr_honest']}(肥尾偏弱→以IC t+金库为主证)")
    print("\nWROTE scratch/illiquidity_evidence_pack.json")


if __name__ == "__main__":
    main()
