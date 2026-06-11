"""LLM 适配器 —— Agent 的"大脑"接口,可插拔。

Phase 5:默认 NullAdapter(无 LLM,planner 走确定性 intent 路由)。
给 ANTHROPIC_API_KEY + 装 anthropic SDK,换成 ClaudeAdapter 即接真模型 ——
**planner/工具/不越权 全不变**,只是 route() 从关键词路由换成真推理。
"""
from __future__ import annotations

import os


class LLMAdapter:
    def available(self) -> bool:
        return False

    def route(self, request: str, context: dict, tool_names: list[str]) -> str | None:
        """返回应调用的工具名,或 None(走确定性 fallback)。"""
        return None


class NullAdapter(LLMAdapter):
    """无 LLM。planner 自行做确定性关键词/页面上下文路由。"""


def get_adapter() -> LLMAdapter:
    # 有 key 且装了 SDK → 未来在此返回 ClaudeAdapter();当前一律 NullAdapter。
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic  # noqa: F401
            # return ClaudeAdapter()   # Phase 5+:真模型接入点
        except ImportError:
            pass
    return NullAdapter()


def llm_ready() -> bool:
    return get_adapter().available()
