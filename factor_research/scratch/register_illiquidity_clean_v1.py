"""注册 illiquidity/clean-v1(干净登记范本)。

复用既有 illiquidity 家族(不改 family 元信息,只加一个新版本)。配置与已在册 v1.0
逐位相同(amihud/无veto/二值MA16/top25),区别只在登记纪律:leverage=1.0(非1.25)+
全套防自欺证据(L0去overlay归因/独立IC+t/holdout金库单次校验/PBO)。

证据来源:
  - scratch/illiquidity_evidence_pack.json(已机械产出:L0/独立IC/holdout/dsr_honest)
  - 本脚本新跑:phase1 合成防未来审计 + run_nine_gates_all 9-Gate(产出真实 dsr/capacity/
    return series)+ lineage_pbo(对家族内已有版本收益序列做 CSCV,真实 PBO)。

诚实边界(不可吃掉,见 DRAFT):
  - 家族 trial_ledger 计数=0(predates ledger)→ 本脚本 dsr_p 字段保留草稿的 dsr_honest
    (n=1/n=7 两种诚实框架),不向 run_nine_gates_all 索要会触发 TrialCountUnknown 的自动
    账本计数,也不伪造地板值(同 ADR-017 industry-neglect-rotation 处置先例)。
  - 全历史(2010-2026,含压力段)回撤 -22.8% 略超 20% 单体线 → 顶层 hit 诚实记 False,
    搜索窗(2018-<2025)与金库段(2025-2026)分别附 hit=True 的子段证据。
  - status 落"候选"而非"在册"——最终是否转在册留给 workflow/用户确认。

Usage:
  python3 scratch/register_illiquidity_clean_v1.py            # 全流程(phase1 + 注册 + 9-Gate + PBO)
  python3 scratch/register_illiquidity_clean_v1.py --dry-run  # 只跑 phase1 + 打印,不写台账
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import pandas as pd


def factor_builder(close, volume, amount, trade_dates):
    from factors.alpha.base import FactorData
    from factors.alpha.builtins.illiq import AmihudIlliq
    from factors.alpha import transforms  # noqa: F401  register zscore/mad_clip/shift
    fdata = FactorData(close=close, volume=volume, amount=amount)
    return AmihudIlliq(window=20).mad_clip(5).zscore().shift(1).compute(fdata)


def timing_builder(close, amount):
    from factors.small_cap import small_cap_timing
    traw, _, _ = small_cap_timing(close, amount, ma_window=16)
    return traw.astype(float)


CONFIG = {
    "top_n": 25, "rebalance_days": 20, "leverage": 1.0,
    "buy_cost": 0.00225, "sell_cost": 0.00275, "financing_rate": 0.0,
}


def run_phase1():
    from workflow.phase1_synthetic import Phase1Checker
    checker = Phase1Checker(factor_builder, timing_builder, "illiquidity-clean-v1", CONFIG)
    results = checker.run_all(use_clean=True, save_lessons=False)
    fails = [r for r in results if r.is_fail]
    print(f"[phase1] {'PASS' if not fails else 'FAIL ' + str([r.check_id for r in fails])}")
    for r in results:
        print(f"    {r.check_id:20} {r.verdict}")
    return not fails


def load_evidence_pack() -> dict:
    p = ROOT / "scratch" / "illiquidity_evidence_pack.json"
    return json.loads(p.read_text())


def initial_register(pack: dict):
    import strategy_registry
    seg = pack["segments_L1_registered"]
    a = pack["anti_self_deception"]
    stress = seg["stress_2010_2026"]

    metrics = {
        "annual": stress["annual"], "maxdd": stress["maxdd"],
        "sharpe": stress["sharpe"], "calmar": stress["calmar"],
        "hit": stress["hit"],
        "annual_search_2018": seg["search_2018_pre2025"]["annual"],
        "maxdd_search_2018": seg["search_2018_pre2025"]["maxdd"],
        "sharpe_search_2018": seg["search_2018_pre2025"]["sharpe"],
        "hit_search_2018": seg["search_2018_pre2025"]["hit"],
        "annual_holdout_2025": seg["holdout_2025_2026"]["annual"],
        "maxdd_holdout_2025": seg["holdout_2025_2026"]["maxdd"],
        "sharpe_holdout_2025": seg["holdout_2025_2026"]["sharpe"],
        "hit_holdout_2025": seg["holdout_2025_2026"]["hit"],
    }

    nine_gate = {
        "l0_bare_sharpe": a["L0_search_sharpe"],
        "l0_bare_annual": a["L0_search_annual"],
        "l0_real_alpha": a["L0_real_alpha"],
        "ic_mean": a["independent_ic_mean"],
        "ic_t": a["independent_ic_t"],
        "timing_dependence": a["timing_dependence"],
        "capacity_aum_亿": a["capacity_亿"],
        "holdout_annual": a["holdout_oos"]["annual"],
        "holdout_sharpe": a["holdout_oos"]["sharpe"],
        "holdout_maxdd": a["holdout_oos"]["maxdd"],
        "holdout_peek_count": a["holdout_oos"]["peek_count"],
        "dsr_honest": a["dsr_honest"],
        "dsr_p": None,  # 家族 trial_ledger=0(predates ledger),不伪造地板值(ADR-017 先例)
        "pbo": None,    # 待 lineage_pbo 用家族版本池真实 CSCV 补(见下一步)
        "passed_all": False,  # 未跑全套机械 9-Gate gate-by-gate,不手填 true
    }

    strategy_registry.register(
        family="illiquidity",
        version="clean-v1",
        desc="小盘 Amihud 非流动性溢价(干净登记范本):配置同 v1.0(amihud20/无veto/二值MA16/top25),"
             "leverage=1.0;首个用全套 LOOP_ENGINEERING 防自欺纪律(L0去overlay归因/独立IC+t/holdout"
             "单次校验/真实PBO)支撑的登记,供后续候选对标。",
        config={
            "factor": "Amihud illiquidity (|ret|/amount).rolling(20)",
            "timing": "PureTrend MA16(二值,非Band)",
            "top_n": 25, "rebal_days": 20, "leverage": 1.0,
            "cost": {"buy": 0.00225, "sell": 0.00275, "financing_rate": 0.0},
        },
        data_scope={
            "source": "data_lake", "period": "2010-2026", "survivorship_bias": False,
            "holdout": {
                "boundary": "2025-01-01", "candidate_id": "illiquidity-clean-v1",
                "peek_count": a["holdout_oos"]["peek_count"],
                "sharpe": a["holdout_oos"]["sharpe"],
            },
        },
        metrics=metrics,
        status="候选",
        admission={
            "track": "standalone",
            "rationale": "全历史(2010-2026)回撤-22.8%略超20%单体线(2015/2018小盘崩,诚实代价);"
                         "搜索窗(2018-<2025)与金库样本外(2025-2026)均 hit=True,L0裸因子夏普1.05"
                         "(去overlay自身达标)+独立IC t=5.94。status=候选,在册与否留待 workflow/用户确认。",
        },
        notes="LOOP_ENGINEERING §4 防自欺范本登记。dsr_p/pbo 待下一步真实补算,先以 None 占位(不伪造)。",
        evidence={"hypothesis_id": "", "experiment_ids": [],
                   "source_script": "scripts/research/illiquidity_evidence_pack.py"},
        nine_gate=nine_gate,
    )
    print("[register] illiquidity/clean-v1 初始登记完成(status=候选)。")


def run_nine_gate_and_persist():
    """跑真实 9-Gate(产出 capacity/cost/IC/return series),dsr_p 显式传 n_trials 避免崩溃,
    但最终落台账时仍尊重 §诚实边界 —— 不让自动算出的 dsr_p 悄悄冒充账本级显著性。"""
    from scripts.research.run_nine_gates_all import run_evaluation
    summary = run_evaluation("illiquidity", n_trials=7, persist=True, version="clean-v1")
    print(f"[nine-gate] 已跑并持久化 version_returns;summary keys: {list(summary.keys())}")
    return summary


def run_lineage_pbo():
    from scripts.research.lineage_pbo import _load_returns, compute_family, _merge_write
    store = _load_returns()
    vers = store.get("illiquidity", {})
    if "clean-v1" not in vers:
        print("[pbo] ⚠️ version_returns/illiquidity__clean-v1.csv 不存在,跳过 PBO")
        return None
    res = compute_family("illiquidity", vers)
    for ver, rec in res.items():
        if rec:
            _merge_write("illiquidity", ver, rec)
    print(f"[pbo] 家族 illiquidity({len(vers)} 个版本有收益序列)真实 PBO 已并入台账:")
    for ver, rec in res.items():
        print(f"    {ver:10} pbo={rec.get('pbo')} corr→{rec.get('corr_parent_version')}={rec.get('corr_to_parent')}")
    return res.get("clean-v1")


def reconcile_dsr_honesty():
    """run_nine_gates_all 的 attach_nine_gate 会整体覆盖 nine_gate 字段(见 strategy_registry.attach_nine_gate),
    其 summary 里的 dsr_p 来自我们传入的 n_trials=7(非账本)。merge 回 dsr_honest 框架,
    把 dsr_p 标注清楚来源,不让它被后续读者误当账本级显著性。"""
    import strategy_registry
    data = strategy_registry._load()
    fam = next(f for f in data["families"] if f["id"] == "illiquidity")
    v = next(x for x in fam["versions"] if x["version"] == "clean-v1")
    ng = dict(v.get("nine_gate") or {})
    ng["dsr_p_caveat"] = ("n_trials=7 为文献prior/池选估计(factor_pool_screen.py n=7),"
                          "非 trial_ledger 账本计数(该家族 predates ledger,账本计数=0);"
                          "不构成账本级显著性声明,主证仍为独立IC t=5.94 + holdout样本外。")
    ng["dsr_honest"] = {"n_trials=1": 0.0285, "n_trials=7": 0.3028}
    strategy_registry.attach_nine_gate("illiquidity", "clean-v1", ng)
    print("[reconcile] dsr 诚实边界注记已补回 nine_gate。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    ok = run_phase1()
    if not ok:
        print("\nphase1 FAIL — 不登记,先修因子/择时构造再重试。")
        return
    if args.dry_run:
        print("\n--dry-run:phase1 通过,未写台账。")
        return

    pack = load_evidence_pack()
    initial_register(pack)
    run_nine_gate_and_persist()
    run_lineage_pbo()
    reconcile_dsr_honesty()

    print("\n完成。最终台账条目:")
    import strategy_registry
    data = strategy_registry._load()
    fam = next(f for f in data["families"] if f["id"] == "illiquidity")
    v = next(x for x in fam["versions"] if x["version"] == "clean-v1")
    print(json.dumps(v, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
