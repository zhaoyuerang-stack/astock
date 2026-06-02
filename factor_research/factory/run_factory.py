"""Strategy factory CLI for stage 1."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import pandas as pd

from factory.evaluator import evaluate_candidates
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
    if mode == "grid":
        return "reports/factory_stage1_2.json"
    return "reports/factory_stage1_1.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["default", "grid"], default="default")
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--limit", type=int, default=None, help="Maximum candidates to evaluate.")
    ap.add_argument("--top", type=int, default=20, help="Rows to print in the terminal report.")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    candidates = choose_candidates(args.mode, args.limit)
    rows = evaluate_candidates(candidates, start=args.start)
    ranked = annotate_pareto(rows)

    out = Path(args.out or default_output(args.mode))
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(ranked, ensure_ascii=False, indent=2))

    view = pd.DataFrame(ranked)
    cols = [
        "pareto", "front_eligible", "family", "version", "desc", "annual", "maxdd", "sharpe",
        "turnover_pa", "cost_drag_pa", "oos_annual", "corr_to_baseline",
        "hit_single",
    ]
    print(f"\nStage 1 factory candidates mode={args.mode} n={len(candidates)} ({args.start}~latest)")
    print(view[cols].head(args.top).to_string(index=False, formatters={
        "annual": "{:+.1%}".format,
        "maxdd": "{:+.1%}".format,
        "sharpe": "{:.2f}".format,
        "turnover_pa": "{:.1f}x".format,
        "cost_drag_pa": "{:.1%}".format,
        "oos_annual": lambda x: "" if pd.isna(x) else f"{x:+.1%}",
        "corr_to_baseline": lambda x: "" if pd.isna(x) else f"{x:+.2f}",
    }))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
