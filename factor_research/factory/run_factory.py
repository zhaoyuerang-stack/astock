"""Stage 1.1 minimal strategy factory CLI."""
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
from factory.search_space import default_candidates


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--out", default="reports/factory_stage1_1.json")
    args = ap.parse_args()

    rows = evaluate_candidates(default_candidates(), start=args.start)
    ranked = annotate_pareto(rows)

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(ranked, ensure_ascii=False, indent=2))

    view = pd.DataFrame(ranked)
    cols = [
        "pareto", "family", "version", "desc", "annual", "maxdd", "sharpe",
        "turnover_pa", "cost_drag_pa", "oos_annual", "corr_to_baseline",
        "hit_single",
    ]
    print(f"\nStage 1.1 factory candidates ({args.start}~latest)")
    print(view[cols].to_string(index=False, formatters={
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
