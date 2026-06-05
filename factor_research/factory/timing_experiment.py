"""Independent-timing experiment for fundamental/defensive sleeves.

For each seed candidate (drawn from the 1.12 incubation pool plus the island
incubation pool) we sweep the independent timing genes from
``factory.timing.INDEPENDENT_TIMING_GENES`` and run the standard 3-segment audit
(2018 in-sample / 2023 OOS / 2010 pressure) plus a +50% cost-up check.

Goal: find >=1 candidate that, with a *market-wide* (non small-cap) timing gene,
clears all three gates simultaneously:
    maxdd > -20%  &  annual > 15%  &  corr_to_baseline < 0.5
on every segment, where the baseline is small-cap-size (small_cap_ma16).

Run:
    python3 -m factory.timing_experiment           # full sweep -> reports/timing
    python3 -m factory.timing_experiment --quick    # 3 seeds x 4 genes smoke
"""
import argparse
import json
from dataclasses import replace
from pathlib import Path

from core.backtest import CostModel
from factory.evaluator import evaluate_candidate, prepare_context
from factory.search_space import Candidate
from factory.timing import INDEPENDENT_TIMING_GENES

PERIODS = {"in_sample": "2018-01-01", "oos": "2023-01-01", "pressure": "2010-01-01"}

# Seed candidates: top distinct configs from the 1.12 parallel incubation pool
# (near 15% annual, drawdown out of control under small_cap_ma16) + the two
# defensive/reversal island incubation candidates. Factors are NOT modified
# here -- only the timing gene is swept.
SEED_CANDIDATES = [
    Candidate("fund-epsyield-bpvalue", "seed01",
              "fund_eps_yield_pctile+fund_bp_value_ind_rank",
              ["fund_eps_yield_pctile", "fund_bp_value_ind_rank"], [0.2766, 0.7234],
              top_n=40, rebalance_days=60, leverage=1.25),
    Candidate("fund-bpvalue-growth-rank", "seed02",
              "fund_bp_value_ind_rank+fund_profit_growth_ind_rank",
              ["fund_bp_value_ind_rank", "fund_profit_growth_ind_rank"], [0.603, 0.397],
              top_n=80, rebalance_days=80, leverage=1.25),
    Candidate("fund-epsyield-bp-cfo", "seed03",
              "fund_eps_yield_pctile+fund_bp_value+fund_cfo_ind_rank",
              ["fund_eps_yield_pctile", "fund_bp_value", "fund_cfo_ind_rank"], [0.2597, 0.3438, 0.3965],
              top_n=25, rebalance_days=60, leverage=1.25),
    Candidate("fund-growth-delta", "seed04",
              "fund_profit_growth_delta+fund_revenue_growth+fund_profit_growth",
              ["fund_profit_growth_delta", "fund_revenue_growth", "fund_profit_growth"], [0.3562, 0.1869, 0.4569],
              top_n=25, rebalance_days=20, leverage=1.0),
    Candidate("fund-bpvalue-rank", "seed05",
              "fund_bp_value_ind_rank",
              ["fund_bp_value_ind_rank"], [1.0],
              top_n=40, rebalance_days=20, leverage=1.0),
    Candidate("fund-bpvalue-neutral", "seed06",
              "fund_bp_value_ind_neutral",
              ["fund_bp_value_ind_neutral"], [1.0],
              top_n=120, rebalance_days=40, leverage=1.0),
    Candidate("fund-growth-delta-solo", "seed07",
              "fund_profit_growth_delta",
              ["fund_profit_growth_delta"], [1.0],
              top_n=80, rebalance_days=20, leverage=1.0),
    Candidate("defensive-liquidity", "seed08",
              "liquidity_dryup20+range_compression20",
              ["liquidity_dryup20", "range_compression20"], [0.6863, 0.3137],
              top_n=40, rebalance_days=40, leverage=1.25),
    Candidate("reversal-liquidity", "seed09",
              "low_turnover5+low_turnover10+reversal20",
              ["low_turnover5", "low_turnover10", "reversal20"], [0.3433, 0.4481, 0.2086],
              top_n=25, rebalance_days=60, leverage=1.0),
]


def _summarize(label, row):
    return {
        f"{label}_annual": row["annual"],
        f"{label}_maxdd": row["maxdd"],
        f"{label}_sharpe": row["sharpe"],
        f"{label}_corr": row["corr_to_baseline"],
        f"{label}_turnover_pa": row["turnover_pa"],
    }


def three_gate_pass(audit):
    """All three segments simultaneously clear the registration gates."""
    for label in PERIODS:
        if audit.get(f"{label}_annual", -9) <= 0.15:
            return False
        if audit.get(f"{label}_maxdd", -9) <= -0.20:
            return False
        corr = audit.get(f"{label}_corr")
        if corr is not None and abs(corr) >= 0.50:
            return False
    # cost-up sanity (kept generous; full gate is the three segments)
    return audit.get("cost_up_annual", -9) > 0.10


def _diagnose(audit):
    """Which gate(s) fail, per segment, for negative-result reporting."""
    fails = []
    for label in PERIODS:
        if audit.get(f"{label}_annual", -9) <= 0.15:
            fails.append(f"{label}:annual")
        if audit.get(f"{label}_maxdd", -9) <= -0.20:
            fails.append(f"{label}:maxdd")
        corr = audit.get(f"{label}_corr")
        if corr is not None and abs(corr) >= 0.50:
            fails.append(f"{label}:corr")
    if audit.get("cost_up_annual", -9) <= 0.10:
        fails.append("cost_up:annual")
    return fails


def run_experiment(seeds, genes, out_dir="reports/timing"):
    contexts = {label: prepare_context(start) for label, start in PERIODS.items()}
    cost_up = CostModel(buy_cost=CostModel().buy_cost * 1.5,
                        sell_cost=CostModel().sell_cost * 1.5,
                        financing_rate=CostModel().financing_rate)
    audits = []
    for seed in seeds:
        for gene in genes:
            cand = replace(seed, timing=gene, version=f"{seed.version}.{gene}")
            audit = {
                "seed_family": seed.family,
                "timing": gene,
                "desc": seed.desc,
                "config": cand.to_dict(),
            }
            for label, start in PERIODS.items():
                engine, library, baseline_result = contexts[label]
                row = evaluate_candidate(cand, engine, library, baseline_result, start)
                audit.update(_summarize(label, row))
            engine, library, baseline_result = contexts["in_sample"]
            cost_row = evaluate_candidate(cand, engine, library, baseline_result,
                                          PERIODS["in_sample"], cost_model=cost_up)
            audit["cost_up_annual"] = cost_row["annual"]
            audit["cost_up_maxdd"] = cost_row["maxdd"]
            audit["three_gate_pass"] = three_gate_pass(audit)
            audit["fails"] = _diagnose(audit)
            audits.append(audit)
            flag = "PASS" if audit["three_gate_pass"] else "    "
            print(f"[{flag}] {seed.family:<26} {gene:<26} "
                  f"is={audit['in_sample_annual']:+.3f}/{audit['in_sample_maxdd']:+.3f}/c{audit['in_sample_corr']:.2f} "
                  f"oos={audit['oos_annual']:+.3f}/{audit['oos_maxdd']:+.3f} "
                  f"pr={audit['pressure_annual']:+.3f}/{audit['pressure_maxdd']:+.3f}")
    audits.sort(key=lambda a: (not a["three_gate_pass"], -a["in_sample_annual"]))
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "timing_sweep_audit.json").write_text(json.dumps(audits, ensure_ascii=False, indent=2))
    passes = [a for a in audits if a["three_gate_pass"]]
    summary = {
        "seeds": len(seeds),
        "genes": len(genes),
        "rows": len(audits),
        "three_gate_pass": len(passes),
        "pass_list": [{"family": a["seed_family"], "timing": a["timing"]} for a in passes],
    }
    (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary, audits


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="3 seeds x 4 genes smoke test")
    ap.add_argument("--out", default="reports/timing")
    args = ap.parse_args()
    if args.quick:
        seeds = SEED_CANDIDATES[:3]
        genes = ["none", "bigcap_trend_200", "vol_target_18", "vol_target_trend_18_200"]
    else:
        seeds = SEED_CANDIDATES
        genes = INDEPENDENT_TIMING_GENES
    summary, _ = run_experiment(seeds, genes, out_dir=args.out)
    print("\nSUMMARY:", json.dumps(summary, ensure_ascii=False))
