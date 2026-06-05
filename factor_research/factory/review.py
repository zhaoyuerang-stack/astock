"""Review shortlist candidates before registry pre-admission."""
import json
from pathlib import Path

from core.backtest import CostModel
from factory.evaluator import evaluate_candidate, prepare_context
from core.engine import BacktestEngine
from factory.niches import annotate_niches
from factory.search_space import Candidate


DEFAULT_PERIODS = {
    "in_sample": "2018-01-01",
    "oos": "2023-01-01",
    "pressure": "2010-01-01",
}


def candidate_from_config(config, fallback_version):
    return Candidate(
        family=config.get("family", "factory-review"),
        version=config.get("version", fallback_version),
        desc=config.get("desc", fallback_version),
        factors=config["factors"],
        weights=config["weights"],
        top_n=config.get("top_n", 25),
        rebalance_days=config.get("rebalance_days", 20),
        leverage=config.get("leverage", 1.0),
        timing=config.get("timing", "small_cap_ma16"),
    )


def load_shortlist(path, include_all=False):
    rows = json.loads(Path(path).read_text())
    if include_all:
        selected = rows
    else:
        selected = [row for row in rows if row.get("review_candidate")]
    candidates = []
    for i, row in enumerate(selected, 1):
        config = dict(row.get("config", {}))
        config.setdefault("family", row.get("family"))
        config.setdefault("version", row.get("version"))
        config.setdefault("desc", row.get("desc"))
        if "factors" not in config or "weights" not in config:
            continue
        candidates.append((row, candidate_from_config(config, f"review.{i:03d}")))
    return candidates


def _summarize(label, row):
    return {
        f"{label}_annual": row["annual"],
        f"{label}_maxdd": row["maxdd"],
        f"{label}_sharpe": row["sharpe"],
        f"{label}_turnover_pa": row["turnover_pa"],
        f"{label}_cost_drag_pa": row["cost_drag_pa"],
        f"{label}_corr_to_baseline": row["corr_to_baseline"],
        f"{label}_hit_single": row["hit_single"],
    }


def _review_pass(audit_row):
    return (
        audit_row.get("in_sample_annual", 0) > 0.15
        and audit_row.get("in_sample_maxdd", -1) > -0.20
        and audit_row.get("oos_annual", -1) > 0
        and audit_row.get("pressure_maxdd", -1) > -0.35
        and audit_row.get("cost_up_annual", -1) > 0.08
        and audit_row.get("size_exposure", 1) < 1
    )


def _incubation_score(audit_row):
    score = 0.0
    score += max(audit_row.get("in_sample_annual", 0), -0.10)
    score += 0.35 * max(audit_row.get("oos_annual", 0), -0.10)
    score += 0.20 * max(audit_row.get("cost_up_annual", 0), -0.10)
    score += 0.10 * audit_row.get("in_sample_sharpe", 0)
    score += 0.15 * (1.0 - abs(audit_row.get("source_corr_to_baseline") or 1.0))
    score += audit_row.get("in_sample_maxdd", -1)
    return score


def _incubation_reason(audit_row):
    reasons = []
    if audit_row.get("size_exposure", 1) < 1:
        reasons.append("non_pure_size")
    corr = audit_row.get("source_corr_to_baseline")
    if corr is not None and abs(corr) < 0.75:
        reasons.append("low_baseline_corr")
    elif corr is not None and abs(corr) < 0.85:
        reasons.append("diversifying_corr")
    if audit_row.get("oos_annual", -1) > 0:
        reasons.append("oos_positive")
    if audit_row.get("pressure_maxdd", -1) > -0.50:
        reasons.append("pressure_not_broken")
    if audit_row.get("cost_up_annual", -1) > 0:
        reasons.append("cost_up_positive")
    if audit_row.get("in_sample_annual", 0) > 0.03:
        reasons.append("weak_positive_alpha")
    return reasons


def _incubate(audit_row):
    if audit_row.get("registry_precheck"):
        return False
    reasons = _incubation_reason(audit_row)
    if audit_row.get("size_exposure", 1) >= 1:
        return False
    if "low_baseline_corr" not in reasons and "diversifying_corr" not in reasons:
        return False
    return (
        "oos_positive" in reasons
        or "pressure_not_broken" in reasons
        or "cost_up_positive" in reasons
        or audit_row.get("in_sample_annual", 0) > 0.05
    )


def annotate_incubation(audit_row):
    audit_row["incubation_score"] = _incubation_score(audit_row)
    audit_row["incubation_reason"] = _incubation_reason(audit_row)
    audit_row["incubate"] = _incubate(audit_row)
    return audit_row


def audit_candidates(shortlist, periods=None):
    periods = periods or DEFAULT_PERIODS
    contexts = {
        label: prepare_context(start)
        for label, start in periods.items()
    }
    cost_up = CostModel(
        buy_cost=CostModel().buy_cost * 1.5,
        sell_cost=CostModel().sell_cost * 1.5,
        financing_rate=CostModel().financing_rate,
    )
    audits = []
    for source_row, candidate in shortlist:
        audit = {
            "family": candidate.family,
            "version": candidate.version,
            "desc": candidate.desc,
            "config": candidate.to_dict(),
            "source_generation": source_row.get("generation"),
            "source_niche": source_row.get("niche"),
            "source_corr_to_baseline": source_row.get("corr_to_baseline"),
            "source_rank_score": source_row.get("rank_score"),
        }
        for label, start in periods.items():
            engine, library, baseline_result = contexts[label]
            row = evaluate_candidate(candidate, engine, library, baseline_result, start)
            audit.update(_summarize(label, row))

        engine, library, baseline_result = contexts["in_sample"]
        cost_row = evaluate_candidate(
            candidate, engine, library, baseline_result,
            periods["in_sample"], cost_model=cost_up,
        )
        audit.update(_summarize("cost_up", cost_row))
        if audit.get("source_corr_to_baseline") is None:
            audit["source_corr_to_baseline"] = audit.get("in_sample_corr_to_baseline")
        audit = annotate_niches([audit])[0]
        audit["registry_precheck"] = _review_pass(audit)
        audit = annotate_incubation(audit)
        audits.append(audit)
    return sorted(
        audits,
        key=lambda row: (
            not row["registry_precheck"],
            not row["incubate"],
            -row.get("incubation_score", -9),
        ),
    )


def write_audit(input_path, output_path=None, include_all=False):
    shortlist = load_shortlist(input_path, include_all=include_all)
    audits = audit_candidates(shortlist) if shortlist else []
    out = Path(output_path) if output_path else Path(input_path).with_name(Path(input_path).stem + "_audit.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(audits, ensure_ascii=False, indent=2))
    return out, audits
