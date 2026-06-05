"""Calibration and combination tests for incubation-pool candidates."""
import itertools
import json
from pathlib import Path

from core.backtest import CostModel, metrics
from factory.evaluator import prepare_context, run_candidate
from factory.niches import annotate_niches
from factory.review import audit_candidates, candidate_from_config


def load_incubation_pool(path):
    return json.loads(Path(path).read_text())


def _variant_config(row, top_n, rebalance_days, leverage, suffix):
    config = dict(row["config"])
    config["top_n"] = top_n
    config["rebalance_days"] = rebalance_days
    config["leverage"] = leverage
    config["version"] = f"{config.get('version', 'incubate')}.{suffix}"
    config["desc"] = (
        f"{'+'.join(config['factors'])} top{top_n} "
        f"reb{rebalance_days} lev{leverage:g}"
    )
    return config


def generate_variants(rows, max_variants_per_seed=6):
    """Create conservative variants around incubated candidates."""
    out = []
    seen = set()
    for row in rows:
        base = row["config"]
        top_options = sorted({base.get("top_n", 25), min(max(base.get("top_n", 25), 40), 120), 80, 120})
        reb_options = sorted({base.get("rebalance_days", 20), 60, 80, 120})
        lev_options = sorted({1.0, min(base.get("leverage", 1.0), 1.25)})
        i = 1
        for top_n, rebalance_days, leverage in itertools.product(top_options, reb_options, lev_options):
            key = (tuple(base["factors"]), tuple(round(w, 4) for w in base["weights"]), top_n, rebalance_days, leverage)
            if key in seen:
                continue
            seen.add(key)
            config = _variant_config(row, top_n, rebalance_days, leverage, f"cal{i:02d}")
            out.append({
                "family": config.get("family", row.get("family")),
                "version": config["version"],
                "desc": config["desc"],
                "config": config,
                "source_desc": row.get("desc"),
                "source_incubation_score": row.get("incubation_score"),
                "review_candidate": True,
            })
            i += 1
            if i > max_variants_per_seed:
                break
    return out


def audit_variant_rows(rows):
    shortlist = [
        (row, candidate_from_config(row["config"], row.get("version", f"variant.{i:03d}")))
        for i, row in enumerate(rows, 1)
    ]
    audits = audit_candidates(shortlist)
    source_by_version = {row["config"]["version"]: row for row in rows}
    for audit in audits:
        source = source_by_version.get(audit["config"]["version"], {})
        audit["source_desc"] = source.get("source_desc")
        audit["source_incubation_score"] = source.get("source_incubation_score")
    return audits


def _cost_up():
    base = CostModel()
    return CostModel(
        buy_cost=base.buy_cost * 1.5,
        sell_cost=base.sell_cost * 1.5,
        financing_rate=base.financing_rate,
    )


def _combo_metrics(candidates, start, cost_model=None):
    import pandas as pd

    engine, library, baseline_result = prepare_context(start)
    returns = []
    details = []
    for candidate in candidates:
        result = run_candidate(candidate, engine, library, start, cost_model=cost_model)
        returns.append(result.returns)
        details.append(result.detail)
    common = returns[0].index
    for ret in returns[1:]:
        common = common.intersection(ret.index)
    combo_ret = sum(ret.loc[common] for ret in returns) / len(returns)
    combo_detail = pd.concat([detail.loc[common] for detail in details]).groupby(level=0).mean()
    m = metrics(combo_ret)
    corr = combo_ret.corr(benchmark_ret.loc[combo_ret.index.intersection(benchmark_ret.index)])
    return {
        "annual": float(m["annual"]),
        "maxdd": float(m["maxdd"]),
        "sharpe": float(m["sharpe"]),
        "turnover_pa": float(combo_detail["turnover"].mean() * 252),
        "cost_drag_pa": float(combo_detail["cost"].mean() * 252),
        "corr_to_baseline": float(corr),
    }


def combo_tests(audits, max_members=2):
    pool = [row for row in audits if row.get("incubate") or row.get("registry_precheck")]
    pool = sorted(pool, key=lambda row: -row.get("incubation_score", -9))[:6]
    combos = []
    for members in itertools.combinations(pool, max_members):
        candidates = [candidate_from_config(row["config"], row["version"]) for row in members]
        row = {
            "members": [m["desc"] for m in members],
            "member_versions": [m["version"] for m in members],
            "member_niches": [m.get("niche") for m in members],
        }
        for label, start in [("in_sample", "2018-01-01"), ("oos", "2023-01-01"), ("pressure", "2010-01-01")]:
            stats = _combo_metrics(candidates, start)
            row.update({f"{label}_{k}": v for k, v in stats.items()})
        cost_stats = _combo_metrics(candidates, "2018-01-01", cost_model=_cost_up())
        row.update({f"cost_up_{k}": v for k, v in cost_stats.items()})
        row["combo_precheck"] = (
            row["in_sample_annual"] > 0.12
            and row["in_sample_maxdd"] > -0.20
            and row["oos_annual"] > 0
            and row["pressure_maxdd"] > -0.35
            and row["cost_up_annual"] > 0.06
        )
        combos.append(row)
    return sorted(combos, key=lambda row: (not row["combo_precheck"], -row["in_sample_annual"]))


def write_calibration(input_path, out_dir="reports/incubation", max_variants_per_seed=6):
    rows = load_incubation_pool(input_path)
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)
    variants = generate_variants(rows, max_variants_per_seed=max_variants_per_seed)
    audits = audit_variant_rows(variants) if variants else []
    combos = combo_tests(audits) if audits else []
    (out_root / "variants.json").write_text(json.dumps(variants, ensure_ascii=False, indent=2))
    (out_root / "variant_audit.json").write_text(json.dumps(audits, ensure_ascii=False, indent=2))
    (out_root / "combo_tests.json").write_text(json.dumps(combos, ensure_ascii=False, indent=2))
    summary = {
        "input": str(input_path),
        "seed_candidates": len(rows),
        "variants": len(variants),
        "registry_precheck": sum(bool(row.get("registry_precheck")) for row in audits),
        "incubate": sum(bool(row.get("incubate")) for row in audits),
        "combo_tests": len(combos),
        "combo_precheck": sum(bool(row.get("combo_precheck")) for row in combos),
    }
    (out_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary, audits, combos
