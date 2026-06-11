"""POST /agent/ask —— 研究副驾驶(规则式 planner;LLM 可插拔)。"""
from __future__ import annotations

from fastapi import APIRouter

from contracts.views import AgentAskRequest, AgentAskResponse
from services.agent.planner import ask

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/ask", response_model=AgentAskResponse)
def agent_ask(body: AgentAskRequest) -> AgentAskResponse:
    return AgentAskResponse(**ask(body.request, body.context))
