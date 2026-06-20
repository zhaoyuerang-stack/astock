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
from services.actions.autoresearch_search import run_island_search, run_autoresearch_island_search
from factory.autoresearch.repositories import CandidateRepository, ReviewQueue, ExperimentLog
from strategies.small_cap import load_price_panels


def main():
    print("=" * 80)
    print("  Scheduled AutoResearch & 9-Gate Audit Execution")
    print("=" * 80)

    # 1. Initialize repositories
    repository = CandidateRepository()
    review_queue = ReviewQueue()
    experiment_log = ExperimentLog()

    # 2. Run Island Search to evolve factors
    print("\n[Step 1] Running Multi-Island Evolutionary Search...", flush=True)
    try:
        # We run 3 islands, 3 generations, population of 6
        # Set use_llm=True so it uses AI if keys are present, otherwise falls back
        search_res = run_autoresearch_island_search(
            islands=3,
            generations=3,
            population=6,
            final_stage="l3",
            use_llm=True,
            start="2018-01-01",
            sample_dates=120,
            repository=repository,
            experiment_log=experiment_log,
            review_queue=review_queue
        )
        print(f"  Evolved factors complete. Evaluated: {search_res.evaluated}.")
        
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
    promoted = review_queue.all()
    if not promoted:
        print("\n[Step 2] No candidates passed L3 validation in this run. No reports to audit.")
        sys.exit(0)

    print(f"\n[Step 2] Found {len(promoted)} candidates promoted to review. Running 9-Gate audits...", flush=True)

    # Load data for evaluation
    close, volume, amount = load_price_panels("2018-01-01")
    prices = PricePanel(close=close, volume=volume, amount=amount)

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
                n_trials=10,
                forward_days=20
            )

            reports = evaluator.evaluate_all(signal, start="2018-01-01")
            passed_all = all(r.passed for r in reports)

            # Build markdown report
            report = NineGatesReport(
                factor_name=f"autoresearch_{fp[:8]}",
                run_date=pd.Timestamp.now().strftime("%Y-%m-%d"),
                passed_all=passed_all,
                reports=reports
            )

            report_dir = ROOT / "reports" / "research"
            report_dir.mkdir(parents=True, exist_ok=True)
            report_path = report_dir / f"autoresearch_{fp[:8]}_9_gates_report.md"
            
            report_path.write_text(report.to_markdown(), encoding="utf-8")
            print(f"  ✅ 9-Gate audit report saved to:\n  {report_path}")

        except Exception as e:
            print(f"  ❌ Failed to evaluate candidate {fp[:8]}: {e}", file=sys.stderr)

    print("\n🎉 Scheduled factor search and evaluation completed!")


if __name__ == "__main__":
    main()
