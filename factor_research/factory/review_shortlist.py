"""CLI for phase-1.5 shortlist audit."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import pandas as pd

from factory.review import write_audit


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", help="Path to *_review.json or full factory report.")
    ap.add_argument("--out", default=None)
    ap.add_argument("--include-all", action="store_true", help="Audit all rows in a full report.")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    out, audits = write_audit(args.input, output_path=args.out, include_all=args.include_all)
    print(f"\nStage 1.5 shortlist audit n={len(audits)}")
    if audits:
        view = pd.DataFrame(audits)
        cols = [
            "registry_precheck", "incubate", "niche", "size_exposure", "family", "version", "desc",
            "in_sample_annual", "in_sample_maxdd", "oos_annual", "pressure_maxdd",
            "cost_up_annual", "cost_up_cost_drag_pa", "source_corr_to_baseline",
            "incubation_score", "incubation_reason",
        ]
        print(view[cols].head(args.top).to_string(index=False, formatters={
            "size_exposure": "{:.0%}".format,
            "in_sample_annual": "{:+.1%}".format,
            "in_sample_maxdd": "{:+.1%}".format,
            "oos_annual": "{:+.1%}".format,
            "pressure_maxdd": "{:+.1%}".format,
            "cost_up_annual": "{:+.1%}".format,
            "cost_up_cost_drag_pa": "{:.1%}".format,
            "source_corr_to_baseline": lambda x: "" if pd.isna(x) else f"{x:+.2f}",
            "incubation_score": "{:+.2f}".format,
        }))
    print(f"\nSaved: {out}")


if __name__ == "__main__":
    main()
