"""GET /governance —— 模型卡与风险治理视图。"""
from __future__ import annotations

from fastapi import APIRouter
from contracts.views import GovernanceView, GateVerdictsView
from services.read.governance import get_governance_overview
from services.read.validation_gate import get_gate_verdicts

router = APIRouter(prefix="/governance", tags=["governance"])

@router.get("", response_model=GovernanceView)
def governance() -> GovernanceView:
    return get_governance_overview()


@router.get("/gate-verdicts", response_model=GateVerdictsView)
def gate_verdicts() -> GateVerdictsView:
    """验证闸门②:全注册表逐版本 9-Gate 裁决面(权威 verdict + 逐门诊断 + 入册卡点)。"""
    return get_gate_verdicts()
