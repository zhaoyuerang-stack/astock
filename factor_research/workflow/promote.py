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
  python3 workflow/promote.py --pool          # 升所有 L3_PASSED
  python3 workflow/promote.py --pool --marginal
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def promote_spec(spec, version="v1.0", warmup_start="2010-01-01",
                 force=False, run_marginal=False, regime="", decay_signal="", hyp=None):
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

    # ── phase4 登记(唯一台账写入口) ──
    print("[phase4] 登记...", flush=True)
    report = Phase4Register(spec.name, version).register(
        p1, p2, p3,
        hypothesis=getattr(spec, "hypothesis", ""),
        regime=regime, decay_signal=decay_signal, force=force,
    )
    print(report, flush=True)

    # ── [可选] 边际评级 → ACTIVE/SHADOW ──
    if run_marginal and report.registered:
        _run_marginal(spec, report)

    return report


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
        live = run_active(start="2018-01-01")
        close, volume, amount = load_price_panels("2018-01-01")
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
    args = ap.parse_args()

    if args.pool:
        promote_pool_l3(version=args.version, run_marginal=args.marginal, force=args.force)
    else:
        print("指定 --pool 升 L3_PASSED 候选;或在代码中调 promote_hypothesis(hyp)。")
