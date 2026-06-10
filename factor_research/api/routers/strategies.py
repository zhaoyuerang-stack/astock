"""GET /strategies —— 台账 family/version 只读列表。"""
from __future__ import annotations

from fastapi import APIRouter

from contracts.views import StrategyView
from services.read.registry import list_strategies

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=list[StrategyView])
def strategies() -> list[StrategyView]:
    return list_strategies()
