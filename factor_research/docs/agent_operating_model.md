# Agent Operating Model

This system is designed so agents act as constrained research operators.

## Layers

- Agent: understands the user request, selects a skill, calls tools, summarizes evidence.
- Skill: maps a task type to required steps, tools, checks, and forbidden actions.
- Tool: deterministic service/action/API entrypoint.
- Data: canonical facts and artifacts with explicit read/write boundaries.
- Strategy: lifecycle state in factory, workflow, registry, portfolio, and production.
- Governance: holdout, trial ledger, 9-Gate, registry evidence, module status, and action policy.

## Principle

Agents may orchestrate and explain. Deterministic code decides validity.

## Default Read Entrypoints

- `services.read.module_inventory`
- `services.read.artifact_inventory`
- `services.read.action_policy`
- `services.read.strategy_lifecycle`
- existing `services.read.*` views

## Default Action Entrypoints

- `workflow.promote`
- `workflow.nine_gate_runner`
- `services.actions.*`
- `scripts/data/*`
- `scripts/ops/*`
- `run_daily.py`

## Forbidden Shortcuts

- direct registry writes
- direct data-lake writes
- promotion without workflow
- formal evidence from scratch/results/logs
- deployment changes without human approval
