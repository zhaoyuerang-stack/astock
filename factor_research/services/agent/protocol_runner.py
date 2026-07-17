"""Minimal protocol runner (ADR-037): validate protocol + tool pairing."""
from __future__ import annotations

from typing import Any

from services.agent.protocols import assert_tool_allowed, get_protocol, list_protocols
from services.agent.tools import tool_registry


def run_protocol_step(
    protocol_id: str,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    confirm_token: str | None = None,
) -> dict[str, Any]:
    """Execute one tool under a registered protocol (Strict rail)."""
    from apps.agent_cli import call_capability

    spec = get_protocol(protocol_id)
    assert_tool_allowed(protocol_id, tool_name)
    result = call_capability(
        tool_name,
        arguments or {},
        confirm_token=confirm_token,
        readonly_only=False,
    )
    return {
        "protocol_id": protocol_id,
        "tool": tool_name,
        "default_tier": spec.default_tier.value,
        "requires_hitl": spec.requires_hitl,
        "result": result,
    }


def describe_protocols() -> list[dict[str, Any]]:
    return list_protocols()
