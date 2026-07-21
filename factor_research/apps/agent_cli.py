"""Machine-readable CLI gateway for the system Agent tool registry (ADR-037).

Readonly tools run freely. Mid-risk tools require --confirm-token matching
ASTOCK_MID_CONFIRM_TOKEN. High-risk tools that only propose are treated as
callable when risk is high but fn is not None (proposals); rebalance stays blocked.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

logger = logging.getLogger(__name__)

from services.agent.tools import (  # noqa: E402
    RISK_HIGH,
    RISK_MID,
    RISK_READONLY,
    Tool,
    tool_registry,
)

MAX_ARGUMENTS_BYTES = 16 * 1024
# Optional args for tools that accept more than required minimum.
_OPTIONAL_ARGS = {
    "run_signal_probe": {"idea", "start", "cutoff", "end", "universe", "full"},
    "propose_high_risk_action": {"target", "rationale"},
    "run_backtest": {"start", "top_n", "rebalance_days", "factor_window", "timing_ma", "family", "version"},
}


class AgentCliError(RuntimeError):
    """Expected user/tool error with a stable CLI exit path."""


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump())
    if hasattr(value, "item"):
        try:
            return _jsonable(value.item())
        except (TypeError, ValueError) as exc:
            # numpy scalar 转换失败则回退 str(value) 路径,不阻断 CLI 序列化
            logger.warning("agent_cli _jsonable item() failed: %s", exc)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return str(value)


def _catalog_tools(registry: dict[str, Tool] | None = None) -> dict[str, Tool]:
    """Expose tools that are executable via CLI (callable fn)."""
    tools = registry if registry is not None else tool_registry()
    return {name: tool for name, tool in tools.items() if callable(tool.fn)}


def capability_catalog(registry: dict[str, Tool] | None = None) -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.desc,
            "risk": tool.risk,
            "arguments": list(tool.args),
            "requires_confirm": tool.risk in {RISK_MID, RISK_HIGH} and tool.risk != RISK_HIGH
            or tool.risk == RISK_MID,
        }
        for tool in _catalog_tools(registry).values()
    ]


def _check_confirm(tool: Tool, confirm_token: str | None) -> None:
    if tool.risk != RISK_MID:
        return
    expected = os.environ.get("ASTOCK_MID_CONFIRM_TOKEN", "")
    if not expected:
        raise AgentCliError(
            "mid-risk capability requires ASTOCK_MID_CONFIRM_TOKEN in environment "
            "and matching --confirm-token (ADR-037 HITL)"
        )
    if not confirm_token or confirm_token != expected:
        raise AgentCliError(
            "mid-risk capability denied: missing or invalid --confirm-token"
        )


def call_capability(
    name: str,
    arguments: dict[str, Any] | None = None,
    registry: dict[str, Tool] | None = None,
    *,
    confirm_token: str | None = None,
    readonly_only: bool = False,
    audit_context: dict[str, Any] | None = None,
) -> Any:
    """Execute one capability; append-only audit via services.agent.audit (ADR-037 P6.4)."""
    from services.agent.audit import audit_event

    tools = registry if registry is not None else tool_registry()
    tool = tools.get(name)

    def _audit_ctx(risk: str | None) -> dict[str, Any]:
        ctx: dict[str, Any] = {
            "risk": risk,
            "confirm_token_present": bool(confirm_token),
            "readonly_only": bool(readonly_only),
        }
        if audit_context:
            ctx.update(audit_context)
        return ctx

    def _audit_error(exc: BaseException, risk: str | None) -> None:
        audit_event(
            name,
            arguments,
            outcome="error",
            error=exc,
            context=_audit_ctx(risk),
        )

    if tool is None:
        exc = AgentCliError(f"unknown capability: {name}")
        _audit_error(exc, None)
        raise exc
    if not callable(tool.fn):
        exc = AgentCliError(f"capability is proposal-only / not executable: {name}")
        _audit_error(exc, tool.risk)
        raise exc
    if readonly_only and tool.risk != RISK_READONLY:
        exc = AgentCliError(f"capability is not available in readonly mode: {name}")
        _audit_error(exc, tool.risk)
        raise exc
    if tool.risk == RISK_HIGH and name == "rebalance":
        exc = AgentCliError(f"capability is not available in readonly mode: {name}")
        _audit_error(exc, tool.risk)
        raise exc

    try:
        _check_confirm(tool, confirm_token)
    except AgentCliError as exc:
        _audit_error(exc, tool.risk)
        raise

    supplied = arguments or {}
    if not isinstance(supplied, dict):
        exc = AgentCliError("arguments must be a JSON object")
        _audit_error(exc, tool.risk)
        raise exc
    required = set(tool.args)
    optional = _OPTIONAL_ARGS.get(name, set())
    provided = set(supplied)
    missing = sorted(required - provided)
    unexpected = sorted(provided - required - optional)
    if missing:
        exc = AgentCliError(f"missing arguments for {name}: {', '.join(missing)}")
        _audit_error(exc, tool.risk)
        raise exc
    if unexpected:
        exc = AgentCliError(f"unexpected arguments for {name}: {', '.join(unexpected)}")
        _audit_error(exc, tool.risk)
        raise exc
    # Only pass known keys
    kwargs = {k: v for k, v in supplied.items() if k in required or k in optional}

    try:
        result = tool.fn(**kwargs)
    except Exception as exc:
        _audit_error(exc, tool.risk)
        raise

    audit_event(
        name,
        arguments,
        outcome="ok",
        context=_audit_ctx(tool.risk),
        result=result,
    )
    return result


def _parse_arguments(raw: str) -> dict[str, Any]:
    if len(raw.encode("utf-8")) > MAX_ARGUMENTS_BYTES:
        raise AgentCliError("arguments payload is too large")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AgentCliError(f"invalid arguments JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise AgentCliError("arguments must be a JSON object")
    return value


def _emit(payload: Any, stream: Any = sys.stdout) -> None:
    json.dump(_jsonable(payload), stream, ensure_ascii=False, separators=(",", ":"))
    stream.write("\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent_cli", description="Agent capability gateway (ADR-037)")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("catalog", help="List executable capabilities")
    call_parser = subparsers.add_parser("call", help="Execute one capability")
    call_parser.add_argument("--tool", required=True, help="Capability name from catalog")
    call_parser.add_argument("--args-json", default="{}", help="JSON object of arguments")
    call_parser.add_argument(
        "--confirm-token",
        default="",
        help="Required for mid-risk tools; must match ASTOCK_MID_CONFIRM_TOKEN",
    )
    call_parser.add_argument(
        "--readonly-only",
        action="store_true",
        help="Reject non-readonly tools (legacy desktop filter)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "catalog":
            _emit({"capabilities": capability_catalog()})
            return 0
        payload = call_capability(
            args.tool,
            _parse_arguments(args.args_json),
            confirm_token=args.confirm_token or None,
            readonly_only=bool(args.readonly_only),
        )
        _emit({"capability": args.tool, "result": payload})
        return 0
    except AgentCliError as exc:
        _emit({"error": str(exc)}, sys.stderr)
        return 2
    except Exception as exc:
        _emit({"error": f"capability execution failed: {exc}"}, sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
