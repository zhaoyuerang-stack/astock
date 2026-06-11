"""系统设置 + 审计 + LLM 配置端点。"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi import APIRouter

from contracts.views import (AuditView, LLMConfigSet, LLMConfigView,
                             LLMTestResult, SystemConfigView)
from services.read.audit import recent_audit
from services.read.settings import system_config

router = APIRouter(prefix="/settings", tags=["settings"])

_CONFIG_AUDIT = Path(__file__).resolve().parents[2] / "data_lake" / "agent" / "config_audit.jsonl"


@router.get("/config", response_model=SystemConfigView)
def config() -> SystemConfigView:
    return system_config()


@router.get("/audit", response_model=AuditView)
def audit(limit: int = 40) -> AuditView:
    return recent_audit(limit=limit)


@router.get("/llm", response_model=LLMConfigView)
def get_llm() -> LLMConfigView:
    from services.agent.llm_adapter import llm_config_masked
    return LLMConfigView(**llm_config_masked())


@router.post("/llm", response_model=LLMConfigView)
def set_llm(body: LLMConfigSet) -> LLMConfigView:
    from services.agent.llm_adapter import llm_config_masked, save_runtime_config
    save_runtime_config(body.provider, body.model, body.base_url, body.api_key)
    _audit_config(f"set LLM provider={body.provider} model={body.model}", "key 已更新" if body.api_key else "保留原 key")
    return LLMConfigView(**llm_config_masked())


@router.post("/llm/test", response_model=LLMTestResult)
def test_llm_endpoint() -> LLMTestResult:
    from services.agent.llm_adapter import test_llm
    return LLMTestResult(**test_llm())


def _audit_config(summary: str, detail: str) -> None:
    """配置变更入审计(SPEC §12.2);绝不记录 key。"""
    try:
        _CONFIG_AUDIT.parent.mkdir(parents=True, exist_ok=True)
        with _CONFIG_AUDIT.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"date": str(date.today()), "summary": summary,
                                "detail": detail, "actor": "human"}, ensure_ascii=False) + "\n")
    except OSError:
        pass
