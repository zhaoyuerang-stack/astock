"""GET /governance —— 模型卡与风险治理视图。"""
from __future__ import annotations

from fastapi import APIRouter
from contracts.views import GovernanceView
from services.read.governance import get_governance_overview

router = APIRouter(prefix="/governance", tags=["governance"])

@router.get("", response_model=GovernanceView)
def governance() -> GovernanceView:
    return get_governance_overview()
