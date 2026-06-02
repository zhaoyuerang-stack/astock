"""Strategy factory CLI for stage 1."""
import argparse
import json
import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import pandas as pd

from factory.evaluator import evaluate_candidates, evaluate_candidates_with_context, prepare_context
from factory.niches import annotate_niches
from factory.nsga2 import NICHE_FAMILIES, genes_to_candidates, initial_population, next_generation
from factory.pareto import annotate_pareto
from factory.search_space import default_candidates, grid_candidates


def choose_candidates(mode, limit):
    if mode == "default":
        candidates = default_candidates()
        return candidates[:limit] if limit else candidates
    if mode == "grid":
        return grid_candidates(limit=limit)
    raise ValueError(f"Unsupported mode: {mode}")


def default_output(mode):
    if mode == "nsga2":
        return "reports/factory_stage1_3.json"
    if mode == "grid":
        return "reports/factory_stage1_2.json"
    return "reports/factory_stage1_1.json"


def output_path(args):
    if args.out:
        return Path(args.out)
    if args.mode == "nsga2" and args.niche != "all":
        return Path(f"reports/factory_stage1_4_{args.niche}.json")
    return Path(default_output(args.mode))


def run_nsga2(args):
    if args.population < 2:
        raise ValueError("--population must be >= 2 for tournament selection.")
    if args.generations < 1:
        raise ValueError("--generations must be >= 1.")
    if not 0 <= args.mutation_rate <= 1:
        raise ValueError("--mutation-rate must be between 0 and 1.")

    rng = random.Random(args.seed)
    close, amount, library, benchmark_ret = prepare_context(args.start)
    genes = initial_population(args.population, seed=args.seed, niche=args.niche)
    history = []

    final_ranked = []
    for generation in range(1, args.generations + 1):
        candidates = genes_to_candidates(genes, prefix=f"nsga2.g{generation}")
        rows = evaluate_candidates_with_context(candidates, close, amount, library, benchmark_ret, args.start)
        ranked = annotate_niches(annotate_pareto(rows), max_corr=args.review_corr)
        for row in ranked:
            row["generation"] = generation
        final_ranked = ranked

        best = ranked[0] if ranked else {}
        summary = {
            "generation": generation,
            "niche": args.niche,
            "evaluated": len(rows),
            "front_eligible": sum(bool(r.get("front_eligible")) for r in ranked),
            "pareto": sum(bool(r.get("pareto")) for r in ranked),
            "review_candidate": sum(bool(r.get("review_candidate")) for r in ranked),
            "hit_single": sum(bool(r.get("hit_single")) for r in ranked),
            "best_desc": best.get("desc"),
            "best_annual": best.get("annual"),
            "best_maxdd": best.get("maxdd"),
            "best_sharpe": best.get("sharpe"),
        }
        history.append(summary)
        print(
            f"gen={generation} evaluated={summary['evaluated']} "
            f"eligible={summary['front_eligible']} pareto={summary['pareto']} "
            f"review={summary['review_candidate']} hit_single={summary['hit_single']} "
            f"best={summary['best_desc']}"
        )

        if generation < args.generations:
            genes, _ = next_generation(rows, genes, args.population, rng, args.mutation_rate, niche=args.niche)

    return final_ranked, history


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["default", "grid", "nsga2"], default="default")
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--limit", type=int, default=None, help="Maximum candidates to evaluate.")
    ap.add_argument("--top", type=int, default=20, help="Rows to print in the terminal report.")
    ap.add_argument("--out", default=None)
    ap.add_argument("--population", type=int, default=12, help="NSGA-II parent population size.")
    ap.add_argument("--generations", type=int, default=2, help="NSGA-II generations to evaluate.")
    ap.add_argument("--mutation-rate", type=float, default=0.30)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--niche", choices=sorted(NICHE_FAMILIES), default="all")
    ap.add_argument("--review-corr", type=float, default=0.90, help="Max baseline correlation for review candidates.")
    args = ap.parse_args()

    history = None
    if args.mode == "nsga2":
        ranked, history = run_nsga2(args)
        candidates_count = len(ranked)
    else:
        candidates = choose_candidates(args.mode, args.limit)
        rows = evaluate_candidates(candidates, start=args.start)
        ranked = annotate_niches(annotate_pareto(rows), max_corr=args.review_corr)
        candidates_count = len(candidates)

    out = output_path(args)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(ranked, ensure_ascii=False, indent=2))
    if history is not None:
        history_out = out.with_name(out.stem + "_history.json")
        history_out.write_text(json.dumps(history, ensure_ascii=False, indent=2))
    review_rows = [row for row in ranked if row.get("review_candidate")]
    review_out = out.with_name(out.stem + "_review.json")
    review_out.write_text(json.dumps(review_rows, ensure_ascii=False, indent=2))

    view = pd.DataFrame(ranked)
    cols = [
        "pareto", "front_eligible", "review_candidate", "niche", "size_exposure", "family", "version", "desc", "annual", "maxdd", "sharpe",
        "turnover_pa", "cost_drag_pa", "oos_annual", "corr_to_baseline",
        "hit_single",
    ]
    review_count = sum(bool(r.get("review_candidate")) for r in ranked)
    print(f"\nStage 1 factory candidates mode={args.mode} niche={args.niche} n={candidates_count} review={review_count} ({args.start}~latest)")
    print(view[cols].head(args.top).to_string(index=False, formatters={
        "annual": "{:+.1%}".format,
        "maxdd": "{:+.1%}".format,
        "sharpe": "{:.2f}".format,
        "size_exposure": "{:.0%}".format,
        "turnover_pa": "{:.1f}x".format,
        "cost_drag_pa": "{:.1%}".format,
        "oos_annual": lambda x: "" if pd.isna(x) else f"{x:+.1%}",
        "corr_to_baseline": lambda x: "" if pd.isna(x) else f"{x:+.2f}",
    }))
    print(f"\nSaved: {out}")
    if history is not None:
        print(f"History: {history_out}")
    print(f"Review: {review_out}")


if __name__ == "__main__":
    main()
