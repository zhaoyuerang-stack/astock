"""研究实验端点:假设池漏斗 / 假设列表 / 已登记实验。"""
from __future__ import annotations

from fastapi import APIRouter

from contracts.views import FunnelView, HypothesisView, RegisteredExperimentView
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
