"""Promote — 候选 Hypothesis 走完整 phase1~4 验证+登记闸门。

这是 factory(广度生成/筛选) → workflow(深度验证/登记) 的**唯一**贯通驱动:

    factory pool 中 L3_PASSED 的 Hypothesis
      → from_factory 适配成 (factor_builder, timing_builder)
      → phase1 合成防未来审计
      → phase2 三段回测(IS/OOS/压力)
      → phase3 walk-forward
      → phase4_register(唯一台账写入口,留 reproducibility_meta)
      → [可选] line3_marginal 边际评级 → ACTIVE/SHADOW

phase4_register 内部只调 strategy_registry.register_family/register;
任何代码都不应绕过它直接改 strategy_versions.json(见 check_layer_deps)。

用法:
  cd /Users/kiki/astcok/factor_research
  python3 workflow/promote.py --pool                       # 升所有 L3_PASSED
  python3 workflow/promote.py --pool --marginal
  python3 workflow/promote.py --pool --nine-gate           # 入册后自动回填 9-Gate
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NINE_GATE_STRATEGY_TO_FAMILY = {
    "small_cap": "small-cap-size",
    "size_earnings": "size-earnings",
    "large_cap": "large-cap-growth-hedged",
    "hq_momentum": "hq-momentum-hedged",
}


def promote_spec(spec, version="v1.0", warmup_start="2010-01-01",
                 force=False, run_marginal=False, regime="", decay_signal="", hyp=None,
                 run_nine_gate=False, nine_gate_strategy=None, nine_gate_runner=None,
                 nine_gate_trials=15, nine_gate_start=None, target_status="", holdout_id=""):
    """把一个 workflow FactorSpec 走完整 phase1~4,返回 RegistrationReport。

    spec 可来自 from_factory.hypothesis_to_spec(hyp) 或 explore.make_candidates()。
    """
    from workflow.phase1_synthetic import Phase1Checker
    from workflow.phase2_backtest import Phase2Runner
    from workflow.phase3_wf import WF3Runner
    from workflow.phase4_register import Phase4Register

    print(f"\n{'='*60}\nPromote: {spec.name} → {version}\n{'='*60}", flush=True)

    # ── intake:知识图谱 gate(仅 SKIP 短路;force 可越过)──
    if hyp is not None and not force:
        from knowledge.graph import load_graph
        skip, reason = load_graph().should_skip(hyp)
        if skip:
            print(f"  ⏭ 知识图谱 gate 跳过(不跑 phase):{reason}", flush=True)
            return None

    # ── phase1 合成防未来审计 ──
    print("[phase1] 合成防未来审计...", flush=True)
    checker = Phase1Checker(spec.factor_builder, spec.timing_builder, spec.name, spec.config)
    p1 = checker.run_all(use_clean=True, save_lessons=False)
    fails = [r for r in p1 if r.is_fail]
    print(f"  → {'PASS' if not fails else 'FAIL '+str([r.check_id for r in fails])}", flush=True)

    # ── phase2 三段回测 ──
    print("[phase2] 三段回测(IS/OOS/压力)...", flush=True)
    p2 = Phase2Runner(spec.factor_builder, spec.timing_builder, spec.name, spec.config).run(
        warmup_start=warmup_start)

    # ── phase3 walk-forward ──
    print("[phase3] walk-forward...", flush=True)
    p3 = WF3Runner(spec.factor_builder, spec.timing_builder, spec.name, spec.config).run(
        warmup_start=warmup_start)

    # ── 知识图谱:从本次验证结果现场生长 finding(phase1 失败→SKIP,其余弱→DEPRIORITIZE)──
    if hyp is not None:
        _record_kg(hyp, p1, p3)

    # ── 证据链:查促成晋级的 L0-L3 实验 ID(锚定到台账) ──
    hyp_id, evidence_ids = "", []
    if hyp is not None:
        hyp_id = hyp.id
        try:
            from factory.repositories.experiment_log import ExperimentLog
            evidence_ids = [e.experiment_id for e in ExperimentLog().list_by_hypothesis(hyp_id)]
        except Exception as e:
            print(f"  (证据链查询跳过 non-fatal): {type(e).__name__}: {str(e)[:60]}", flush=True)

    # ── phase4 登记(唯一台账写入口) ──
    print("[phase4] 登记...", flush=True)
    report = Phase4Register(spec.name, version).register(
        p1, p2, p3,
        hypothesis=getattr(spec, "hypothesis", ""),
        regime=regime, decay_signal=decay_signal, force=force,
        hypothesis_id=hyp_id, evidence_experiment_ids=evidence_ids,
        target_status=target_status, holdout_id=holdout_id,
    )
    if report is not None:
        report.phase_summary = _phase_summary(p1, p2, p3, report)
    print(report, flush=True)

    # ── [可选] Nine-Gate 完整审计 → 回填台账 DSR/PSR/PBO 摘要 ──
    if run_nine_gate:
        if report and report.registered:
            print("[nine-gate] 完整审计并回填台账...", flush=True)
            ng_result = run_nine_gate_after_registration(
                report,
                strategy_name=nine_gate_strategy,
                runner=nine_gate_runner,
                n_trials=nine_gate_trials,
                start=nine_gate_start,
            )
            print(f"  → {ng_result.get('status')}: {ng_result.get('strategy', '')}", flush=True)
        else:
            print("[nine-gate] 跳过: phase4 未登记成功", flush=True)

    # ── [可选] 边际评级 → ACTIVE/SHADOW ──
    if run_marginal and report.registered:
        _run_marginal(spec, report)

    return report


def _phase_summary(p1, p2, p3, report) -> dict:
    """Compact phase summary for async job results."""
    p1_fails = [getattr(r, "check_id", "") for r in (p1 or []) if getattr(r, "is_fail", False)]
    p2_segments = {}
    for label, seg in ((p2 or {}).get("segments") or {}).items():
        p2_segments[label] = {
            "annual": seg.get("annual"),
            "maxdd": seg.get("maxdd"),
            "sharpe": seg.get("sharpe"),
        }
    p3_agg = (p3 or {}).get("aggregate", {}) if isinstance(p3, dict) else {}
    return {
        "phase1": {
            "status": "PASS" if not p1_fails else "FAIL",
            "failures": [x for x in p1_fails if x],
        },
        "phase2": {
            "segments": p2_segments,
            "cost_sensitivity": (p2 or {}).get("cost_sensitivity", {}).get("verdict"),
            "correlation": (p2 or {}).get("correlation", {}).get("verdict"),
        },
        "phase3": {
            "verdict": p3_agg.get("verdict"),
            "annual": p3_agg.get("annual"),
            "maxdd": p3_agg.get("maxdd"),
            "sharpe": p3_agg.get("sharpe"),
        },
        "phase4": {
            "registered": getattr(report, "registered", False),
            "status": getattr(report, "status", ""),
            "detail": getattr(report, "detail", ""),
        },
    }


def _infer_nine_gate_strategy(family: str) -> str | None:
    """Registry family id -> run_nine_gates_all strategy name."""
    for strategy_name, family_id in NINE_GATE_STRATEGY_TO_FAMILY.items():
        if family_id == family:
            return strategy_name
    return None


def _default_nine_gate_runner(strategy_name, n_trials=15, persist=False, version=None, start=None):
    """Lazy adapter so importing promote.py stays light."""
    from scripts.research.run_nine_gates_all import run_evaluation
    return run_evaluation(
        strategy_name,
        n_trials=n_trials,
        persist=persist,
        version=version,
        start=start,
    )


def _attach_nine_gate_control_status(family: str, version: str, status: str, *,
                                     strategy: str = "", error: str = "") -> dict:
    """Persist a control-plane Nine-Gate status without changing registration state."""
    summary = {
        "status": status,
        "strategy": strategy,
    }
    if error:
        summary["error"] = error[:800]
    try:
        from strategy_registry import attach_nine_gate
        attach_nine_gate(family, version, summary)
    except Exception as attach_error:
        summary["attach_error"] = f"{type(attach_error).__name__}: {str(attach_error)[:300]}"
    return summary


def run_nine_gate_after_registration(report, *, strategy_name=None, runner=None,
                                     n_trials=15, start=None) -> dict:
    """Run full 9-Gate after a successful Phase4 registration.

    A Nine-Gate failure is deliberately non-transactional: the registry entry stays,
    but its nine_gate field records FAILED_TO_RUN so governance/readiness can block it.
    """
    if report is None:
        return {"status": "SKIPPED", "reason": "no_report"}
    family = getattr(report, "family", "")
    version = getattr(report, "version", "")
    if not getattr(report, "registered", False):
        return {"status": "SKIPPED", "family": family, "version": version,
                "reason": "not_registered"}

    strategy = strategy_name or _infer_nine_gate_strategy(family)
    if not strategy:
        return _attach_nine_gate_control_status(
            family, version, "FAILED_TO_RUN",
            error=f"No 9-Gate strategy mapping for family={family!r}",
        )

    effective_runner = runner or _default_nine_gate_runner
    try:
        summary = effective_runner(
            strategy,
            n_trials=n_trials,
            persist=True,
            version=version,
            start=start,
        )
        if isinstance(summary, dict) and summary:
            persisted = dict(summary)
            persisted.setdefault("status", "PERSISTED")
            persisted.setdefault("strategy", strategy)
            from strategy_registry import attach_nine_gate
            attach_nine_gate(family, version, persisted)
        return {"status": "PERSISTED", "family": family, "version": version,
                "strategy": strategy}
    except Exception as e:
        return _attach_nine_gate_control_status(
            family, version, "FAILED_TO_RUN",
            strategy=strategy,
            error=f"{type(e).__name__}: {str(e)[:700]}",
        )


def _record_kg(hyp, p1, p3):
    """把验证结果写进知识图谱(失败也记,避免重复尝试)。best-effort。"""
    try:
        from knowledge.graph import load_graph
        kg = load_graph()
        p1_fail = any(getattr(r, "is_fail", False) for r in (p1 or []))
        agg = (p3 or {}).get("aggregate", {})
        metrics = {"wf_sharpe": agg.get("sharpe", 0), "annual": agg.get("annual", 0),
                   "wf_maxdd": agg.get("maxdd", 0)}
        if p1_fail:
            kg.record_from_validation(hyp, passed=False, metrics=metrics, stage="phase1")
        elif agg.get("verdict") == "PASS":
            kg.record_from_validation(hyp, passed=True, metrics=metrics, stage="phase3")
        else:
            kg.record_from_validation(hyp, passed=False, metrics=metrics, stage="phase3")
        print(f"  [knowledge] {kg.summary()}", flush=True)
    except Exception as e:
        print(f"  [knowledge] 记录跳过(non-fatal): {type(e).__name__}: {str(e)[:80]}", flush=True)


def _run_marginal(spec, report):
    """登记后:对当前 ACTIVE 组合算边际贡献,标 ACTIVE/SHADOW。best-effort。"""
    try:
        from portfolio.strategy_runners import run_active
        from factory.lines.line3_marginal.marginal_eval import evaluate_candidate
        from factory.ontology import Hypothesis
        from strategies.small_cap import load_price_panels

        print("[marginal] 对 ACTIVE 组合算边际贡献...", flush=True)
        # §5.2 缝③:边际 ACTIVE/SHADOW 定级是选择,只用 <boundary,金库不参与定级。
        from governance.holdout import boundary
        _hb = boundary()
        live = {k: v[v.index < _hb] for k, v in run_active(start="2018-01-01").items()}
        close, volume, amount = load_price_panels("2018-01-01")
        close, volume, amount = close[close.index < _hb], volume[volume.index < _hb], amount[amount.index < _hb]
        # 用 spec 反推一个最小 Hypothesis(marginal 需要 factor_fn_name);
        # 若 spec 来自 from_factory,其 config 不含 fn_name,这里 best-effort 跳过。
        fn_name = spec.config.get("factor_fn_name")
        if not fn_name:
            print("  (spec 无 factor_fn_name,跳过 marginal;factory 来源的 Hypothesis 走 promote_hypothesis)", flush=True)
            return
        hyp = Hypothesis(name=spec.name, description=spec.hypothesis,
                         factor_fn_name=fn_name,
                         factor_params=spec.config.get("factor_params", {}),
                         data_dependencies=tuple(spec.config.get("data_dependencies", ())))
        _, mreport = evaluate_candidate(hyp, direction=1, live_returns=live,
                                        close=close, volume=volume, amount=amount,
                                        vintage_id="promote")
        if mreport is not None:
            print(f"  grade={mreport.grade} → {'ACTIVE' if mreport.grade != 'SHELVE' else 'SHADOW'}", flush=True)
        # §5.3 残差边际硬闸:用 governance.marginal_alpha(残差法)复核 line3 的 raw-corr 定级,
        # 补根因#2 的洞(long-only raw 相关把市场 beta 误当 alpha 冗余)。裸因子对 book 残差化。
        from governance.marginal import marginal_alpha
        from factory.lines.line3_marginal.marginal_eval import run_candidate_returns, StrategyConfig
        cand_bare = run_candidate_returns(hyp, 1, close, volume, amount,
                                          config=StrategyConfig(timing_kind="none"))
        mres = marginal_alpha(cand_bare, live)
        print(f"  [marginal-residual] corr(book)={mres.get('corr_to_book')} "
              f"残差夏普={mres.get('residual_sharpe')} → {mres['marginal_verdict']}", flush=True)
        if "冗余" in mres.get("marginal_verdict", ""):
            print("  ⚠️ 残差判定冗余:与在册组合同质,建议 SHADOW 不并实盘权重(governance 据此降级)。", flush=True)
    except Exception as e:
        print(f"  marginal 跳过(non-fatal): {type(e).__name__}: {str(e)[:80]}", flush=True)


def promote_hypothesis(hyp, version="v1.0", **kw):
    """factory Hypothesis → 完整 phase1~4。"""
    from workflow.from_factory import hypothesis_to_spec
    spec = hypothesis_to_spec(hyp)
    # 把 fn_name 透传进 config,供 marginal 复用
    spec.config["factor_fn_name"] = hyp.factor_fn_name
    spec.config["factor_params"] = dict(hyp.factor_params)
    spec.config["data_dependencies"] = tuple(hyp.data_dependencies)
    return promote_spec(spec, version=version, hyp=hyp, **kw)


def promote_pool_l3(version="v1.0", **kw):
    """升 factory pool 中所有 L3_PASSED 的 Hypothesis。"""
    from factory.pool import HypothesisPool
    from factory.ontology import HypothesisStatus

    pool = HypothesisPool()
    l3 = pool.list_by_status(HypothesisStatus.L3_PASSED)
    if not l3:
        print("pool 中无 L3_PASSED 候选。", flush=True)
        return []
    print(f"发现 {len(l3)} 个 L3_PASSED 候选,逐个 promote...", flush=True)
    reports = []
    for hyp in l3:
        reports.append(promote_hypothesis(hyp, version=version, **kw))
    return reports


if __name__ == "__main__":
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    ap = argparse.ArgumentParser()
    ap.add_argument("--pool", action="store_true", help="升 pool 中所有 L3_PASSED")
    ap.add_argument("--version", default="v1.0")
    ap.add_argument("--marginal", action="store_true", help="登记后算边际贡献")
    ap.add_argument("--force", action="store_true", help="phase1/2 不过也强制登记(标候选)")
    ap.add_argument("--nine-gate", action="store_true", help="登记成功后运行 9-Gate 并回填台账")
    ap.add_argument("--nine-gate-strategy", default=None, help="覆盖 9-Gate CLI 策略名")
    ap.add_argument("--nine-gate-trials", type=int, default=15, help="9-Gate 多重检验 trial 数")
    ap.add_argument("--nine-gate-start", default=None, help="覆盖 9-Gate 回测起始日期")
    args = ap.parse_args()

    if args.pool:
        promote_pool_l3(
            version=args.version,
            run_marginal=args.marginal,
            force=args.force,
            run_nine_gate=args.nine_gate,
            nine_gate_strategy=args.nine_gate_strategy,
            nine_gate_trials=args.nine_gate_trials,
            nine_gate_start=args.nine_gate_start,
        )
    else:
        print("指定 --pool 升 L3_PASSED 候选;或在代码中调 promote_hypothesis(hyp)。")
