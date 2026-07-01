"""Agent action policy tests.

Run:
    cd factor_research && python3 tests/test_agent_action_policy.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.agent_control import AgentAction
from services.read.action_policy import can_agent_do


def test_registry_direct_write_is_blocked():
    decision = can_agent_do(AgentAction.WRITE_REGISTRY, "strategy_versions.json")
    assert decision.allowed is False
    assert decision.required_entrypoint == "strategy_registry.register"


def test_workflow_promotion_is_allowed_only_via_workflow():
    decision = can_agent_do(AgentAction.PROMOTE_CANDIDATE, "candidate:abc")
    assert decision.allowed is True
    assert decision.required_entrypoint == "workflow.promote"


def test_scratch_formal_evidence_is_blocked():
    decision = can_agent_do(AgentAction.USE_FORMAL_EVIDENCE, "scratch/foo.json")
    assert decision.allowed is False


def test_run_daily_is_allowed_through_entrypoint():
    decision = can_agent_do(AgentAction.RUN_DAILY, "production_signal")
    assert decision.allowed is True
    assert decision.required_entrypoint == "run_daily.py"


if __name__ == "__main__":
    test_registry_direct_write_is_blocked()
    test_workflow_promotion_is_allowed_only_via_workflow()
    test_scratch_formal_evidence_is_blocked()
    test_run_daily_is_allowed_through_entrypoint()
    print("agent action policy tests passed")
