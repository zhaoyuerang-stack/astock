from __future__ import annotations

import json

import pytest

from apps.agent_cli import AgentCliError, call_capability, capability_catalog, main
from services.agent.tools import RISK_HIGH, RISK_READONLY, Tool


def _registry() -> dict[str, Tool]:
    return {
        "profile": Tool("profile", RISK_READONLY, "profile", lambda code: {"code": code}, ("code",)),
        "rebalance": Tool("rebalance", RISK_HIGH, "rebalance", None),
    }


def test_catalog_only_exposes_executable_readonly_capabilities():
    assert capability_catalog(_registry()) == [
        {
            "name": "profile",
            "description": "profile",
            "risk": "readonly",
            "arguments": ["code"],
        }
    ]


def test_call_capability_checks_risk_and_exact_arguments():
    assert call_capability("profile", {"code": "600519"}, _registry()) == {"code": "600519"}

    with pytest.raises(AgentCliError, match="not available in readonly mode"):
        call_capability("rebalance", {}, _registry())
    with pytest.raises(AgentCliError, match="unexpected arguments"):
        call_capability("profile", {"code": "600519", "command": "rm"}, _registry())


def test_cli_rejects_non_readonly_tool_with_machine_readable_error(monkeypatch, capsys):
    monkeypatch.setattr("apps.agent_cli.tool_registry", _registry)

    assert main(["call", "--tool", "rebalance", "--args-json", "{}"]) == 2
    error = json.loads(capsys.readouterr().err)
    assert "not available in readonly mode" in error["error"]
