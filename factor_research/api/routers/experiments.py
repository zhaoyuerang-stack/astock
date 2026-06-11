"""研究实验端点:假设池漏斗 / 假设列表 / 已登记实验。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from contracts.views import (
    AutoResearchCandidateView,
    AutoResearchFunnelView,
    AutoResearchIslandSearchResponse,
    AutoResearchLLMGenResponse,
    AutoResearchPromoteResponse,
    AutoResearchReviewItemView,
    AutoResearchReviewRequest,
    AutoResearchRunResponse,
    FunnelView,
    HypothesisView,
    RegisteredExperimentView,
)
from services.actions.autoresearch import (
    promote_approved_candidate,
    review_autoresearch_candidate,
    run_autoresearch_seeds,
)
from services.actions.autoresearch_llm import run_autoresearch_llm
from services.actions.autoresearch_search import run_autoresearch_island_search
from services.read.autoresearch import (
    autoresearch_candidates,
    autoresearch_funnel,
    autoresearch_review_queue,
)
from services.read.experiments import funnel, hypotheses, registered_experiments

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("/funnel", response_model=FunnelView)
def get_funnel() -> FunnelView:
    return funnel()


@router.get("/hypotheses", response_model=list[HypothesisView])
def get_hypotheses(status: str | None = None, limit: int = 60) -> list[HypothesisView]:
    return hypotheses(status=status, limit=limit)


@router.get("/registered", response_model=list[RegisteredExperimentView])
def get_registered() -> list[RegisteredExperimentView]:
    return registered_experiments()


@router.get("/autoresearch/funnel", response_model=AutoResearchFunnelView)
def get_autoresearch_funnel() -> AutoResearchFunnelView:
    return autoresearch_funnel()


@router.get("/autoresearch/candidates", response_model=list[AutoResearchCandidateView])
def get_autoresearch_candidates(limit: int = 60) -> list[AutoResearchCandidateView]:
    return autoresearch_candidates(limit=limit)


@router.get("/autoresearch/review-queue", response_model=list[AutoResearchReviewItemView])
def get_autoresearch_review_queue(limit: int = 60) -> list[AutoResearchReviewItemView]:
    return autoresearch_review_queue(limit=limit)


@router.post("/autoresearch/review/{fingerprint}", response_model=AutoResearchReviewItemView)
def post_autoresearch_review(fingerprint: str, body: AutoResearchReviewRequest) -> AutoResearchReviewItemView:
    """人工复核 approve/reject。approve 不写 LIVE 台账,入册仍走 workflow/promote。"""
    try:
        return review_autoresearch_candidate(fingerprint=fingerprint, action=body.action, notes=body.notes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/autoresearch/run-seeds", response_model=AutoResearchRunResponse)
def post_autoresearch_run_seeds(
    limit: int = 5,
    max_stage: str = "l0",
    start: str = "2018-01-01",
    sample_dates: int | None = 120,
) -> AutoResearchRunResponse:
    return run_autoresearch_seeds(
        limit=limit,
        max_stage=max_stage,
        start=start,
        sample_dates=sample_dates,
    )


@router.post("/autoresearch/promote/{fingerprint}", response_model=AutoResearchPromoteResponse)
def post_autoresearch_promote(fingerprint: str, version: str = "v1.0") -> AutoResearchPromoteResponse:
    """APPROVED 候选 → workflow phase1~4 正式入册(分钟级,phase4 是唯一台账入口)。"""
    try:
        return promote_approved_candidate(fingerprint=fingerprint, version=version)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/autoresearch/run-llm", response_model=AutoResearchLLMGenResponse)
def post_autoresearch_run_llm(
    n: int = 5,
    theme: str = "",
    max_stage: str = "l1",
    start: str = "2018-01-01",
    sample_dates: int | None = 120,
) -> AutoResearchLLMGenResponse:
    """LLM 生成候选并走真实验证线。LLM 未配置 → 400。"""
    try:
        return run_autoresearch_llm(n=n, theme=theme, max_stage=max_stage, start=start, sample_dates=sample_dates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/autoresearch/island-search", response_model=AutoResearchIslandSearchResponse)
def post_autoresearch_island_search(
    islands: int = 4,
    generations: int = 3,
    population: int = 8,
    top_k: int = 5,
    final_stage: str = "l0",
    use_llm: bool = True,
    start: str = "2018-01-01",
    sample_dates: int | None = 120,
) -> AutoResearchIslandSearchResponse:
    """多岛屿进化搜索(分钟级;LLM 可用时按主题播种,否则确定性种子)。"""
    try:
        return run_autoresearch_island_search(
            islands=islands, generations=generations, population=population,
            top_k=top_k, final_stage=final_stage, use_llm=use_llm,
            start=start, sample_dates=sample_dates,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
