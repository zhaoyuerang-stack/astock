"""Machine-readable CLI gateway for the system Agent tool registry (ADR-037).

Readonly tools run freely. Mid-risk tools require --confirm-token matching
ASTOCK_MID_CONFIRM_TOKEN. High-risk tools that only propose are treated as
callable when risk is high but fn is not None (proposals); rebalance stays blocked.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from services.agent.tools import (  # noqa: E402
    RISK_HIGH,
    RISK_LOW,
    RISK_MID,
    RISK_READONLY,
    Tool,
    tool_registry,
)


MAX_ARGUMENTS_BYTES = 16 * 1024
# Optional args for tools that accept more than required minimum.
_OPTIONAL_ARGS = {
    "run_signal_probe": {"idea", "start", "cutoff", "end"},
    "propose_high_risk_action": {"target", "rationale"},
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
        except (TypeError, ValueError):
            pass
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
) -> Any:
    tools = registry if registry is not None else tool_registry()
    tool = tools.get(name)
    if tool is None:
        raise AgentCliError(f"unknown capability: {name}")
    if not callable(tool.fn):
        raise AgentCliError(f"capability is proposal-only / not executable: {name}")
    if readonly_only and tool.risk != RISK_READONLY:
        raise AgentCliError(f"capability is not available in readonly mode: {name}")
    if tool.risk == RISK_HIGH and name == "rebalance":
        raise AgentCliError(f"capability is not available in readonly mode: {name}")

    _check_confirm(tool, confirm_token)

    supplied = arguments or {}
    if not isinstance(supplied, dict):
        raise AgentCliError("arguments must be a JSON object")
    required = set(tool.args)
    optional = _OPTIONAL_ARGS.get(name, set())
    provided = set(supplied)
    missing = sorted(required - provided)
    unexpected = sorted(provided - required - optional)
    if missing:
        raise AgentCliError(f"missing arguments for {name}: {', '.join(missing)}")
    if unexpected:
        raise AgentCliError(f"unexpected arguments for {name}: {', '.join(unexpected)}")
    # Only pass known keys
    kwargs = {k: v for k, v in supplied.items() if k in required or k in optional}
    return tool.fn(**kwargs)


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
