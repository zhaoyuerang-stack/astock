# Agent Operating Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an agent-friendly operating layer over `factor_research` so agents can discover module status, read facts, choose allowed actions, execute deterministic workflows, and avoid unsafe writes.

**Architecture:** Add a thin, auditable control plane rather than giving agents free access to the repository. The control plane reads `MODULE_STATUS.md`, artifact boundaries, registry/workflow state, and action policies; it exposes structured read APIs and guarded action checks through `services/read` and `services/actions`.

**Tech Stack:** Python 3, dataclasses/Pydantic-compatible dict payloads, existing `services/read`, `services/actions`, `contracts/views.py`, `api/routers`, `tests/test_*.py`, and `scripts/ci`.

---

## Non-Negotiable Constraints

- Agent-facing tools must not decide whether alpha is valid. They may summarize deterministic evidence only.
- No direct writes to `strategy_versions.json`, `data_lake/`, `signals/`, `paper/`, or deployment manifests from agent code.
- All official promotion remains through `workflow/`.
- `scratch/`, `results/`, and ad hoc research artifacts must not become formal evidence sources.
- Production behavior, cost model, `shift(1)`, T+1 semantics, holdout boundary, and registry statuses must not change in this plan.
- Do not use `git add -A`, `git add .`, or `git commit -a`.
- Current worktree is dirty; every task must stage explicit paths only.

## Target Control Plane

```text
Agent
  -> Skill playbook
  -> services/read/* for facts
  -> services/actions/* for controlled actions
  -> policy checks before any write/promotion/deployment action
  -> workflow/core/governance deterministic validators
```

## File Map

- Create: `factor_research/contracts/agent_control.py`
  - Small dataclasses/enums for module status, artifact policy, action policy, and agent task payloads.
- Create: `factor_research/services/read/module_inventory.py`
  - Parse every top-level `MODULE_STATUS.md`.
- Create: `factor_research/tests/test_module_inventory.py`
  - Guard all top-level dirs have parseable status files.
- Create: `factor_research/docs/agent_operating_model.md`
  - Human/agent design guide.
- Create: `factor_research/services/read/artifact_inventory.py`
  - Structured map for `data_lake`, `reports`, `signals`, `paper`, `scratch`, `results`, `logs`.
- Create: `factor_research/tests/test_artifact_inventory.py`
  - Guard artifact read/write policy.
- Create: `factor_research/services/read/action_policy.py`
  - `can_agent_do(action, target, context=None)`.
- Create: `factor_research/tests/test_agent_action_policy.py`
  - Guard unsafe actions are blocked.
- Create: `factor_research/services/read/strategy_lifecycle.py`
  - Agent-readable strategy family/version lifecycle view.
- Create: `factor_research/tests/test_strategy_lifecycle_view.py`
  - Guard registry lifecycle view handles known shapes and missing entries.
- Create: `factor_research/docs/agent_skills/*.md`
  - Skill playbooks for common tasks.
- Create: `factor_research/services/actions/agent_tasks.py`
  - Safe orchestration wrappers for allowed agent tasks.
- Create: `factor_research/tests/test_agent_tasks.py`
  - Guard orchestration never bypasses policy.
- Modify: `factor_research/api/routers/agent.py` or create `factor_research/api/routers/agent_control.py`
  - Expose read-only agent control-plane endpoints if API wiring is desired.
- Modify: `factor_research/api/main.py`
  - Include router only after tests pass.
- Create: `factor_research/scripts/ci/check_module_status.py`
  - CI guard for `MODULE_STATUS.md`.
- Modify: `factor_research/scripts/test_all.sh`
  - Add control-plane guards.

---

### Task 1: Define Agent Control Contracts

**Files:**
- Create: `factor_research/contracts/agent_control.py`
- Create: `factor_research/tests/test_agent_control_contracts.py`

- [ ] **Step 1: Write the failing contract test**

Create `factor_research/tests/test_agent_control_contracts.py`:

```python
"""Agent control contract tests.

Run:
    cd factor_research && python3 tests/test_agent_control_contracts.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.agent_control import ActionDecision, AgentAction, ArtifactPolicy, ModuleStatus


def test_module_status_values_include_expected_taxonomy():
    expected = {
        "ONLINE",
        "ONLINE_CRITICAL",
        "ONLINE_GOVERNANCE",
        "RESEARCH_SUPPORT",
        "STAGING",
        "ARCHIVE_OR_REHOME",
        "ARTIFACTS_ONLY",
        "TEMP_ONLY",
    }
    assert expected.issubset({item.value for item in ModuleStatus})


def test_action_decision_serializes_to_plain_dict():
    decision = ActionDecision(
        allowed=False,
        action=AgentAction.WRITE_REGISTRY,
        target="strategy_versions.json",
        reason="registry writes must go through strategy_registry.register",
        required_entrypoint="strategy_registry.register",
    )
    payload = decision.to_dict()
    assert payload["allowed"] is False
    assert payload["action"] == "write_registry"
    assert payload["target"] == "strategy_versions.json"
    assert payload["required_entrypoint"] == "strategy_registry.register"


def test_artifact_policy_serializes_boundaries():
    policy = ArtifactPolicy(
        name="scratch",
        path="scratch/",
        read_allowed=True,
        write_allowed=True,
        formal_evidence_allowed=False,
        writer="temporary only",
    )
    payload = policy.to_dict()
    assert payload["formal_evidence_allowed"] is False
    assert payload["writer"] == "temporary only"


if __name__ == "__main__":
    test_module_status_values_include_expected_taxonomy()
    test_action_decision_serializes_to_plain_dict()
    test_artifact_policy_serializes_boundaries()
    print("agent control contract tests passed")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_agent_control_contracts.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'contracts.agent_control'`.

- [ ] **Step 3: Implement contracts**

Create `factor_research/contracts/agent_control.py`:

```python
"""Agent control-plane contracts.

These are plain dataclasses so CLI, tests, services, and API routers can share
structured payloads without introducing a new framework dependency.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any


class ModuleStatus(str, Enum):
    ONLINE = "ONLINE"
    ONLINE_CRITICAL = "ONLINE_CRITICAL"
    ONLINE_CRITICAL_ARTIFACTS = "ONLINE_CRITICAL_ARTIFACTS"
    ONLINE_SUPPORT = "ONLINE_SUPPORT"
    ONLINE_RESEARCH = "ONLINE_RESEARCH"
    ONLINE_GOVERNANCE = "ONLINE_GOVERNANCE"
    ONLINE_CONFIG = "ONLINE_CONFIG"
    ONLINE_DOCS = "ONLINE_DOCS"
    ONLINE_ARTIFACTS = "ONLINE_ARTIFACTS"
    ONLINE_GUARDRAILS = "ONLINE_GUARDRAILS"
    CLI_ENTRYPOINTS = "CLI_ENTRYPOINTS"
    MIXED_ENTRYPOINTS = "MIXED_ENTRYPOINTS"
    RESEARCH_ENTRYPOINTS = "RESEARCH_ENTRYPOINTS"
    RESEARCH_SUPPORT = "RESEARCH_SUPPORT"
    RESEARCH_DIAGNOSTIC = "RESEARCH_DIAGNOSTIC"
    STAGING = "STAGING"
    STAGING_GOVERNANCE = "STAGING_GOVERNANCE"
    ARCHIVE_OR_REHOME = "ARCHIVE_OR_REHOME"
    ARTIFACTS_ONLY = "ARTIFACTS_ONLY"
    TEMP_ONLY = "TEMP_ONLY"


class AgentAction(str, Enum):
    READ = "read"
    WRITE_ARTIFACT = "write_artifact"
    WRITE_REGISTRY = "write_registry"
    WRITE_DATA_LAKE = "write_data_lake"
    PROMOTE_CANDIDATE = "promote_candidate"
    RUN_VALIDATION = "run_validation"
    RUN_DAILY = "run_daily"
    UPDATE_DEPLOYMENT = "update_deployment"
    USE_FORMAL_EVIDENCE = "use_formal_evidence"
    ARCHIVE_MODULE = "archive_module"


@dataclass(frozen=True)
class ModuleInventoryItem:
    module: str
    path: str
    status: str
    role: str
    keep_reason: str
    boundary: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ArtifactPolicy:
    name: str
    path: str
    read_allowed: bool
    write_allowed: bool
    formal_evidence_allowed: bool
    writer: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ActionDecision:
    allowed: bool
    action: AgentAction
    target: str
    reason: str
    required_entrypoint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["action"] = self.action.value
        return payload
```

- [ ] **Step 4: Run the test**

Run:

```bash
cd factor_research && python3 tests/test_agent_control_contracts.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add factor_research/contracts/agent_control.py factor_research/tests/test_agent_control_contracts.py
git diff --cached --stat
git diff --cached
git commit -m "feat(agent): add control-plane contracts"
```

---

### Task 2: Build Module Inventory Reader

**Files:**
- Create: `factor_research/services/read/module_inventory.py`
- Create: `factor_research/tests/test_module_inventory.py`

- [ ] **Step 1: Write the failing inventory test**

Create `factor_research/tests/test_module_inventory.py`:

```python
"""Module inventory reader tests.

Run:
    cd factor_research && python3 tests/test_module_inventory.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.read.module_inventory import get_module_inventory, get_module_status


def test_all_top_level_directories_have_module_status():
    inventory = get_module_inventory()
    modules = {item.module for item in inventory}
    top_dirs = {
        p.name for p in ROOT.iterdir()
        if p.is_dir() and not p.name.startswith(".") and p.name != "__pycache__"
    }
    assert top_dirs == modules


def test_core_and_execution_statuses_are_parsed():
    core = get_module_status("core")
    execution = get_module_status("execution")
    assert core.status == "ONLINE_CRITICAL"
    assert "BacktestEngine" in core.role
    assert execution.status == "ARCHIVE_OR_REHOME"


def test_inventory_items_are_plain_dict_serializable():
    payload = [item.to_dict() for item in get_module_inventory()]
    first = payload[0]
    assert set(first) == {"module", "path", "status", "role", "keep_reason", "boundary"}


if __name__ == "__main__":
    test_all_top_level_directories_have_module_status()
    test_core_and_execution_statuses_are_parsed()
    test_inventory_items_are_plain_dict_serializable()
    print("module inventory tests passed")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_module_inventory.py
```

Expected: FAIL with missing `services.read.module_inventory`.

- [ ] **Step 3: Implement module inventory parser**

Create `factor_research/services/read/module_inventory.py`:

```python
"""Read top-level MODULE_STATUS.md files as structured agent inventory."""
from __future__ import annotations

from pathlib import Path

from contracts.agent_control import ModuleInventoryItem


ROOT = Path(__file__).resolve().parents[2]


def _section_value(lines: list[str], prefix: str) -> str:
    for line in lines:
        if line.startswith(prefix):
            return line.split(":", 1)[1].strip()
    return ""


def _boundary_lines(lines: list[str]) -> list[str]:
    boundary = []
    in_boundary = False
    for line in lines:
        stripped = line.strip()
        if stripped == "Boundary:":
            in_boundary = True
            continue
        if in_boundary:
            if stripped.startswith("- "):
                boundary.append(stripped[2:])
            elif stripped and not stripped.startswith("- "):
                break
    return boundary


def _read_status_file(module_dir: Path) -> ModuleInventoryItem:
    status_path = module_dir / "MODULE_STATUS.md"
    lines = status_path.read_text(encoding="utf-8").splitlines()
    status = _section_value(lines, "Status")
    role = _section_value(lines, "Role")
    keep_reason = _section_value(lines, "Keep because") or _section_value(lines, "Keep for now because")
    if not keep_reason:
        keep_reason = _section_value(lines, "Current issue") or _section_value(lines, "Decision")
    return ModuleInventoryItem(
        module=module_dir.name,
        path=str(module_dir.relative_to(ROOT)),
        status=status,
        role=role,
        keep_reason=keep_reason,
        boundary=_boundary_lines(lines),
    )


def get_module_inventory() -> list[ModuleInventoryItem]:
    items = []
    for module_dir in sorted(ROOT.iterdir(), key=lambda p: p.name):
        if not module_dir.is_dir() or module_dir.name.startswith(".") or module_dir.name == "__pycache__":
            continue
        status_file = module_dir / "MODULE_STATUS.md"
        if status_file.exists():
            items.append(_read_status_file(module_dir))
    return items


def get_module_status(module: str) -> ModuleInventoryItem:
    for item in get_module_inventory():
        if item.module == module:
            return item
    raise KeyError(f"Unknown module or missing MODULE_STATUS.md: {module}")
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd factor_research && python3 tests/test_module_inventory.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add factor_research/services/read/module_inventory.py factor_research/tests/test_module_inventory.py
git diff --cached --stat
git diff --cached
git commit -m "feat(agent): expose module inventory"
```

---

### Task 3: Add Artifact Inventory and Boundaries

**Files:**
- Create: `factor_research/services/read/artifact_inventory.py`
- Create: `factor_research/tests/test_artifact_inventory.py`

- [ ] **Step 1: Write artifact policy test**

Create `factor_research/tests/test_artifact_inventory.py`:

```python
"""Artifact inventory tests.

Run:
    cd factor_research && python3 tests/test_artifact_inventory.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.read.artifact_inventory import get_artifact_inventory, get_artifact_policy


def test_canonical_artifacts_are_declared():
    policies = {p.name: p for p in get_artifact_inventory()}
    for name in ["data_lake", "reports", "signals", "paper", "scratch", "results", "logs"]:
        assert name in policies


def test_scratch_and_results_are_not_formal_evidence():
    assert get_artifact_policy("scratch").formal_evidence_allowed is False
    assert get_artifact_policy("results").formal_evidence_allowed is False


def test_data_lake_write_is_restricted():
    policy = get_artifact_policy("data_lake")
    assert policy.read_allowed is True
    assert policy.write_allowed is False
    assert "scripts/data" in policy.writer


if __name__ == "__main__":
    test_canonical_artifacts_are_declared()
    test_scratch_and_results_are_not_formal_evidence()
    test_data_lake_write_is_restricted()
    print("artifact inventory tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_artifact_inventory.py
```

Expected: FAIL because `services.read.artifact_inventory` does not exist.

- [ ] **Step 3: Implement artifact inventory**

Create `factor_research/services/read/artifact_inventory.py`:

```python
"""Agent-readable artifact boundary inventory."""
from __future__ import annotations

from contracts.agent_control import ArtifactPolicy


_POLICIES = {
    "data_lake": ArtifactPolicy(
        name="data_lake",
        path="data_lake/",
        read_allowed=True,
        write_allowed=False,
        formal_evidence_allowed=True,
        writer="lake/ or scripts/data/ controlled writers only",
    ),
    "reports": ArtifactPolicy(
        name="reports",
        path="reports/",
        read_allowed=True,
        write_allowed=True,
        formal_evidence_allowed=True,
        writer="report-generation tools and approved workflows",
    ),
    "signals": ArtifactPolicy(
        name="signals",
        path="signals/",
        read_allowed=True,
        write_allowed=False,
        formal_evidence_allowed=True,
        writer="run_daily.py only",
    ),
    "paper": ArtifactPolicy(
        name="paper",
        path="paper/",
        read_allowed=True,
        write_allowed=False,
        formal_evidence_allowed=True,
        writer="portfolio.paper_engine or approved ops scripts",
    ),
    "scratch": ArtifactPolicy(
        name="scratch",
        path="scratch/",
        read_allowed=True,
        write_allowed=True,
        formal_evidence_allowed=False,
        writer="temporary experiments only",
    ),
    "results": ArtifactPolicy(
        name="results",
        path="results/",
        read_allowed=True,
        write_allowed=False,
        formal_evidence_allowed=False,
        writer="deprecated; rehome to reports or archive",
    ),
    "logs": ArtifactPolicy(
        name="logs",
        path="logs/",
        read_allowed=True,
        write_allowed=False,
        formal_evidence_allowed=False,
        writer="runtime logging only",
    ),
}


def get_artifact_inventory() -> list[ArtifactPolicy]:
    return list(_POLICIES.values())


def get_artifact_policy(name: str) -> ArtifactPolicy:
    try:
        return _POLICIES[name]
    except KeyError as exc:
        raise KeyError(f"Unknown artifact policy: {name}") from exc
```

- [ ] **Step 4: Run test**

Run:

```bash
cd factor_research && python3 tests/test_artifact_inventory.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add factor_research/services/read/artifact_inventory.py factor_research/tests/test_artifact_inventory.py
git diff --cached --stat
git diff --cached
git commit -m "feat(agent): expose artifact boundaries"
```

---

### Task 4: Add Agent Action Policy

**Files:**
- Create: `factor_research/services/read/action_policy.py`
- Create: `factor_research/tests/test_agent_action_policy.py`

- [ ] **Step 1: Write action policy tests**

Create `factor_research/tests/test_agent_action_policy.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_agent_action_policy.py
```

Expected: FAIL because `services.read.action_policy` does not exist.

- [ ] **Step 3: Implement policy function**

Create `factor_research/services/read/action_policy.py`:

```python
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
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd factor_research && python3 tests/test_agent_action_policy.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add factor_research/services/read/action_policy.py factor_research/tests/test_agent_action_policy.py
git diff --cached --stat
git diff --cached
git commit -m "feat(agent): add action policy checks"
```

---

### Task 5: Add Strategy Lifecycle Read Model

**Files:**
- Create: `factor_research/services/read/strategy_lifecycle.py`
- Create: `factor_research/tests/test_strategy_lifecycle_view.py`

- [ ] **Step 1: Write lifecycle tests**

Create `factor_research/tests/test_strategy_lifecycle_view.py`:

```python
"""Strategy lifecycle read-model tests.

Run:
    cd factor_research && python3 tests/test_strategy_lifecycle_view.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.read.strategy_lifecycle import get_strategy_lifecycle, list_strategy_lifecycles


def test_list_strategy_lifecycles_returns_plain_dicts():
    rows = list_strategy_lifecycles()
    assert isinstance(rows, list)
    if rows:
        row = rows[0]
        assert {"family", "version", "status", "allowed_agent_actions", "blocked_agent_actions"}.issubset(row)


def test_missing_strategy_returns_blocked_view():
    row = get_strategy_lifecycle("missing-family", "v0")
    assert row["status"] == "missing"
    assert "promote" not in row["allowed_agent_actions"]
    assert "direct_registry_write" in row["blocked_agent_actions"]


if __name__ == "__main__":
    test_list_strategy_lifecycles_returns_plain_dicts()
    test_missing_strategy_returns_blocked_view()
    print("strategy lifecycle view tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_strategy_lifecycle_view.py
```

Expected: FAIL because `services.read.strategy_lifecycle` does not exist.

- [ ] **Step 3: Implement lifecycle read model**

Create `factor_research/services/read/strategy_lifecycle.py`:

```python
"""Agent-readable strategy lifecycle view."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "strategy_versions.json"


def _load_registry() -> dict[str, Any]:
    if not REGISTRY.exists():
        return {"families": []}
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _actions_for_status(status: str) -> tuple[list[str], list[str]]:
    blocked = ["direct_registry_write", "bypass_workflow", "use_scratch_as_evidence"]
    if status in {"候选", "candidate", "CANDIDATE"}:
        return ["run_validation", "request_review"], blocked
    if status in {"参考", "REGISTERED_REFERENCE", "reference"}:
        return ["monitor", "rerun_gates"], blocked + ["deploy_without_gate"]
    if status in {"在册", "ACTIVE", "active"}:
        return ["monitor", "run_daily_if_deployed", "decay_check"], blocked
    if status in {"退役", "RETIRED", "retired"}:
        return ["explain_retirement"], blocked + ["reactivate_without_new_workflow"]
    return ["inspect"], blocked


def list_strategy_lifecycles() -> list[dict[str, Any]]:
    data = _load_registry()
    rows: list[dict[str, Any]] = []
    for family in data.get("families", []):
        family_id = family.get("id", "")
        for version in family.get("versions", []):
            version_id = version.get("version", "")
            status = str(version.get("status", "unknown"))
            allowed, blocked = _actions_for_status(status)
            rows.append({
                "family": family_id,
                "version": version_id,
                "status": status,
                "family_status": family.get("status", ""),
                "has_metrics": bool(version.get("metrics")),
                "has_nine_gate": bool(version.get("nine_gate")),
                "allowed_agent_actions": allowed,
                "blocked_agent_actions": blocked,
            })
    return rows


def get_strategy_lifecycle(family: str, version: str) -> dict[str, Any]:
    for row in list_strategy_lifecycles():
        if row["family"] == family and row["version"] == version:
            return row
    return {
        "family": family,
        "version": version,
        "status": "missing",
        "family_status": "missing",
        "has_metrics": False,
        "has_nine_gate": False,
        "allowed_agent_actions": ["inspect"],
        "blocked_agent_actions": ["direct_registry_write", "promote", "deploy", "use_scratch_as_evidence"],
    }
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd factor_research && python3 tests/test_strategy_lifecycle_view.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add factor_research/services/read/strategy_lifecycle.py factor_research/tests/test_strategy_lifecycle_view.py
git diff --cached --stat
git diff --cached
git commit -m "feat(agent): expose strategy lifecycle view"
```

---

### Task 6: Write Agent Skill Playbooks

**Files:**
- Create: `factor_research/docs/agent_operating_model.md`
- Create: `factor_research/docs/agent_skills/data_health.md`
- Create: `factor_research/docs/agent_skills/factor_audit.md`
- Create: `factor_research/docs/agent_skills/candidate_promote.md`
- Create: `factor_research/docs/agent_skills/production_readiness.md`
- Create: `factor_research/docs/agent_skills/module_cleanup.md`
- Create: `factor_research/tests/test_agent_skill_docs.py`

- [ ] **Step 1: Write docs guard test**

Create `factor_research/tests/test_agent_skill_docs.py`:

```python
"""Agent skill documentation guard.

Run:
    cd factor_research && python3 tests/test_agent_skill_docs.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_agent_operating_model_exists():
    doc = ROOT / "docs" / "agent_operating_model.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    for term in ["Agent", "Skill", "Tool", "Data", "Strategy", "Governance"]:
        assert term in text


def test_skill_docs_have_required_sections():
    skill_dir = ROOT / "docs" / "agent_skills"
    expected = [
        "data_health.md",
        "factor_audit.md",
        "candidate_promote.md",
        "production_readiness.md",
        "module_cleanup.md",
    ]
    for name in expected:
        path = skill_dir / name
        assert path.exists(), f"missing {path}"
        text = path.read_text(encoding="utf-8")
        for section in ["## Inputs", "## Allowed Tools", "## Forbidden", "## Success Criteria"]:
            assert section in text, f"{name} missing {section}"


if __name__ == "__main__":
    test_agent_operating_model_exists()
    test_skill_docs_have_required_sections()
    print("agent skill docs tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_agent_skill_docs.py
```

Expected: FAIL because docs are missing.

- [ ] **Step 3: Create operating model doc**

Create `factor_research/docs/agent_operating_model.md`:

```markdown
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
```

- [ ] **Step 4: Create skill docs**

Create `factor_research/docs/agent_skills/data_health.md`:

```markdown
# data-health

## Inputs

- Optional date or expected freshness window.

## Allowed Tools

- `services.read.state`
- `services.read.artifact_inventory`
- `lake.validator`
- `validate_final.py`

## Forbidden

- Do not silently repair data.
- Do not write `data_lake/` except through `scripts/data`.

## Success Criteria

- Report latest data date, quality status, stale status, and blocking issues.
```

Create `factor_research/docs/agent_skills/factor_audit.md`:

```markdown
# factor-audit

## Inputs

- Factor name, formula, panel path, or candidate id.

## Allowed Tools

- `factory.lines.line2_validation`
- `factor_store.scoring`
- `core.analysis`
- `services.actions.run_backtest`

## Forbidden

- Do not declare alpha valid from language alone.
- Do not use scratch output as final evidence.

## Success Criteria

- Produce IC, ICIR, monotonicity, decay, cost sensitivity, and next recommended gate.
```

Create `factor_research/docs/agent_skills/candidate_promote.md`:

```markdown
# candidate-promote

## Inputs

- Hypothesis id, AutoResearch fingerprint, or approved candidate id.

## Allowed Tools

- `services.read.action_policy`
- `workflow.research_stages`
- `workflow.promote`
- `workflow.nine_gate_runner`

## Forbidden

- Do not write registry files directly.
- Do not skip phase1 synthetic audit.
- Do not bypass human review when required.

## Success Criteria

- Candidate is promoted, rejected, blocked, or left in review with exact mechanical evidence.
```

Create `factor_research/docs/agent_skills/production_readiness.md`:

```markdown
# production-readiness

## Inputs

- Optional deployment id or date.

## Allowed Tools

- `runtime.production_readiness`
- `runtime.deployment`
- `services.read.trade_readiness`
- `run_daily.py --no-update`

## Forbidden

- Do not activate deployment.
- Do not edit `deployments/production.json` without human approval.

## Success Criteria

- Report allowed/blocked status, blockers, latest signal path or draft path, and required human action.
```

Create `factor_research/docs/agent_skills/module_cleanup.md`:

```markdown
# module-cleanup

## Inputs

- Module name or status class.

## Allowed Tools

- `services.read.module_inventory`
- `services.read.action_policy`
- `scripts/ci/check_layer_deps.py`

## Forbidden

- Do not delete or move modules without explicit human approval.
- Do not archive modules with active production, workflow, or service callers.

## Success Criteria

- Classify as keep, rehome, archive, or investigate, with caller evidence and required tests.
```

- [ ] **Step 5: Run docs test**

Run:

```bash
cd factor_research && python3 tests/test_agent_skill_docs.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add factor_research/docs/agent_operating_model.md factor_research/docs/agent_skills/data_health.md factor_research/docs/agent_skills/factor_audit.md factor_research/docs/agent_skills/candidate_promote.md factor_research/docs/agent_skills/production_readiness.md factor_research/docs/agent_skills/module_cleanup.md factor_research/tests/test_agent_skill_docs.py
git diff --cached --stat
git diff --cached
git commit -m "docs(agent): add operating model and skill playbooks"
```

---

### Task 7: Add Safe Agent Task Orchestration Wrappers

**Files:**
- Create: `factor_research/services/actions/agent_tasks.py`
- Create: `factor_research/tests/test_agent_tasks.py`

- [ ] **Step 1: Write orchestration tests**

Create `factor_research/tests/test_agent_tasks.py`:

```python
"""Agent task action wrapper tests.

Run:
    cd factor_research && python3 tests/test_agent_tasks.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.actions.agent_tasks import describe_agent_task, guard_agent_action


def test_guard_blocks_direct_registry_write():
    decision = guard_agent_action("write_registry", "strategy_versions.json")
    assert decision["allowed"] is False
    assert decision["required_entrypoint"] == "strategy_registry.register"


def test_describe_module_cleanup_task_uses_inventory_and_policy():
    payload = describe_agent_task("module_cleanup", target="execution")
    assert payload["task"] == "module_cleanup"
    assert payload["target"] == "execution"
    assert payload["module"]["status"] == "ARCHIVE_OR_REHOME"
    assert payload["archive_policy"]["allowed"] is False


if __name__ == "__main__":
    test_guard_blocks_direct_registry_write()
    test_describe_module_cleanup_task_uses_inventory_and_policy()
    print("agent task tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_agent_tasks.py
```

Expected: FAIL because `services.actions.agent_tasks` does not exist.

- [ ] **Step 3: Implement wrappers**

Create `factor_research/services/actions/agent_tasks.py`:

```python
"""Safe agent task wrappers.

These functions do not execute risky mutations. They assemble the facts and
policy decisions an agent needs before selecting a deterministic workflow.
"""
from __future__ import annotations

from contracts.agent_control import AgentAction
from services.read.action_policy import can_agent_do
from services.read.module_inventory import get_module_status


def guard_agent_action(action: str, target: str, context: dict | None = None) -> dict:
    return can_agent_do(AgentAction(action), target, context).to_dict()


def describe_agent_task(task: str, *, target: str) -> dict:
    if task == "module_cleanup":
        module = get_module_status(target).to_dict()
        archive_policy = can_agent_do(AgentAction.ARCHIVE_MODULE, target).to_dict()
        return {
            "task": task,
            "target": target,
            "module": module,
            "archive_policy": archive_policy,
            "next_step": "collect callers and request human approval before moving or deleting files",
        }

    return {
        "task": task,
        "target": target,
        "policy": can_agent_do(AgentAction.READ, target).to_dict(),
        "next_step": "select a specific skill playbook",
    }
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd factor_research && python3 tests/test_agent_tasks.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add factor_research/services/actions/agent_tasks.py factor_research/tests/test_agent_tasks.py
git diff --cached --stat
git diff --cached
git commit -m "feat(agent): add safe task wrappers"
```

---

### Task 8: Expose Read-Only Agent Control API

**Files:**
- Create: `factor_research/api/routers/agent_control.py`
- Modify: `factor_research/api/main.py`
- Create: `factor_research/tests/test_agent_control_api_contract.py`

- [ ] **Step 1: Write API contract test**

Create `factor_research/tests/test_agent_control_api_contract.py`:

```python
"""Agent control API contract smoke tests.

Run:
    cd factor_research && python3 tests/test_agent_control_api_contract.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.routers.agent_control import module_inventory, artifact_inventory, action_policy


def test_module_inventory_endpoint_shape():
    payload = module_inventory()
    assert isinstance(payload, list)
    assert payload
    assert {"module", "status", "role"}.issubset(payload[0])


def test_artifact_inventory_endpoint_shape():
    payload = artifact_inventory()
    names = {row["name"] for row in payload}
    assert "data_lake" in names
    assert "scratch" in names


def test_action_policy_endpoint_shape():
    payload = action_policy(action="write_registry", target="strategy_versions.json")
    assert payload["allowed"] is False
    assert payload["required_entrypoint"] == "strategy_registry.register"


if __name__ == "__main__":
    test_module_inventory_endpoint_shape()
    test_artifact_inventory_endpoint_shape()
    test_action_policy_endpoint_shape()
    print("agent control API contract tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_agent_control_api_contract.py
```

Expected: FAIL because router is missing.

- [ ] **Step 3: Create router**

Create `factor_research/api/routers/agent_control.py`:

```python
"""Read-only agent control-plane endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from services.read.action_policy import can_agent_do
from services.read.artifact_inventory import get_artifact_inventory
from services.read.module_inventory import get_module_inventory
from services.read.strategy_lifecycle import get_strategy_lifecycle, list_strategy_lifecycles

router = APIRouter(prefix="/agent-control", tags=["agent-control"])


@router.get("/modules")
def module_inventory():
    return [item.to_dict() for item in get_module_inventory()]


@router.get("/artifacts")
def artifact_inventory():
    return [item.to_dict() for item in get_artifact_inventory()]


@router.get("/policy")
def action_policy(action: str, target: str):
    return can_agent_do(action, target).to_dict()


@router.get("/strategies")
def strategy_lifecycles():
    return list_strategy_lifecycles()


@router.get("/strategies/{family}/{version}")
def strategy_lifecycle(family: str, version: str):
    return get_strategy_lifecycle(family, version)
```

- [ ] **Step 4: Wire router into API main**

In `factor_research/api/main.py`, add `agent_control` to the router import list and include it with the other routers. Use the existing local pattern in that file.

Expected shape:

```python
from api.routers import agent_control

app.include_router(agent_control.router)
```

- [ ] **Step 5: Run API contract test**

Run:

```bash
cd factor_research && python3 tests/test_agent_control_api_contract.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add factor_research/api/routers/agent_control.py factor_research/api/main.py factor_research/tests/test_agent_control_api_contract.py
git diff --cached --stat
git diff --cached
git commit -m "feat(api): expose agent control-plane views"
```

---

### Task 9: Add CI Guard for Module Status

**Files:**
- Create: `factor_research/scripts/ci/check_module_status.py`
- Create: `factor_research/tests/test_module_status_guard.py`
- Modify: `factor_research/scripts/test_all.sh`

- [ ] **Step 1: Write guard test**

Create `factor_research/tests/test_module_status_guard.py`:

```python
"""Module status CI guard tests.

Run:
    cd factor_research && python3 tests/test_module_status_guard.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_module_status_guard_passes_current_tree():
    proc = subprocess.run(
        [sys.executable, "scripts/ci/check_module_status.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


if __name__ == "__main__":
    test_module_status_guard_passes_current_tree()
    print("module status guard tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_module_status_guard.py
```

Expected: FAIL because guard script is missing.

- [ ] **Step 3: Implement guard**

Create `factor_research/scripts/ci/check_module_status.py`:

```python
"""Ensure every top-level module has parseable MODULE_STATUS.md."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REQUIRED = ["# MODULE_STATUS", "Status:", "Role:"]


def main() -> int:
    failures = []
    for module_dir in sorted(ROOT.iterdir(), key=lambda p: p.name):
        if not module_dir.is_dir() or module_dir.name.startswith(".") or module_dir.name == "__pycache__":
            continue
        path = module_dir / "MODULE_STATUS.md"
        if not path.exists():
            failures.append(f"{module_dir.name}: missing MODULE_STATUS.md")
            continue
        text = path.read_text(encoding="utf-8")
        for marker in REQUIRED:
            if marker not in text:
                failures.append(f"{module_dir.name}: missing marker {marker}")

    if failures:
        print("MODULE_STATUS guard failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("MODULE_STATUS guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run guard test**

Run:

```bash
cd factor_research && python3 tests/test_module_status_guard.py && python3 scripts/ci/check_module_status.py
```

Expected: PASS.

- [ ] **Step 5: Add to test_all**

In `factor_research/scripts/test_all.sh`, add near the other guard checks:

```bash
echo "== MODULE_STATUS guard =="
python3 scripts/ci/check_module_status.py
```

- [ ] **Step 6: Run targeted guard stack**

Run:

```bash
cd factor_research && python3 scripts/ci/check_module_status.py && python3 scripts/ci/check_layer_deps.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add factor_research/scripts/ci/check_module_status.py factor_research/tests/test_module_status_guard.py factor_research/scripts/test_all.sh
git diff --cached --stat
git diff --cached
git commit -m "test(agent): guard module status metadata"
```

---

### Task 10: Final Documentation and Verification

**Files:**
- Create: `factor_research/docs/agent_control_plane_report.md`

- [ ] **Step 1: Run targeted tests**

Run:

```bash
cd factor_research && \
python3 tests/test_agent_control_contracts.py && \
python3 tests/test_module_inventory.py && \
python3 tests/test_artifact_inventory.py && \
python3 tests/test_agent_action_policy.py && \
python3 tests/test_strategy_lifecycle_view.py && \
python3 tests/test_agent_skill_docs.py && \
python3 tests/test_agent_tasks.py && \
python3 tests/test_agent_control_api_contract.py && \
python3 tests/test_module_status_guard.py
```

Expected: PASS.

- [ ] **Step 2: Run architecture guards**

Run:

```bash
cd factor_research && python3 scripts/ci/check_module_status.py && python3 scripts/ci/check_layer_deps.py
```

Expected: PASS.

- [ ] **Step 3: Run full test suite if current worktree allows**

Run:

```bash
cd factor_research && bash scripts/test_all.sh
```

Expected: PASS. If unrelated dirty-worktree changes cause failures, record exact failing tests and prove the new targeted tests pass.

- [ ] **Step 4: Write report**

Create `factor_research/docs/agent_control_plane_report.md`:

```markdown
# Agent Control Plane Report

## What Changed

- Added structured contracts for module status, artifact policy, action policy, and agent decisions.
- Added module inventory reader from top-level `MODULE_STATUS.md`.
- Added artifact inventory boundaries for data lake, reports, signals, paper, scratch, results, and logs.
- Added action policy checks for registry writes, data-lake writes, promotion, formal evidence, deployment, and daily runs.
- Added strategy lifecycle read model.
- Added agent operating model and skill playbooks.
- Added safe task wrappers and read-only API views.
- Added CI guard for module status metadata.

## Safety Properties

- Agent code cannot treat scratch/results/logs as formal evidence.
- Agent code gets blocked from direct registry and data-lake writes.
- Candidate promotion points to workflow only.
- Deployment changes remain human-approved.
- Module archival remains human-approved.

## Verification

- `python3 tests/test_agent_control_contracts.py`
- `python3 tests/test_module_inventory.py`
- `python3 tests/test_artifact_inventory.py`
- `python3 tests/test_agent_action_policy.py`
- `python3 tests/test_strategy_lifecycle_view.py`
- `python3 tests/test_agent_skill_docs.py`
- `python3 tests/test_agent_tasks.py`
- `python3 tests/test_agent_control_api_contract.py`
- `python3 tests/test_module_status_guard.py`
- `python3 scripts/ci/check_module_status.py`
- `python3 scripts/ci/check_layer_deps.py`
- `bash scripts/test_all.sh`

## Deferred Work

- Build a Web panel for module inventory and allowed agent actions.
- Add richer strategy state-machine transitions.
- Add policy coverage for cost-model changes and holdout boundary changes.
- Add per-skill structured execution logs.
```

- [ ] **Step 5: Commit report**

```bash
git add factor_research/docs/agent_control_plane_report.md
git diff --cached --stat
git diff --cached
git commit -m "docs(agent): record control-plane implementation"
```

---

## Rollback Strategy

- Each task is independent and commit-sized.
- If API wiring fails, revert Task 8 only; read services can remain.
- If `test_all.sh` fails due to unrelated dirty worktree changes, keep targeted test evidence and do not claim full-suite success.
- Do not delete `MODULE_STATUS.md` files; they are useful even if later control-plane code is reverted.

## Definition of Done

- Every top-level `factor_research/*/MODULE_STATUS.md` is machine-checked.
- Agent-readable module inventory is available through `services.read.module_inventory`.
- Artifact boundaries are available through `services.read.artifact_inventory`.
- Unsafe direct writes are blocked by `services.read.action_policy`.
- Strategy lifecycle facts are queryable without hand-reading registry JSON.
- Skill playbooks exist for data health, factor audit, candidate promotion, production readiness, and module cleanup.
- Safe agent task wrappers exist and do not perform risky mutations.
- Optional read-only API endpoints expose modules, artifacts, policy, and strategy lifecycle.
- Targeted tests pass.
- Architecture guards pass.
