"""Machine-readable CLI gateway for the system Agent tool registry.

Only readonly tools with concrete implementations are executable here. The
desktop Pi runtime consumes this interface instead of receiving shell access.
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

from services.agent.tools import RISK_READONLY, Tool, tool_registry


MAX_ARGUMENTS_BYTES = 16 * 1024


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


def _readonly_tools(registry: dict[str, Tool] | None = None) -> dict[str, Tool]:
    tools = registry if registry is not None else tool_registry()
    return {
        name: tool
        for name, tool in tools.items()
        if tool.risk == RISK_READONLY and callable(tool.fn)
    }


def capability_catalog(registry: dict[str, Tool] | None = None) -> list[dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.desc,
            "risk": tool.risk,
            "arguments": list(tool.args),
        }
        for tool in _readonly_tools(registry).values()
    ]


def call_capability(
    name: str,
    arguments: dict[str, Any] | None = None,
    registry: dict[str, Tool] | None = None,
) -> Any:
    tools = registry if registry is not None else tool_registry()
    tool = tools.get(name)
    if tool is None:
        raise AgentCliError(f"unknown capability: {name}")
    if tool.risk != RISK_READONLY or not callable(tool.fn):
        raise AgentCliError(f"capability is not available in readonly mode: {name}")

    supplied = arguments or {}
    if not isinstance(supplied, dict):
        raise AgentCliError("arguments must be a JSON object")
    required = set(tool.args)
    provided = set(supplied)
    missing = sorted(required - provided)
    unexpected = sorted(provided - required)
    if missing:
        raise AgentCliError(f"missing arguments for {name}: {', '.join(missing)}")
    if unexpected:
        raise AgentCliError(f"unexpected arguments for {name}: {', '.join(unexpected)}")
    return tool.fn(**supplied)


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
    parser = argparse.ArgumentParser(prog="agent_cli", description="Readonly system capability gateway")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("catalog", help="List executable readonly capabilities")
    call_parser = subparsers.add_parser("call", help="Execute one readonly capability")
    call_parser.add_argument("--tool", required=True, help="Capability name from catalog")
    call_parser.add_argument("--args-json", default="{}", help="JSON object containing exact capability arguments")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "catalog":
            _emit({"capabilities": capability_catalog()})
            return 0
        payload = call_capability(args.tool, _parse_arguments(args.args_json))
        _emit({"capability": args.tool, "result": payload})
        return 0
    except AgentCliError as exc:
        _emit({"error": str(exc)}, sys.stderr)
        return 2
    except Exception as exc:  # Fail closed without leaking a Python traceback to the model.
        _emit({"error": f"capability execution failed: {exc}"}, sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
