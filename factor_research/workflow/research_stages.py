"""Workflow-owned execution for research workspace L0-L3 stages."""
from __future__ import annotations

from dataclasses import replace
from typing import Callable


class ResearchStageConflict(RuntimeError):
    """The requested stage conflicts with current item state."""


class InvalidResearchStageTransition(ValueError):
    """The requested stage transition is invalid."""


def load_stage_data(start: str):
    from factory.lines.line2_validation.l0_ic_scan import precompute_forward_returns
    from lake.load_lake import load_prices, load_raw_close
    from lake.units import implied_amount

    px = load_prices(start=start, fields=("close", "volume"))
    close, volume = px["close"], px["volume"]
    raw = load_raw_close(start=start).reindex(index=volume.index, columns=volume.columns)
    # canonical lake volume unit = share; amount CNY = shares × raw CNY/share
    amount = implied_amount(volume, raw)
    forward = precompute_forward_returns(close)
    vintage = f"data_lake@{close.index[-1].strftime('%Y-%m-%d')}"
    return close, volume, amount, forward, vintage


def default_stage_runners() -> dict[str, Callable]:
    from factory.lines.line2_validation import run_l0, run_l1, run_l2, run_l3
    return {"l0": run_l0, "l1": run_l1, "l2": run_l2, "l3": run_l3}


def _direction_from_experiments(experiments) -> int:
    for exp in reversed(list(experiments)):
        if getattr(exp.protocol, "value", "") == "l0_ic_scan":
            return -1 if exp.result.details.get("direction") == "short" else 1
    raise ResearchStageConflict("L0 direction evidence is missing")


def run_hypothesis_stage(
    item_id: str,
    stage: str,
    *,
    start: str = "2018-01-01",
    sample_dates: int | None = 120,
    hypothesis_pool=None,
    experiment_log=None,
    data_loader: Callable = load_stage_data,
    runners: dict[str, Callable] | None = None,
) -> dict:
    from factory.ontology import Decision, HypothesisStatus
    from factory.pool.pool_repo import HypothesisPool
    from factory.repositories.experiment_log import ExperimentLog

    expected = {
        "l0": HypothesisStatus.QUEUED,
        "l1": HypothesisStatus.L0_PASSED,
        "l2": HypothesisStatus.L1_PASSED,
        "l3": HypothesisStatus.L2_PASSED,
    }
    advanced = {
        "l0": HypothesisStatus.L0_PASSED,
        "l1": HypothesisStatus.L1_PASSED,
        "l2": HypothesisStatus.L2_PASSED,
        "l3": HypothesisStatus.L3_PASSED,
    }
    if stage not in expected:
        raise InvalidResearchStageTransition(f"unknown stage: {stage}")
    hypothesis_pool = hypothesis_pool if hypothesis_pool is not None else HypothesisPool()
    experiment_log = experiment_log if experiment_log is not None else ExperimentLog()
    item = hypothesis_pool.get(item_id)
    if item is None:
        raise KeyError(item_id)
    if item.status != expected[stage]:
        raise ResearchStageConflict(
            f"stale stage request: {stage} requires {expected[stage].value}, got {item.status.value}"
        )

    close, volume, amount, forward, vintage = data_loader(start)
    runner = (runners or default_stage_runners())[stage]
    if stage == "l0":
        exp = runner(item, close, volume, amount, forward, vintage_id=vintage, sample_dates=sample_dates)
    else:
        direction = _direction_from_experiments(experiment_log.list_by_hypothesis(item_id))
        exp = runner(
            item, close, volume, amount, direction=direction,
            vintage_id=vintage, start=start,
        )
    experiment_log.append(exp)
    if exp.decision == Decision.PROMOTE:
        hypothesis_pool.update_status(item_id, advanced[stage])
    elif exp.decision == Decision.SHELVE:
        hypothesis_pool.update_status(item_id, HypothesisStatus.SHELVED)
    else:
        hypothesis_pool.update_status(item_id, HypothesisStatus.DISCARDED)
    return {
        "kind": "hypothesis",
        "item_id": item_id,
        "stage": stage,
        "experiment_id": exp.experiment_id,
        "decision": exp.decision.value,
        "reason": exp.notes,
        "metrics": exp.result.metrics,
        "error": exp.result.error,
    }


def run_autoresearch_stage(
    item_id: str,
    stage: str,
    *,
    start: str = "2018-01-01",
    sample_dates: int | None = 120,
    candidate_repo=None,
    experiment_log=None,
    legacy_review_queue=None,
    data_loader: Callable = load_stage_data,
    runners: dict[str, Callable] | None = None,
) -> dict:
    from factory.autoresearch import CandidateRepository, ExperimentLog, ReviewQueue, ast_to_hypothesis
    from factory.autoresearch.models import CandidateDecision, CandidateEvaluationResult, CandidateStatus
    from factory.ontology import Decision, HypothesisStatus

    expected = {
        "l0": CandidateStatus.GENERATED,
        "l1": CandidateStatus.L0_PASSED,
        "l2": CandidateStatus.L1_PASSED,
        "l3": CandidateStatus.L2_PASSED,
    }
    hyp_status = {
        "l0": HypothesisStatus.QUEUED,
        "l1": HypothesisStatus.L0_PASSED,
        "l2": HypothesisStatus.L1_PASSED,
        "l3": HypothesisStatus.L2_PASSED,
    }
    passed_status = {
        "l0": CandidateStatus.L0_PASSED,
        "l1": CandidateStatus.L1_PASSED,
        "l2": CandidateStatus.L2_PASSED,
        "l3": CandidateStatus.PROMOTED_TO_REVIEW,
    }
    if stage not in expected:
        raise InvalidResearchStageTransition(f"unknown stage: {stage}")
    candidate_repo = candidate_repo if candidate_repo is not None else CandidateRepository()
    experiment_log = experiment_log if experiment_log is not None else ExperimentLog()
    legacy_review_queue = legacy_review_queue if legacy_review_queue is not None else ReviewQueue()
    candidate = candidate_repo.get(item_id)
    if candidate is None:
        raise KeyError(item_id)
    if candidate.status != expected[stage]:
        raise ResearchStageConflict(
            f"stale stage request: {stage} requires {expected[stage].value}, got {candidate.status.value}"
        )

    close, volume, amount, forward, vintage = data_loader(start)
    runner = (runners or default_stage_runners())[stage]
    hyp = replace(ast_to_hypothesis(candidate), status=hyp_status[stage])
    prior = [row for row in experiment_log.iter_all() if row.fingerprint == item_id]
    if stage == "l0":
        exp = runner(hyp, close, volume, amount, forward, vintage_id=vintage, sample_dates=sample_dates)
    else:
        embedded = []
        for result in prior:
            embedded.extend(result.metrics.get("experiments", []))
        direction = -1 if any(
            row.get("protocol") == "l0_ic_scan"
            and row.get("details", {}).get("direction") == "short"
            for row in embedded
        ) else 1
        exp = runner(hyp, close, volume, amount, direction=direction, vintage_id=vintage, start=start)

    if exp.decision == Decision.PROMOTE:
        status = passed_status[stage]
        decision = CandidateDecision.PROMOTE if stage == "l3" else CandidateDecision.KEEP
    elif exp.decision == Decision.SHELVE:
        status, decision = CandidateStatus.SHELVED, CandidateDecision.SHELVE
    else:
        status, decision = CandidateStatus.DISCARDED, CandidateDecision.DISCARD
    metrics = {"experiments": [{
        "experiment_id": exp.experiment_id,
        "protocol": exp.protocol.value,
        "decision": exp.decision.value,
        "metrics": exp.result.metrics,
        "details": exp.result.details,
        "error": exp.result.error,
        "notes": exp.notes,
    }]}
    result = CandidateEvaluationResult(
        fingerprint=item_id, status=status, decision=decision, metrics=metrics, reason=exp.notes,
    )
    updated = candidate.with_status(status, exp.notes)
    candidate_repo.record(updated)
    experiment_log.append(result)
    if status == CandidateStatus.PROMOTED_TO_REVIEW:
        legacy_review_queue.add(updated, result)
    return {
        "kind": "autoresearch",
        "item_id": item_id,
        "stage": stage,
        "experiment_id": exp.experiment_id,
        "decision": exp.decision.value,
        "reason": exp.notes,
        "metrics": exp.result.metrics,
        "error": exp.result.error,
    }
