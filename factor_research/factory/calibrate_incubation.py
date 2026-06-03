"""CLI for calibrating incubation-pool candidates."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import pandas as pd

from factory.incubation import write_calibration


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="reports/islands/incubation_pool.json")
    ap.add_argument("--out-dir", default="reports/incubation")
    ap.add_argument("--max-variants-per-seed", type=int, default=6)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    summary, audits, combos = write_calibration(
        args.input,
        out_dir=args.out_dir,
        max_variants_per_seed=args.max_variants_per_seed,
    )
    print(
        f"\nStage 1.8 incubation calibration seeds={summary['seed_candidates']} "
        f"variants={summary['variants']} precheck={summary['registry_precheck']} "
        f"incubate={summary['incubate']} combo_precheck={summary['combo_precheck']}"
    )
    if audits:
        view = pd.DataFrame(audits)
        cols = [
            "registry_precheck", "incubate", "niche", "version", "desc",
            "in_sample_annual", "in_sample_maxdd", "oos_annual", "pressure_maxdd",
            "cost_up_annual", "source_corr_to_baseline", "incubation_score",
        ]
        print(view[cols].head(args.top).to_string(index=False, formatters={
            "in_sample_annual": "{:+.1%}".format,
            "in_sample_maxdd": "{:+.1%}".format,
            "oos_annual": "{:+.1%}".format,
            "pressure_maxdd": "{:+.1%}".format,
            "cost_up_annual": "{:+.1%}".format,
            "source_corr_to_baseline": lambda x: "" if pd.isna(x) else f"{x:+.2f}",
            "incubation_score": "{:+.2f}".format,
        }))
    if combos:
        view = pd.DataFrame(combos)
        cols = [
            "combo_precheck", "members", "in_sample_annual", "in_sample_maxdd",
            "oos_annual", "pressure_maxdd", "cost_up_annual", "in_sample_corr_to_baseline",
        ]
        print("\nCombo contribution")
        print(view[cols].head(args.top).to_string(index=False, formatters={
            "in_sample_annual": "{:+.1%}".format,
            "in_sample_maxdd": "{:+.1%}".format,
            "oos_annual": "{:+.1%}".format,
            "pressure_maxdd": "{:+.1%}".format,
            "cost_up_annual": "{:+.1%}".format,
            "in_sample_corr_to_baseline": lambda x: "" if pd.isna(x) else f"{x:+.2f}",
        }))
    print(f"\nSaved: {Path(args.out_dir)}")


if __name__ == "__main__":
    main()
