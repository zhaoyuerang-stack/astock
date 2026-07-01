"""Agent action policy.

This module answers whether an agent may perform an action and which canonical
entrypoint must be used.
"""
from __future__ import annotations

from contracts.agent_control import ActionDecision, AgentAction


def _target_starts(target: str, prefixes: tuple[str, ...]) -> bool:
    clean = target.lstrip("./")
    return clean.startswith(prefixes)


def can_agent_do(
    action: AgentAction | str,
    target: str,
    context: dict | None = None,
) -> ActionDecision:
    action = AgentAction(action)
    context = context or {}

    if action == AgentAction.WRITE_REGISTRY:
        return ActionDecision(
            allowed=False,
            action=action,
            target=target,
            reason="Direct registry writes are forbidden.",
            required_entrypoint="strategy_registry.register",
        )

    if action == AgentAction.WRITE_DATA_LAKE:
        return ActionDecision(
            allowed=False,
            action=action,
            target=target,
            reason="Data lake writes must use controlled lake or scripts/data writers.",
            required_entrypoint="lake/ or scripts/data/",
        )

    if action == AgentAction.PROMOTE_CANDIDATE:
        return ActionDecision(
            allowed=True,
            action=action,
            target=target,
            reason="Candidate promotion is allowed only through canonical workflow.",
            required_entrypoint="workflow.promote",
        )

    if action == AgentAction.RUN_VALIDATION:
        return ActionDecision(
            allowed=True,
            action=action,
            target=target,
            reason="Validation is allowed through canonical factory/workflow runners.",
            required_entrypoint="factory.lines or workflow.nine_gate_runner",
        )

    if action == AgentAction.RUN_DAILY:
        return ActionDecision(
            allowed=True,
            action=action,
            target=target,
            reason="Daily signal generation is allowed through production entrypoint.",
            required_entrypoint="run_daily.py",
        )

    if action == AgentAction.UPDATE_DEPLOYMENT:
        return ActionDecision(
            allowed=False,
            action=action,
            target=target,
            reason="Deployment changes require explicit human approval and registry consistency.",
            required_entrypoint="runtime.deployment with human approval",
        )

    if action == AgentAction.USE_FORMAL_EVIDENCE:
        if _target_starts(target, ("scratch/", "results/", "logs/")):
            return ActionDecision(
                allowed=False,
                action=action,
                target=target,
                reason="Scratch, results, and logs are not formal evidence sources.",
                required_entrypoint="workflow/registry/reports/research_ledger",
            )
        return ActionDecision(
            allowed=True,
            action=action,
            target=target,
            reason="Target is not a known forbidden evidence path.",
            required_entrypoint=None,
        )

    if action == AgentAction.ARCHIVE_MODULE:
        return ActionDecision(
            allowed=False,
            action=action,
            target=target,
            reason="Module archival requires inventory audit and explicit human approval.",
            required_entrypoint="module cleanup plan + approval",
        )

    if action == AgentAction.WRITE_ARTIFACT:
        return ActionDecision(
            allowed=False,
            action=action,
            target=target,
            reason="Generic artifact writes are blocked; use a domain-specific writer.",
            required_entrypoint="runtime.artifacts + approved writer",
        )

    return ActionDecision(
        allowed=True,
        action=action,
        target=target,
        reason="Read-only action allowed.",
        required_entrypoint=None,
    )
