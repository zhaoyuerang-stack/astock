"""Actions for running Auto Factor Research candidates through real validation lines."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

import pandas as pd

from contracts.views import (
    AutoResearchPromoteResponse,
    AutoResearchReviewItemView,
    AutoResearchRunResponse,
    AutoResearchRunResultView,
)
from factory.autoresearch import (
    CandidateRepository,
    CandidateStatus,
    ExperimentLog,
    ReviewQueue,
    ast_to_hypothesis,
    generate_seed_candidates,
    run_validation_pipeline,
)


def _load_validation_data(start: str):
    from factory.lines.line2_validation.l0_ic_scan import precompute_forward_returns
    from lake.load_lake import load_prices, load_raw_close

    px = load_prices(start=start, fields=("close", "volume"))
    close, volume = px["close"], px["volume"]
    raw = load_raw_close(start=start).reindex(index=volume.index, columns=volume.columns)
    amount = volume * 100 * raw
    forward_ret = precompute_forward_returns(close)
    return close, volume, amount, forward_ret


def _protocols(result) -> list[str]:
    return [e.get("protocol", "") for e in result.metrics.get("experiments", []) if e.get("protocol")]


def _run_candidates(
    candidates,
    *,
    max_stage: str = "l0",
    start: str = "2018-01-01",
    sample_dates: int | None = 120,
    close: pd.DataFrame | None = None,
    volume: pd.DataFrame | None = None,
    amount: pd.DataFrame | None = None,
    forward_ret: pd.DataFrame | None = None,
    vintage_id: str | None = None,
    repository: CandidateRepository | None = None,
    experiment_log: ExperimentLog | None = None,
    review_queue: ReviewQueue | None = None,
    runners: dict[str, Callable] | None = None,
) -> AutoResearchRunResponse:
    """共用驱动:一批已校验候选走真实 L0/L1/L2/L3 验证线。"""
    if max_stage not in {"l0", "l1", "l2", "l3"}:
        raise ValueError("max_stage must be one of: l0, l1, l2, l3")
    if close is None or volume is None or amount is None or forward_ret is None:
        close, volume, amount, forward_ret = _load_validation_data(start)

    vintage = vintage_id or f"data_lake:{start}:{date.today().isoformat()}"
    results: list[AutoResearchRunResultView] = []
    for candidate in candidates:
        result = run_validation_pipeline(
            candidate,
            close=close,
            volume=volume,
            amount=amount,
            forward_ret=forward_ret,
            vintage_id=vintage,
            repository=repository,
            experiment_log=experiment_log,
            review_queue=review_queue,
            runners=runners,
            sample_dates=sample_dates,
            max_stage=max_stage,
        )
        results.append(
            AutoResearchRunResultView(
                fingerprint=result.fingerprint,
                status=result.status.value,
                decision=result.decision.value,
                reason=result.reason,
                protocols=_protocols(result),
            )
        )
    return AutoResearchRunResponse(vintage_id=vintage, max_stage=max_stage, results=results)


def run_autoresearch_seeds(*, limit: int = 5, **kw) -> AutoResearchRunResponse:
    """Run deterministic seed candidates through L0/L1/L2/L3.

    Default max_stage is L0 because L1-L3 are real backtests and can be slow.
    Passing max_stage='l3' uses the existing canonical factory validation lines.
    """
    return _run_candidates(list(generate_seed_candidates(limit=limit)), **kw)


def review_autoresearch_candidate(
    *,
    fingerprint: str,
    action: str,
    notes: str = "",
    repository: CandidateRepository | None = None,
    review_queue: ReviewQueue | None = None,
) -> AutoResearchReviewItemView:
    """Human approve/reject for a promoted candidate.

    Approve 只把状态推进到 APPROVED——不写 LIVE 台账;
    入册仍走唯一通道 workflow/promote.py(后续独立步骤)。
    """
    if action not in {"approve", "reject"}:
        raise ValueError("action must be 'approve' or 'reject'")
    repository = repository or CandidateRepository()
    review_queue = review_queue or ReviewQueue()

    item = review_queue.get(fingerprint)
    if item is None:
        raise ValueError(f"fingerprint not in review queue: {fingerprint}")
    if item.get("status") != CandidateStatus.PROMOTED_TO_REVIEW.value:
        raise ValueError(f"candidate is not pending review (status={item.get('status')})")

    status = CandidateStatus.APPROVED if action == "approve" else CandidateStatus.REJECTED_BY_HUMAN
    candidate = repository.get(fingerprint)
    if candidate is not None:
        repository.record(candidate.with_status(status, notes or f"human {action}"))
    rec = review_queue.record_decision(
        fingerprint,
        status,
        action=action,
        notes=notes,
        reviewed_at=date.today().isoformat(),
    )
    return AutoResearchReviewItemView(**rec)


def promote_approved_candidate(
    *,
    fingerprint: str,
    version: str = "v1.0",
    run_marginal: bool = False,
    repository: CandidateRepository | None = None,
    review_queue: ReviewQueue | None = None,
    promote_fn: Callable | None = None,
) -> AutoResearchPromoteResponse:
    """APPROVED 候选 → workflow phase1~4 正式入册的"最后一公里"。

    入册唯一通道不变:这里只是把候选翻译成 factory Hypothesis 后交给
    workflow.promote.promote_hypothesis(phase1 合成防未来审计 → phase2/3 → phase4 唯一登记)。
    本函数自身绝不写台账。
    """
    repository = repository or CandidateRepository()
    review_queue = review_queue or ReviewQueue()

    item = review_queue.get(fingerprint)
    if item is None:
        raise ValueError(f"fingerprint not in review queue: {fingerprint}")
    if item.get("review_action") != "approve":
        raise ValueError(f"candidate is not approved (review_action={item.get('review_action') or 'pending'})")
    candidate = repository.get(fingerprint)
    if candidate is None:
        raise ValueError(f"fingerprint not in candidate repository: {fingerprint}")

    if promote_fn is None:
        from workflow.promote import promote_hypothesis

        promote_fn = promote_hypothesis

    hyp = ast_to_hypothesis(candidate)
    report = promote_fn(hyp, version=version, run_marginal=run_marginal)

    registered = bool(report is not None and getattr(report, "registered", False))
    detail = getattr(report, "detail", "") if report is not None else "知识图谱 gate 跳过"
    note = f"registered {hyp.name}/{version}" if registered else f"promotion not registered: {detail or 'gates not met'}"
    repository.record(candidate.with_status(candidate.status, note))
    return AutoResearchPromoteResponse(
        fingerprint=fingerprint,
        hypothesis_name=hyp.name,
        version=version,
        registered=registered,
        detail=detail,
    )
