"""Agent 工具白名单 + 不越权分级(SPEC §9.2 / WEB_DESIGN §14.2)。

Phase 0:空白名单 + 风险分级常量。Phase 5 把 services.read/actions 注册成工具。
铁律:Agent 只能调白名单工具;中/高风险动作 requires_human_confirmation。
"""
from __future__ import annotations

# 风险分级 → 是否需人工二次确认
RISK_READONLY = "readonly"      # 解释/摘要 → 自动
RISK_LOW = "low"                # 生成报告/草稿 → 自动或轻确认
RISK_MID = "mid"                # 改参数/批量实验 → 必须确认
RISK_HIGH = "high"              # 调仓/下单/改风控规则 → 必须确认

REQUIRES_CONFIRMATION = {RISK_MID, RISK_HIGH}

# Phase 0:空。Phase 5 形如 {"run_backtest": (callable, RISK_MID), ...}
TOOL_WHITELIST: dict[str, tuple] = {}


def requires_confirmation(risk_level: str) -> bool:
    return risk_level in REQUIRES_CONFIRMATION
