"""CLI for self-evolving incubation-pool candidates."""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from factory.self_evolution import EvolutionConfig, run_self_evolution


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default="reports/islands_fundamental_1_12_parallel/incubation_pool.json")
    ap.add_argument("--out-dir", default="reports/incubation_evolution")
    ap.add_argument("--generations", type=int, default=3)
    ap.add_argument("--population", type=int, default=12)
    ap.add_argument("--survivors", type=int, default=6)
    ap.add_argument("--seed", type=int, default=1307)
    ap.add_argument("--mutation-rate", type=float, default=0.45)
    ap.add_argument("--max-factors", type=int, default=3)
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    cfg = EvolutionConfig(
        input_path=args.input,
        out_dir=args.out_dir,
        generations=args.generations,
        population=args.population,
        survivors=args.survivors,
        seed=args.seed,
        mutation_rate=args.mutation_rate,
        max_factors=args.max_factors,
    )
    summary, precheck, incubate = run_self_evolution(cfg)
    print(
        f"\nIncubation self-evolution evaluated={summary['evaluated']} "
        f"precheck={summary['registry_precheck']} incubate={summary['incubate']} "
        f"acceptance={summary['acceptance_met']}"
    )
    for gen in summary["generations"]:
        print(
            f"gen={gen['generation']} candidates={gen['candidates']} "
            f"precheck={gen['registry_precheck']} incubate={gen['incubate']} "
            f"best_score={gen['best_incubation_score']}"
        )

    rows = precheck or incubate
    if rows:
        cols = [
            "registry_precheck", "incubate", "niche", "version", "desc",
            "in_sample_annual", "in_sample_maxdd", "oos_annual",
            "pressure_maxdd", "cost_up_annual", "source_corr_to_baseline",
            "incubation_score",
        ]
        print("\nTop rows")
        print(" | ".join(cols))
        for row in rows[:args.top]:
            values = []
            for col in cols:
                value = row.get(col)
                if col in {"in_sample_annual", "in_sample_maxdd", "oos_annual", "pressure_maxdd", "cost_up_annual"}:
                    values.append("" if value is None else f"{value:+.1%}")
                elif col == "source_corr_to_baseline":
                    values.append("" if value is None else f"{value:+.2f}")
                elif col == "incubation_score":
                    values.append("" if value is None else f"{value:+.3f}")
                else:
                    values.append(str(value))
            print(" | ".join(values))
    print(f"\nSaved: {Path(args.out_dir)}")


if __name__ == "__main__":
    main()
