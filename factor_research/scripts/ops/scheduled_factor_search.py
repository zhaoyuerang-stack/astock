"""Scheduled Factor Search & 9-Gate Evaluation pipeline step.

This script runs during weekly maintenance to automatically discover new factors,
evaluate them through 9-Gate audits, and write reports for manual review.
"""
from __future__ import annotations

import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from core.engine import PricePanel, Signal
from core.analysis.nine_gates import NineGatesEvaluator, NineGatesReport
from services.actions.autoresearch_search import run_autoresearch_walk_forward
from factory.autoresearch.repositories import CandidateRepository, ReviewQueue, ExperimentLog
from strategies.small_cap import load_price_panels
from governance.trial_ledger import honest_n_trials  # LOOP_ENGINEERING §5.1(record 下沉到 orchestrator)
from governance.holdout import (
    boundary,
    assert_search_clean,
    candidate_identity,
    current_data_fingerprint,
    validate_on_holdout,
)

# Holdout 金库 review 状态(与 9-Gate passed_all 正交;异常不得伪装成可晋级叙事)
HOLDOUT_PASS = "pass"
HOLDOUT_FAIL = "fail"
HOLDOUT_ERROR = "error"


def classify_holdout_outcome(
    *,
    ho: dict | None = None,
    error: BaseException | None = None,
    min_sharpe: float = 0.6,
) -> dict:
    """把 validate_on_holdout 结果/异常压成 fail-closed 的 review 字段。

    - 异常 → status=error, ok=False(不得写成「未能校验、需人工」的软叙事)
    - 正常但夏普/DSR 不达标 → status=fail, ok=False
    - 正常且达标 → status=pass, ok=True
    """
    if error is not None:
        err_text = f"{type(error).__name__}: {str(error)[:200]}"
        return {
            "holdout_ok": False,
            "holdout_status": HOLDOUT_ERROR,
            "holdout_error": err_text,
            "holdout_sharpe": None,
            "holdout_dsr_p": None,
            "holdout_dsr_sig": None,
            "holdout_trials": None,
            "holdout_peek": None,
            "ho": {"error": err_text, "status": HOLDOUT_ERROR},
        }

    metrics = dict(ho or {})
    sharpe = metrics.get("sharpe")
    ho_sharpe_ok = isinstance(sharpe, (int, float)) and float(sharpe) >= min_sharpe
    # 金库 DSR 算得动则必须显著;短段算不动(None)退回夏普门兜底
    dsr_sig = metrics.get("holdout_dsr_sig")
    ho_ok = bool(ho_sharpe_ok and dsr_sig is not False)
    return {
        "holdout_ok": ho_ok,
        "holdout_status": HOLDOUT_PASS if ho_ok else HOLDOUT_FAIL,
        "holdout_error": None,
        "holdout_sharpe": (
            round(float(sharpe), 3) if isinstance(sharpe, (int, float)) else None
        ),
        "holdout_dsr_p": metrics.get("holdout_dsr_p"),
        "holdout_dsr_sig": dsr_sig,
        "holdout_trials": metrics.get("holdout_trials"),
        "holdout_peek": int(metrics.get("peek_count", 1) or 1),
        "ho": metrics,
    }


def promotion_eligible(*, nine_gate_passed: bool, holdout_status: str) -> bool:
    """仅当 9-Gate 全过且 holdout 明确 pass 才可进入人工 promote 候选叙事。"""
    return bool(nine_gate_passed) and holdout_status == HOLDOUT_PASS


def render_holdout_markdown(
    *,
    boundary_date,
    outcome: dict,
    nine_gate_passed: bool,
) -> str:
    """Holdout 段 + 晋级总裁决。error/fail 一律 ❌,禁止 ⚠️ 软化。"""
    status = outcome.get("holdout_status") or HOLDOUT_FAIL
    ho = outcome.get("ho") or {}
    eligible = promotion_eligible(
        nine_gate_passed=nine_gate_passed, holdout_status=status,
    )

    lines = [
        "",
        "## 晋级裁决(自动·fail-closed)",
        f"- 9-Gate passed_all: {'✅ PASS' if nine_gate_passed else '❌ FAIL'}",
        f"- Holdout 金库: **{status}**",
        f"- **可提交 promote: {'✅ 是' if eligible else '❌ 否'}**",
        "",
        "## Holdout 金库校验(LOOP_ENGINEERING §5.2)",
        f"- 金库边界 **{boundary_date}**(≥此为 holdout,搜索/9-Gate 从未使用)",
    ]

    if status == HOLDOUT_ERROR:
        err = outcome.get("holdout_error") or ho.get("error") or "unknown error"
        lines += [
            f"- ⚠️ 校验**异常**(非样本外表现差,是流程故障): `{err}`",
            "- 判定: ❌ **holdout_error** — 不得晋级;不得把 9-Gate 报告当 holdout 通过证据",
            "- 说明: 异常已记入 review_queue(`holdout_ok=false`, `holdout_status=error`),"
            " 不得仅因 9-Gate 好看而人工放行",
        ]
    else:
        dsr_sig = ho.get("holdout_dsr_sig")
        if dsr_sig is True:
            dsr_tag = " ✅显著"
        elif dsr_sig is False:
            dsr_tag = " ❌不显著"
        else:
            dsr_tag = " (短段未算)"
        lines += [
            f"- holdout 段: 年化 {ho.get('annual', 0):+.1%} / 夏普 {ho.get('sharpe', 0):.2f} / "
            f"回撤 {ho.get('maxdd', 0):+.1%}(n={ho.get('n')})",
            f"- 多重检验(§5.2 缝②): 金库已试 {ho.get('holdout_trials')} 候选, "
            f"DSR_p={ho.get('holdout_dsr_p')}{dsr_tag}, "
            f"偷看 {ho.get('peek_count')} 次",
            (
                "- 判定: ✅ 通过(夏普≥0.6 且金库多重检验过关)"
                if status == HOLDOUT_PASS
                else "- 判定: ❌ **holdout_failed** — 不予晋级"
            ),
        ]
    return "\n".join(lines) + "\n"


def main():
    print("=" * 80)
    print("  Scheduled AutoResearch & 9-Gate Audit Execution")
    print("=" * 80)

    # 1. Initialize repositories
    repository = CandidateRepository()
    review_queue = ReviewQueue()
    experiment_log = ExperimentLog()
    pending_before = {item["fingerprint"] for item in review_queue.pending()}

    # 2. Run Island Search to evolve factors
    print("\n[Step 1] Running Multi-Island Evolutionary Search...", flush=True)
    try:
        # True meta-WF:演化只见训练截止日,冠军在 2024 OOS 一次评分;
        # 2025+ holdout 金库仍完全保留给晋级前唯一一次消费。
        HOLDOUT = boundary()
        _c, _v, _a = load_price_panels("2018-01-01")
        meta_oos_end = _c.index[_c.index < HOLDOUT][-1]
        meta_cutoff = meta_oos_end - pd.DateOffset(years=1)
        assert_search_clean(meta_oos_end, label="周度元级WF OOS")
        print(
            f"  [meta-WF] train≤{meta_cutoff.date()} / "
            f"OOS=({meta_cutoff.date()},{meta_oos_end.date()}] / "
            f"holdout≥{HOLDOUT.date()} 保留",
            flush=True,
        )
        # We run 5 islands, 3 generations, population of 6
        # Set use_llm=True so it uses AI if keys are present, otherwise falls back
        # islands=5(原3)让 _ISLAND_THEMES 第5个主题"股东行为与资金流"轮得到
        # (i % len(_ISLAND_THEMES) 轮询,<5 个岛永远摸不到第5个主题)
        search_res = run_autoresearch_walk_forward(
            cutoff=str(meta_cutoff.date()),
            oos_end=str(meta_oos_end.date()),
            islands=5,
            generations=3,
            population=6,
            final_stage="l3",
            use_llm=True,
            start="2018-01-01",
            sample_dates=120,
            repository=repository,
            experiment_log=experiment_log,
            review_queue=review_queue,
            close=_c,
            volume=_v,
            amount=_a,
        )
        print(f"  Evolved factors complete. Evaluated: {search_res.evaluated}.")
        oos_promoted = {
            champion.fingerprint
            for champion in search_res.champions
            if champion.oos_decision == "promote"
        }
        # trial 记账已下沉到 run_autoresearch_island_search(§5.1 chokepoint),此处不再重复,
        # 避免双计。honest_n_trials("autoresearch") 仍由 9-Gate 在下方读取。
        
        # Copy newly evolved candidate experiments to the immutable ResearchLedger
        try:
            from research_ledger.ledger import ResearchLedger, LedgerEntry
            import time
            ledger = ResearchLedger()
            logged_count = 0
            for e in experiment_log.iter_all():
                exp_id = f"EXP_AUTO_{e.fingerprint[:12]}"
                if ledger.get_by_id(exp_id) is None:
                    entry = LedgerEntry(
                        experiment_id=exp_id,
                        parent_experiment_id="VINTAGE_AUTO",
                        hypothesis_text=e.reason or f"AutoResearch evolved candidate: {e.fingerprint[:8]}",
                        llm_prompt_hash=None,
                        factor_ast_hash=e.fingerprint,
                        code_commit_hash="git_head",
                        data_snapshot_hash="data_lake",
                        universe_version="CSI_1000",
                        cost_model_version="v1.25",
                        random_seed=42,
                        tried_parameters={},
                        result_metrics=e.metrics,
                        rejection_reason=e.reason if e.decision.value != "promote" else None,
                        reviewer="AI AutoResearch",
                        run_at=time.strftime("%Y-%m-%d %H:%M:%S")
                    )
                    ledger.log_experiment(entry)
                    logged_count += 1
            if logged_count > 0:
                print(f"  Logged {logged_count} search outcomes to the immutable ResearchLedger.")
        except Exception as err:
            print(f"  ⚠️ Failed to sync experiments to ResearchLedger: {err}")
    except Exception as e:
        print(f"❌ Island Search failed to run: {e}", file=sys.stderr)
        sys.exit(1)

    # 3. Fetch promoted candidates that passed L3
    # Check the review queue for any candidates waiting for human review
    promoted = [
        item for item in review_queue.pending()
        if item["fingerprint"] not in pending_before
        and item["fingerprint"] in oos_promoted
    ]
    if not promoted:
        print("\n[Step 2] No candidates passed L3 validation in this run. No reports to audit.")
        sys.exit(0)

    print(f"\n[Step 2] Found {len(promoted)} candidates promoted to review. Running 9-Gate audits...", flush=True)

    # Load data for evaluation. 保留全样本面板(close_full)仅供晋级前唯一一次 holdout 校验;
    # 9-Gate 是选择层,只看 < boundary 的切片(§5.2:补上"评估半边"的洞,loop 不得触碰金库)。
    close_full, volume_full, amount_full = load_price_panels("2018-01-01")
    close = close_full[close_full.index < HOLDOUT]
    volume = volume_full[volume_full.index < HOLDOUT]
    amount = amount_full[amount_full.index < HOLDOUT]
    assert_search_clean(close.index, label="9-Gate 评估")
    prices = PricePanel(close=close, volume=volume, amount=amount)

    # §5.3 缝④:预算一次在册 ACTIVE 组合(<boundary)收益,供逐候选边际真 alpha 判冗余。
    try:
        from portfolio.strategy_runners import run_active
        book_search = {k: v[v.index < HOLDOUT] for k, v in run_active(start="2018-01-01").items()}
    except Exception as _bk_err:
        book_search = None
        print(f"  [marginal] 在册组合加载失败,跳过边际判定: {_bk_err}", flush=True)

    for item in promoted:
        from factory.autoresearch.models import Candidate, CandidateStatus
        cand = Candidate(
            fingerprint=item["fingerprint"],
            ast=item["candidate"],
            status=CandidateStatus(item["status"]),
        )
        fp = cand.fingerprint
        print(f"\nEvaluating candidate {fp[:8]}...", flush=True)

        try:
            # Build factor and weights from AST
            from factory.autoresearch.pipeline import ast_to_hypothesis
            from workflow.from_factory import hypothesis_to_spec
            
            hyp = ast_to_hypothesis(cand)
            spec = hypothesis_to_spec(hyp)
            
            # Resolve weights
            from strategies.small_cap import build_rebalance_weights
            from factors.veto import salience_covariance_veto
            
            # We use standard parameters (top 25, 20d rebalance, veto)
            veto = salience_covariance_veto(close).shift(1)
            # Wrap factor_builder to match NineGatesEvaluator expectations (takes PricePanel)
            def wrapped_builder(prices_obj):
                return spec.factor_builder(
                    prices_obj.close, 
                    prices_obj.volume, 
                    prices_obj.amount, 
                    prices_obj.close.index
                )

            factor_df = spec.factor_builder(close, volume, amount, close.index)
            scheduled = build_rebalance_weights(
                factor_df,
                close,
                top_n=25,
                rebalance_days=20,
                veto_factor=veto,
                veto_q=0.30
            )
            
            signal = Signal(
                weights=scheduled,
                family=f"autoresearch_{fp[:8]}",
                version="v1.0"
            )

            # Economic thesis from candidate
            thesis = cand.ast.get("thesis", {
                "mechanism": "AutoResearch evolved mathematical combination.",
                "citation": "islands mutation"
            })

            # Run 9-Gate evaluator
            evaluator = NineGatesEvaluator(
                prices=prices,
                factor_df=factor_df,
                factor_builder=wrapped_builder,
                thesis=thesis,
                n_trials=honest_n_trials("autoresearch"),  # 读账本累计,替代手填 10(§5.1)
                forward_days=20
            )

            reports = evaluator.evaluate_all(signal, start="2018-01-01")
            passed_all = all(r.passed for r in reports)

            # §5.2 晋级前唯一一次 holdout 校验:可部署形态(因子+veto 权重)的全样本收益,
            # validate_on_holdout 只读 ≥boundary 段。
            # 9-Gate 报告仍写出(供人读门明细),但 holdout 异常/失败必须 fail-closed 记入
            # review_queue 与 markdown 晋级裁决——禁止「未能校验,需人工」软化叙事。
            from core.engine import BacktestEngine, BacktestConfig, CostModel
            ret_full = None  # §5.3 缝④:供 holdout 与 marginal 复用;holdout try 内赋值
            holdout_id = ""
            data_fp = ""
            try:
                veto_full = salience_covariance_veto(close_full).shift(1)
                factor_full = spec.factor_builder(close_full, volume_full, amount_full, close_full.index)
                weights_full = build_rebalance_weights(
                    factor_full, close_full, top_n=25, rebalance_days=20,
                    veto_factor=veto_full, veto_q=0.30,
                )
                ho_cost = CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.065)
                ret_full = BacktestEngine(
                    prices=PricePanel(close=close_full, volume=volume_full, amount=amount_full),
                    config=BacktestConfig(start="2018-01-01", cost=ho_cost, leverage=1.0),
                ).run(Signal(weights=weights_full)).returns
                data_fp = current_data_fingerprint()
                holdout_id = candidate_identity(f"autoresearch_{fp[:8]}", fp, data_fp)
                ho_raw = validate_on_holdout(
                    holdout_id,
                    ret_full,
                    spec_hash=fp,
                    data_fingerprint=data_fp,
                )
                outcome = classify_holdout_outcome(ho=ho_raw)
                print(
                    f"  [holdout] 段夏普 {ho_raw.get('sharpe', 0):.2f} (n={ho_raw.get('n')}, "
                    f"金库试过{ho_raw.get('holdout_trials')}候选/DSR_p={ho_raw.get('holdout_dsr_p')}, "
                    f"偷看{ho_raw.get('peek_count')}次) → {outcome['holdout_status']}",
                    flush=True,
                )
            except Exception as ho_err:
                outcome = classify_holdout_outcome(error=ho_err)
                print(
                    f"  [holdout] ❌ 校验异常 → holdout_error "
                    f"(9-Gate 报告仍落盘,但晋级裁决=否): {ho_err}",
                    flush=True,
                )

            # 无论通过/失败/异常,都把 holdout 状态写入 review(异常路径以前漏写)
            review_queue.record_fields(
                fp,
                holdout_id=holdout_id or f"autoresearch_{fp[:8]}_unvalidated",
                holdout_spec_hash=fp,
                holdout_data_fingerprint=data_fp or "",
                holdout_ok=bool(outcome["holdout_ok"]),
                holdout_status=outcome["holdout_status"],
                holdout_error=outcome.get("holdout_error") or "",
                holdout_sharpe=outcome.get("holdout_sharpe"),
                holdout_peek=outcome.get("holdout_peek"),
                holdout_dsr_p=outcome.get("holdout_dsr_p"),
                holdout_trials=outcome.get("holdout_trials"),
            )

            # §5.3 缝④:边际真 alpha — 候选去掉对在册组合暴露后是否还赚钱(高相关+残差弱=冗余同质变体)
            mg = {"marginal_verdict": "未计算"}
            if ret_full is not None and book_search is not None:
                try:
                    from governance.marginal import marginal_alpha
                    mg = marginal_alpha(ret_full[ret_full.index < HOLDOUT], book_search)
                    print(f"  [marginal] {mg.get('marginal_verdict')} "
                          f"(corr={mg.get('corr_to_book')}, 残差夏普={mg.get('residual_sharpe')})", flush=True)
                    review_queue.record_fields(
                        fp,
                        marginal_verdict=mg.get("marginal_verdict"),
                        marginal_resid_sharpe=mg.get("residual_sharpe"),
                        marginal_corr=mg.get("corr_to_book"),
                    )
                except Exception as mg_err:
                    mg = {"marginal_verdict": f"未能计算: {type(mg_err).__name__}"}

            # Build markdown report: 9-Gate 明细 + fail-closed 晋级裁决
            eligible = promotion_eligible(
                nine_gate_passed=passed_all,
                holdout_status=outcome["holdout_status"],
            )
            report = NineGatesReport(
                factor_name=f"autoresearch_{fp[:8]}",
                run_date=pd.Timestamp.now().strftime("%Y-%m-%d"),
                passed_all=passed_all,
                reports=reports
            )

            report_dir = ROOT / "reports" / "research"
            report_dir.mkdir(parents=True, exist_ok=True)
            # 文件名带裁决后缀,避免只看文件名以为全绿
            if eligible:
                suffix = "PROMOTE_OK"
            elif outcome["holdout_status"] != HOLDOUT_PASS:
                suffix = f"BLOCKED_{outcome['holdout_status'].upper()}"
            elif not passed_all:
                suffix = "BLOCKED_NINE_GATE"
            else:
                suffix = "BLOCKED"
            report_path = report_dir / f"autoresearch_{fp[:8]}_9_gates_{suffix}.md"

            ho_md = "\n" + render_holdout_markdown(
                boundary_date=HOLDOUT.date(),
                outcome=outcome,
                nine_gate_passed=passed_all,
            )
            ho_md += (
                f"\n## 边际真 alpha(§5.3 缝④)\n"
                f"- 判定: {mg.get('marginal_verdict')}(对在册组合 corr={mg.get('corr_to_book')}, "
                f"去暴露后残差夏普={mg.get('residual_sharpe')})\n"
            )
            report_path.write_text(report.to_markdown() + ho_md, encoding="utf-8")
            review_queue.record_fields(
                fp,
                nine_gate_passed_all=bool(passed_all),
                promotion_eligible=bool(eligible),
                nine_gate_report_path=str(report_path),
            )
            icon = "✅" if eligible else "🚫"
            print(f"  {icon} 9-Gate audit report saved (eligible={eligible}):\n  {report_path}")

        except Exception as e:
            print(f"  ❌ Failed to evaluate candidate {fp[:8]}: {e}", file=sys.stderr)

    print("\n🎉 Scheduled factor search and evaluation completed!")


if __name__ == "__main__":
    main()
