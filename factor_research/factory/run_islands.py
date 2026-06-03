"""CLI for phase-1.6 island-model factory search."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import pandas as pd

from factory.islands import DEFAULT_ISLANDS, aggregate_islands, run_island, small_islands


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2018-01-01")
    ap.add_argument("--out-dir", default="reports/islands")
    ap.add_argument("--smoke", action="store_true", help="Run two tiny islands for verification.")
    ap.add_argument("--population", type=int, default=4, help="Smoke population size.")
    ap.add_argument("--generations", type=int, default=1, help="Smoke generation count.")
    ap.add_argument("--create-worktrees", action="store_true", help="Create optional git worktrees under .worktrees/.")
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    specs = small_islands(args.population, args.generations) if args.smoke else DEFAULT_ISLANDS
    manifests = []
    audits = []
    for spec in specs:
        print(f"\n[island] {spec.name} niche={spec.niche} seed={spec.seed}")
        manifest, island_audits = run_island(
            spec,
            start=args.start,
            out_dir=args.out_dir,
            create_worktree=args.create_worktrees,
        )
        manifests.append(manifest)
        audits.extend({**row, "island": spec.name, "island_hypothesis": spec.hypothesis} for row in island_audits)
        print(
            f"[island] evaluated={manifest['evaluated']} "
            f"review={manifest['review_candidates']} "
            f"precheck={manifest['registry_precheck']}"
        )

    summary, front = aggregate_islands(manifests, audits, out_dir=args.out_dir)
    print(
        f"\nStage 1.6 islands total_precheck={summary['total_registry_precheck']} "
        f"incubate={summary['total_incubate']} "
        f"pareto_candidates={summary['pareto_candidates']} acceptance_met={summary['acceptance_met']}"
    )
    if front:
        view = pd.DataFrame(front)
        cols = [
            "island", "registry_precheck", "niche", "family", "version", "desc",
            "in_sample_annual", "in_sample_maxdd", "oos_annual", "pressure_maxdd",
            "cost_up_annual", "source_corr_to_baseline",
            "pairwise_corr_max",
        ]
        print(view[cols].head(args.top).to_string(index=False, formatters={
            "in_sample_annual": "{:+.1%}".format,
            "in_sample_maxdd": "{:+.1%}".format,
            "oos_annual": "{:+.1%}".format,
            "pressure_maxdd": "{:+.1%}".format,
            "cost_up_annual": "{:+.1%}".format,
            "source_corr_to_baseline": lambda x: "" if pd.isna(x) else f"{x:+.2f}",
            "pairwise_corr_max": lambda x: "" if pd.isna(x) else f"{x:+.2f}",
        }))
    print(f"\nSaved: {Path(args.out_dir) / 'candidate_batch.json'}")
    print(f"Incubation: {Path(args.out_dir) / 'incubation_pool.json'}")
    print(f"Summary: {Path(args.out_dir) / 'summary.json'}")


if __name__ == "__main__":
    main()
