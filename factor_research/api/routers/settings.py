"""系统设置 + 审计端点:GET /settings/config、/settings/audit。"""
from __future__ import annotations

from fastapi import APIRouter

from contracts.views import AuditView, SystemConfigView
from services.read.audit import recent_audit
from services.read.settings import system_config

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/config", response_model=SystemConfigView)
def config() -> SystemConfigView:
    return system_config()


@router.get("/audit", response_model=AuditView)
def audit(limit: int = 40) -> AuditView:
    return recent_audit(limit=limit)
