# Loop Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a thin, auditable Loop OS that closes the existing Data → Hypothesis → Experiment → Evaluation → Memory → Governance cycle without replacing the canonical research engine.

**Architecture:** Add a small `factor_research/loops/` orchestration layer that records append-only loop events, coordinates existing modules, and exposes deterministic status/decision artifacts. The layer must not judge alpha itself; it delegates alpha validity to `BacktestEngine`, 9-Gate, DSR, holdout, marginal/capacity checks, and registry gates.

**Tech Stack:** Python 3.13 on Apple Silicon macOS, stdlib dataclasses/json/pathlib/argparse, existing `factor_research` modules, pytest-style tests run through `python3 tests/...` and `bash scripts/test_all.sh`.

---

## Hard Rules For Claude Code

- Read `CLAUDE.md`, `STATUS.md`, `LOOP_ENGINEERING.md`, `WORKFLOW.md`, and this file before edits.
- Run `git status --short` before edits. Do not touch unrelated dirty files.
- Never use `git add -A`, `git add .`, or `git commit -a`.
- Do not modify alpha validity criteria, cost model, holdout boundary, DSR threshold, registry status semantics, or production deployment manifest as part of this plan.
- Do not let LLM output decide whether alpha is valid.
- Do not write directly to `strategy_versions.json`, `strategy_families.json`, or registry JSON files.
- Do not import `factory`, `workflow`, or `scripts.research` from production code.
- Do not add network-dependent tests.
- All new durable loop state must be append-only JSONL unless explicitly stated otherwise.

## Intended File Map

Create:

- `factor_research/loops/__init__.py` — public package exports.
- `factor_research/loops/types.py` — loop names, statuses, run/event/decision/artifact/report dataclasses.
- `factor_research/loops/store.py` — append-only JSONL event store and status reconstruction.
- `factor_research/loops/policy.py` — governance policy, budgets, approvals, and hard action gates.
- `factor_research/loops/context.py` — shared filesystem/config context.
- `factor_research/loops/data.py` — Data Loop adapter.
- `factor_research/loops/hypothesis.py` — Hypothesis Loop adapter.
- `factor_research/loops/experiment.py` — Experiment Loop adapter and artifact writer.
- `factor_research/loops/evaluation.py` — Evaluation Loop adapter and report writer.
- `factor_research/loops/memory.py` — Memory Loop adapter and structured feedback writer.
- `factor_research/loops/orchestrator.py` — six-loop state machine.
- `factor_research/apps/loop_cli.py` — CLI entry point for dry-run/status/daily MVP.
- `factor_research/services/read/loops.py` — read model for Web/API.
- `factor_research/api/routers/loops.py` — optional API route for loop status.
- `factor_research/scripts/ci/check_loop_contracts.py` — static guard for Loop OS boundaries.
- `factor_research/tests/test_loop_contracts.py`
- `factor_research/tests/test_loop_store.py`
- `factor_research/tests/test_loop_policy.py`
- `factor_research/tests/test_loop_adapters.py`
- `factor_research/tests/test_loop_orchestrator.py`
- `factor_research/tests/test_loop_cli.py`
- `factor_research/tests/test_loop_ci_guard.py`

Modify:

- `factor_research/scripts/test_all.sh` — add new loop tests and CI guard.
- `factor_research/api/main.py` or equivalent router registration file — include loop status router only after service tests pass.
- `WORKFLOW.md` — document the new Loop OS execution path.
- `LOOP_ENGINEERING.md` — document that this is a thin L1 orchestrator, not an alpha judge.
- `SPEC.md` — update central scheduling layer status from event-driven pending to Loop OS MVP.
- `TASKS.md` — add or close the “complete loop closure” item only after implementation is verified.

Durable runtime paths:

- `factor_research/data_lake/governance/loop_events.jsonl`
- `factor_research/data_lake/governance/loop_memory.jsonl`
- `factor_research/reports/loops/`

Do not commit generated data-lake runtime rows unless the project already tracks the target file and the row is explicitly intended as a fixture. Tests must use `tmp_path`.

---

## Definition Of Done

- `python3 tests/test_loop_contracts.py` passes.
- `python3 tests/test_loop_store.py` passes.
- `python3 tests/test_loop_policy.py` passes.
- `python3 tests/test_loop_adapters.py` passes.
- `python3 tests/test_loop_orchestrator.py` passes.
- `python3 tests/test_loop_cli.py` passes.
- `python3 tests/test_loop_ci_guard.py` passes.
- `python3 scripts/ci/check_loop_contracts.py` exits 0.
- `python3 scripts/ci/check_layer_deps.py` exits 0.
- `python3 scripts/ci/check_registry_evidence.py` exits 0.
- `python3 scripts/ci/check_holdout_compliance.py` exits 0.
- `bash scripts/test_all.sh` passes.
- `python3 apps/loop_cli.py status --root .` works from `factor_research/`.
- `python3 apps/loop_cli.py dry-run --root .` records only tmp/test output when run in tests; real workspace dry-run must not alter registry or production files.
- No code path introduced by this plan can promote, register, deploy, or trade without the existing workflow/registry/governance gates.

---

## Task 0: Preflight And Baseline

**Files:**
- Read: `CLAUDE.md`
- Read: `STATUS.md`
- Read: `LOOP_ENGINEERING.md`
- Read: `WORKFLOW.md`
- Read: `SPEC.md`
- No code changes.

- [ ] **Step 1: Confirm working tree scope**

Run:

```bash
git status --short
```

Expected: There may be unrelated dirty files. Record them in the implementation notes and do not touch them unless a later task explicitly names them.

- [ ] **Step 2: Confirm existing loop-related tests**

Run:

```bash
cd factor_research
python3 tests/test_loop_foundations.py
python3 tests/test_research_run_ledger.py
python3 tests/test_trial_count_semantics.py
```

Expected: All pass before new work. If any fail, stop and diagnose; do not build Loop OS on a failing baseline.

- [ ] **Step 3: Confirm layer and holdout guards**

Run:

```bash
cd factor_research
python3 scripts/ci/check_layer_deps.py
python3 scripts/ci/check_holdout_compliance.py
python3 scripts/ci/check_registry_evidence.py
```

Expected: All exit 0. If not, the implementation must not proceed until the governance baseline is understood.

---

## Task 1: Loop Contracts

**Files:**
- Create: `factor_research/loops/__init__.py`
- Create: `factor_research/loops/types.py`
- Test: `factor_research/tests/test_loop_contracts.py`

- [ ] **Step 1: Write the failing contract tests**

Create `factor_research/tests/test_loop_contracts.py`:

```python
from pathlib import Path

from loops.types import (
    EvaluationReport,
    ExperimentArtifact,
    LoopDecision,
    LoopEvent,
    LoopName,
    LoopRun,
    LoopStatus,
)


def test_loop_event_round_trips_json_dict():
    event = LoopEvent(
        run_id="run-1",
        loop=LoopName.DATA,
        status=LoopStatus.PASSED,
        message="manifest fresh",
        payload={"freshness_date": "2026-06-26"},
        created_at="2026-06-27T00:00:00Z",
    )

    encoded = event.to_json_dict()
    decoded = LoopEvent.from_json_dict(encoded)

    assert decoded == event
    assert encoded["loop"] == "data"
    assert encoded["status"] == "passed"


def test_experiment_artifact_has_reproducibility_fields():
    artifact = ExperimentArtifact(
        run_id="run-1",
        artifact_id="artifact-1",
        candidate_id="candidate-a",
        candidate_fingerprint="abc123",
        hypothesis="liquidity stress premium",
        dsl={"op": "rank", "field": "amount"},
        params={"top_n": 25},
        data_fingerprint="lake-fp",
        trial_scope="autoresearch",
        n_trials=12,
        output_path="reports/loops/run-1/artifact-1.json",
    )

    assert artifact.to_json_dict()["n_trials"] == 12
    assert artifact.to_json_dict()["data_fingerprint"] == "lake-fp"
    assert artifact.to_json_dict()["output_path"].endswith("artifact-1.json")


def test_evaluation_report_is_independent_from_experiment_status():
    report = EvaluationReport(
        run_id="run-1",
        artifact_id="artifact-1",
        evaluator="deterministic",
        verdict="review_required",
        reasons=["nine_gate_pending"],
        metrics={"rank_ic": 0.02},
        report_path="reports/loops/run-1/evaluation-artifact-1.json",
    )

    assert report.verdict == "review_required"
    assert "nine_gate_pending" in report.reasons
    assert report.to_json_dict()["metrics"]["rank_ic"] == 0.02


def test_loop_run_summary_uses_events_not_side_effects():
    run = LoopRun(
        run_id="run-1",
        mode="dry-run",
        root=str(Path("/tmp/factor_research")),
        started_at="2026-06-27T00:00:00Z",
        completed_at=None,
        status=LoopStatus.RUNNING,
    )

    assert run.to_json_dict()["status"] == "running"
    assert run.to_json_dict()["mode"] == "dry-run"


def test_loop_decision_requires_explicit_approval_flag():
    decision = LoopDecision(
        run_id="run-1",
        action="promote_candidate",
        allowed=False,
        reasons=["manual_approval_required"],
        requires_manual_approval=True,
    )

    assert decision.allowed is False
    assert decision.requires_manual_approval is True
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research
python3 tests/test_loop_contracts.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'loops'`.

- [ ] **Step 3: Implement loop contract dataclasses**

Create `factor_research/loops/types.py`:

```python
"""Typed contracts for the Loop OS orchestration layer.

This module is intentionally stdlib-only. It defines transport-safe records for
events, experiments, evaluations, and governance decisions. It does not run
research logic and does not judge alpha validity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, ClassVar


class LoopName(str, Enum):
    DATA = "data"
    HYPOTHESIS = "hypothesis"
    EXPERIMENT = "experiment"
    EVALUATION = "evaluation"
    MEMORY = "memory"
    GOVERNANCE = "governance"


class LoopStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


def _enum_to_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: _enum_to_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_enum_to_value(v) for v in value]
    return value


@dataclass(frozen=True)
class JsonRecord:
    """Small base class for JSONL-safe dataclasses."""

    _enum_fields: ClassVar[dict[str, type[Enum]]] = {}

    def to_json_dict(self) -> dict[str, Any]:
        return _enum_to_value(asdict(self))


@dataclass(frozen=True)
class LoopEvent(JsonRecord):
    run_id: str
    loop: LoopName
    status: LoopStatus
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""

    _enum_fields: ClassVar[dict[str, type[Enum]]] = {
        "loop": LoopName,
        "status": LoopStatus,
    }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> "LoopEvent":
        return cls(
            run_id=str(data["run_id"]),
            loop=LoopName(data["loop"]),
            status=LoopStatus(data["status"]),
            message=str(data.get("message", "")),
            payload=dict(data.get("payload") or {}),
            created_at=str(data.get("created_at", "")),
        )


@dataclass(frozen=True)
class LoopRun(JsonRecord):
    run_id: str
    mode: str
    root: str
    started_at: str
    completed_at: str | None
    status: LoopStatus

    _enum_fields: ClassVar[dict[str, type[Enum]]] = {"status": LoopStatus}


@dataclass(frozen=True)
class LoopDecision(JsonRecord):
    run_id: str
    action: str
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    requires_manual_approval: bool = False
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ExperimentArtifact(JsonRecord):
    run_id: str
    artifact_id: str
    candidate_id: str
    candidate_fingerprint: str
    hypothesis: str
    dsl: dict[str, Any]
    params: dict[str, Any]
    data_fingerprint: str
    trial_scope: str
    n_trials: int
    output_path: str


@dataclass(frozen=True)
class EvaluationReport(JsonRecord):
    run_id: str
    artifact_id: str
    evaluator: str
    verdict: str
    reasons: list[str]
    metrics: dict[str, Any]
    report_path: str
```

Create `factor_research/loops/__init__.py`:

```python
"""Loop OS orchestration layer for the research system.

The package coordinates existing canonical modules. It must remain thin:
generation can be delegated to factory/autoresearch, experiments to workflow
and BacktestEngine, validity decisions to 9-Gate/governance, and registry writes
to strategy_registry only.
"""

from .types import (
    EvaluationReport,
    ExperimentArtifact,
    LoopDecision,
    LoopEvent,
    LoopName,
    LoopRun,
    LoopStatus,
)

__all__ = [
    "EvaluationReport",
    "ExperimentArtifact",
    "LoopDecision",
    "LoopEvent",
    "LoopName",
    "LoopRun",
    "LoopStatus",
]
```

- [ ] **Step 4: Add script execution shim for tests**

Because existing tests are often run directly as `python3 tests/test_*.py`, append this block to the bottom of `factor_research/tests/test_loop_contracts.py`:

```python
if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
cd factor_research
python3 tests/test_loop_contracts.py
```

Expected: PASS.

- [ ] **Step 6: Commit this task only**

Run:

```bash
git add factor_research/loops/__init__.py factor_research/loops/types.py factor_research/tests/test_loop_contracts.py
git diff --cached --stat
git diff --cached
git commit -m "feat(loops): add loop orchestration contracts"
```

Expected: staged diff contains only the three files listed above.

---

## Task 2: Append-Only Loop Event Store

**Files:**
- Create: `factor_research/loops/store.py`
- Test: `factor_research/tests/test_loop_store.py`

- [ ] **Step 1: Write failing store tests**

Create `factor_research/tests/test_loop_store.py`:

```python
from loops.store import LoopEventStore
from loops.types import LoopEvent, LoopName, LoopStatus


def test_event_store_appends_jsonl(tmp_path):
    store = LoopEventStore(tmp_path / "loop_events.jsonl")

    store.append(
        LoopEvent(
            run_id="run-1",
            loop=LoopName.DATA,
            status=LoopStatus.PASSED,
            message="data ok",
            payload={"rows": 10},
            created_at="2026-06-27T00:00:00Z",
        )
    )
    store.append(
        LoopEvent(
            run_id="run-1",
            loop=LoopName.GOVERNANCE,
            status=LoopStatus.BLOCKED,
            message="manual approval required",
            payload={"action": "register"},
            created_at="2026-06-27T00:01:00Z",
        )
    )

    rows = store.read_all()
    assert len(rows) == 2
    assert rows[0].loop == LoopName.DATA
    assert rows[1].status == LoopStatus.BLOCKED


def test_event_store_reconstructs_latest_status_by_loop(tmp_path):
    store = LoopEventStore(tmp_path / "loop_events.jsonl")
    store.append(LoopEvent("run-1", LoopName.DATA, LoopStatus.RUNNING, "start"))
    store.append(LoopEvent("run-1", LoopName.DATA, LoopStatus.PASSED, "done"))
    store.append(LoopEvent("run-1", LoopName.EVALUATION, LoopStatus.FAILED, "bad"))

    latest = store.latest_by_loop("run-1")

    assert latest[LoopName.DATA].status == LoopStatus.PASSED
    assert latest[LoopName.EVALUATION].status == LoopStatus.FAILED


def test_event_store_ignores_other_runs_in_latest_status(tmp_path):
    store = LoopEventStore(tmp_path / "loop_events.jsonl")
    store.append(LoopEvent("run-1", LoopName.DATA, LoopStatus.FAILED, "old"))
    store.append(LoopEvent("run-2", LoopName.DATA, LoopStatus.PASSED, "new"))

    assert store.latest_by_loop("run-1")[LoopName.DATA].status == LoopStatus.FAILED
    assert store.latest_by_loop("run-2")[LoopName.DATA].status == LoopStatus.PASSED


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research
python3 tests/test_loop_store.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'loops.store'`.

- [ ] **Step 3: Implement append-only event store**

Create `factor_research/loops/store.py`:

```python
"""Append-only JSONL storage for Loop OS events."""

from __future__ import annotations

import json
from pathlib import Path

from .types import LoopEvent, LoopName


class LoopEventStore:
    """Small append-only event store.

    The store intentionally has no update/delete methods. Corrections must be
    represented as later events.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, event: LoopEvent) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event.to_json_dict(), ensure_ascii=False, sort_keys=True))
            fh.write("\n")

    def read_all(self) -> list[LoopEvent]:
        if not self.path.exists():
            return []
        events: list[LoopEvent] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                raw = line.strip()
                if not raw:
                    continue
                events.append(LoopEvent.from_json_dict(json.loads(raw)))
        return events

    def latest_by_loop(self, run_id: str) -> dict[LoopName, LoopEvent]:
        latest: dict[LoopName, LoopEvent] = {}
        for event in self.read_all():
            if event.run_id == run_id:
                latest[event.loop] = event
        return latest
```

- [ ] **Step 4: Run store tests**

Run:

```bash
cd factor_research
python3 tests/test_loop_store.py
```

Expected: PASS.

- [ ] **Step 5: Commit this task only**

Run:

```bash
git add factor_research/loops/store.py factor_research/tests/test_loop_store.py
git diff --cached --stat
git diff --cached
git commit -m "feat(loops): add append-only loop event store"
```

---

## Task 3: Governance Policy API

**Files:**
- Create: `factor_research/loops/policy.py`
- Test: `factor_research/tests/test_loop_policy.py`

- [ ] **Step 1: Write failing policy tests**

Create `factor_research/tests/test_loop_policy.py`:

```python
from loops.policy import GovernancePolicy


def test_policy_allows_read_only_daily_dry_run():
    policy = GovernancePolicy.default()
    decision = policy.decide(action="run_daily_loop", mode="dry-run", payload={})

    assert decision.allowed is True
    assert decision.requires_manual_approval is False


def test_policy_blocks_registry_write_without_approval():
    policy = GovernancePolicy.default()
    decision = policy.decide(
        action="register_strategy",
        mode="daily",
        payload={"manual_approval": False},
    )

    assert decision.allowed is False
    assert decision.requires_manual_approval is True
    assert "manual_approval_required" in decision.reasons


def test_policy_blocks_production_trade_always():
    policy = GovernancePolicy.default()
    decision = policy.decide(
        action="place_real_order",
        mode="daily",
        payload={"manual_approval": True},
    )

    assert decision.allowed is False
    assert "real_trading_out_of_scope" in decision.reasons


def test_policy_enforces_experiment_budget():
    policy = GovernancePolicy(max_experiments_per_run=2, max_hypotheses_per_run=5)

    allowed = policy.decide("generate_hypotheses", "daily", {"requested": 2})
    blocked = policy.decide("generate_hypotheses", "daily", {"requested": 6})

    assert allowed.allowed is True
    assert blocked.allowed is False
    assert "hypothesis_budget_exceeded" in blocked.reasons


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research
python3 tests/test_loop_policy.py
```

Expected: FAIL with `ModuleNotFoundError: No module named 'loops.policy'`.

- [ ] **Step 3: Implement policy API**

Create `factor_research/loops/policy.py`:

```python
"""Governance policy for Loop OS actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .types import LoopDecision


@dataclass(frozen=True)
class GovernancePolicy:
    max_experiments_per_run: int = 20
    max_hypotheses_per_run: int = 20

    @classmethod
    def default(cls) -> "GovernancePolicy":
        return cls()

    def decide(self, action: str, mode: str, payload: dict[str, Any]) -> LoopDecision:
        reasons: list[str] = []
        requires_manual = False

        if action in {"place_real_order", "submit_order", "trade_real_account"}:
            reasons.append("real_trading_out_of_scope")

        if action in {"register_strategy", "promote_to_registry", "touch_holdout"}:
            if not bool(payload.get("manual_approval")):
                reasons.append("manual_approval_required")
                requires_manual = True

        if action == "generate_hypotheses":
            requested = int(payload.get("requested") or 0)
            if requested > self.max_hypotheses_per_run:
                reasons.append("hypothesis_budget_exceeded")

        if action == "run_experiments":
            requested = int(payload.get("requested") or 0)
            if requested > self.max_experiments_per_run:
                reasons.append("experiment_budget_exceeded")

        allowed = not reasons
        if mode == "dry-run" and action in {"run_daily_loop", "read_status"}:
            allowed = True

        return LoopDecision(
            run_id=str(payload.get("run_id") or ""),
            action=action,
            allowed=allowed,
            reasons=reasons,
            requires_manual_approval=requires_manual,
            payload={"mode": mode},
        )
```

- [ ] **Step 4: Run policy tests**

Run:

```bash
cd factor_research
python3 tests/test_loop_policy.py
```

Expected: PASS.

- [ ] **Step 5: Commit this task only**

Run:

```bash
git add factor_research/loops/policy.py factor_research/tests/test_loop_policy.py
git diff --cached --stat
git diff --cached
git commit -m "feat(loops): add governance policy gates"
```

---

## Task 4: Shared Context And Data Loop Adapter

**Files:**
- Create: `factor_research/loops/context.py`
- Create: `factor_research/loops/data.py`
- Test: extend `factor_research/tests/test_loop_adapters.py`

- [ ] **Step 1: Write failing data adapter tests**

Create `factor_research/tests/test_loop_adapters.py`:

```python
import json

from loops.context import LoopContext
from loops.data import run_data_loop
from loops.types import LoopName, LoopStatus


def test_data_loop_passes_when_manifest_and_quality_exist(tmp_path):
    root = tmp_path
    lake = root / "data_lake"
    lake.mkdir()
    (lake / "_manifest.json").write_text(json.dumps({"price": {"latest": "2026-06-26"}}), encoding="utf-8")
    (lake / "quality_report.json").write_text(json.dumps({"status": "ok"}), encoding="utf-8")

    event = run_data_loop(LoopContext(root=root), run_id="run-1")

    assert event.loop == LoopName.DATA
    assert event.status == LoopStatus.PASSED
    assert event.payload["manifest_exists"] is True
    assert event.payload["quality_report_exists"] is True


def test_data_loop_blocks_when_manifest_missing(tmp_path):
    root = tmp_path
    (root / "data_lake").mkdir()

    event = run_data_loop(LoopContext(root=root), run_id="run-1")

    assert event.status == LoopStatus.BLOCKED
    assert "manifest_missing" in event.payload["issues"]


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research
python3 tests/test_loop_adapters.py
```

Expected: FAIL with missing `loops.context` or `loops.data`.

- [ ] **Step 3: Implement context and data loop**

Create `factor_research/loops/context.py`:

```python
"""Shared filesystem context for Loop OS."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LoopContext:
    root: Path

    @property
    def data_lake(self) -> Path:
        return self.root / "data_lake"

    @property
    def governance_dir(self) -> Path:
        return self.data_lake / "governance"

    @property
    def reports_dir(self) -> Path:
        return self.root / "reports" / "loops"
```

Create `factor_research/loops/data.py`:

```python
"""Data Loop adapter.

This adapter only inspects existing data health artifacts. It does not fetch
network data and does not repair data.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .context import LoopContext
from .types import LoopEvent, LoopName, LoopStatus


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_data_loop(context: LoopContext, run_id: str) -> LoopEvent:
    manifest = context.data_lake / "_manifest.json"
    quality = context.data_lake / "quality_report.json"
    issues: list[str] = []

    if not manifest.exists():
        issues.append("manifest_missing")

    status = LoopStatus.PASSED if not issues else LoopStatus.BLOCKED
    return LoopEvent(
        run_id=run_id,
        loop=LoopName.DATA,
        status=status,
        message="data health artifacts inspected",
        payload={
            "manifest_exists": manifest.exists(),
            "quality_report_exists": quality.exists(),
            "issues": issues,
        },
        created_at=_now(),
    )
```

- [ ] **Step 4: Run adapter tests**

Run:

```bash
cd factor_research
python3 tests/test_loop_adapters.py
```

Expected: PASS.

- [ ] **Step 5: Commit this task only**

Run:

```bash
git add factor_research/loops/context.py factor_research/loops/data.py factor_research/tests/test_loop_adapters.py
git diff --cached --stat
git diff --cached
git commit -m "feat(loops): add data loop adapter"
```

---

## Task 5: Hypothesis, Experiment, Evaluation, And Memory Adapters

**Files:**
- Create: `factor_research/loops/hypothesis.py`
- Create: `factor_research/loops/experiment.py`
- Create: `factor_research/loops/evaluation.py`
- Create: `factor_research/loops/memory.py`
- Test: extend `factor_research/tests/test_loop_adapters.py`

- [ ] **Step 1: Extend adapter tests**

Append to `factor_research/tests/test_loop_adapters.py`:

```python
from loops.evaluation import evaluate_artifact
from loops.experiment import write_experiment_artifact
from loops.hypothesis import CandidateSeed, run_hypothesis_loop
from loops.memory import write_memory_feedback


def test_hypothesis_loop_uses_seed_provider_without_judging_alpha(tmp_path):
    seeds = [
        CandidateSeed(
            candidate_id="c1",
            candidate_fingerprint="fp1",
            hypothesis="liquidity stress premium",
            dsl={"op": "rank", "field": "amount"},
            params={"top_n": 25},
        )
    ]

    event = run_hypothesis_loop(LoopContext(root=tmp_path), run_id="run-1", seeds=seeds)

    assert event.status == LoopStatus.PASSED
    assert event.payload["candidate_count"] == 1
    assert "verdict" not in event.payload


def test_experiment_artifact_writer_persists_reproducibility_contract(tmp_path):
    context = LoopContext(root=tmp_path)
    artifact = write_experiment_artifact(
        context=context,
        run_id="run-1",
        candidate=CandidateSeed(
            candidate_id="c1",
            candidate_fingerprint="fp1",
            hypothesis="liquidity stress premium",
            dsl={"op": "rank", "field": "amount"},
            params={"top_n": 25},
        ),
        data_fingerprint="lake-fp",
        trial_scope="autoresearch",
        n_trials=3,
    )

    assert artifact.output_path.endswith(".json")
    assert (tmp_path / artifact.output_path).exists()
    assert artifact.n_trials == 3


def test_evaluation_report_is_read_only_verdict_over_artifact(tmp_path):
    context = LoopContext(root=tmp_path)
    artifact = write_experiment_artifact(
        context,
        "run-1",
        CandidateSeed("c1", "fp1", "hypothesis", {"op": "rank"}, {}),
        "lake-fp",
        "autoresearch",
        1,
    )

    report = evaluate_artifact(context, artifact, metrics={"rank_ic": 0.01}, reasons=["nine_gate_pending"])

    assert report.verdict == "review_required"
    assert "nine_gate_pending" in report.reasons
    assert (tmp_path / report.report_path).exists()


def test_memory_feedback_is_append_only(tmp_path):
    context = LoopContext(root=tmp_path)

    first = write_memory_feedback(
        context,
        run_id="run-1",
        item_id="c1",
        outcome="failed",
        reasons=["cost_too_high"],
        regime_tags=["small_cap_bear"],
    )
    second = write_memory_feedback(
        context,
        run_id="run-1",
        item_id="c2",
        outcome="failed",
        reasons=["redundant_with_book"],
        regime_tags=["liquidity_stress"],
    )

    path = tmp_path / "data_lake" / "governance" / "loop_memory.jsonl"
    assert first.status == LoopStatus.PASSED
    assert second.status == LoopStatus.PASSED
    assert len(path.read_text(encoding="utf-8").strip().splitlines()) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd factor_research
python3 tests/test_loop_adapters.py
```

Expected: FAIL with missing adapter modules.

- [ ] **Step 3: Implement hypothesis adapter**

Create `factor_research/loops/hypothesis.py`:

```python
"""Hypothesis Loop adapter."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from .context import LoopContext
from .types import LoopEvent, LoopName, LoopStatus


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class CandidateSeed:
    candidate_id: str
    candidate_fingerprint: str
    hypothesis: str
    dsl: dict[str, Any]
    params: dict[str, Any]


def run_hypothesis_loop(context: LoopContext, run_id: str, seeds: list[CandidateSeed]) -> LoopEvent:
    del context
    return LoopEvent(
        run_id=run_id,
        loop=LoopName.HYPOTHESIS,
        status=LoopStatus.PASSED if seeds else LoopStatus.SKIPPED,
        message="candidate hypotheses collected",
        payload={
            "candidate_count": len(seeds),
            "candidate_ids": [seed.candidate_id for seed in seeds],
        },
        created_at=_now(),
    )
```

- [ ] **Step 4: Implement experiment adapter**

Create `factor_research/loops/experiment.py`:

```python
"""Experiment Loop adapter and artifact writer."""

from __future__ import annotations

import json
from hashlib import sha256

from .context import LoopContext
from .hypothesis import CandidateSeed
from .types import ExperimentArtifact


def _artifact_id(run_id: str, fingerprint: str) -> str:
    return sha256(f"{run_id}:{fingerprint}".encode("utf-8")).hexdigest()[:16]


def write_experiment_artifact(
    context: LoopContext,
    run_id: str,
    candidate: CandidateSeed,
    data_fingerprint: str,
    trial_scope: str,
    n_trials: int,
) -> ExperimentArtifact:
    artifact_id = _artifact_id(run_id, candidate.candidate_fingerprint)
    rel_path = f"reports/loops/{run_id}/{artifact_id}.json"
    abs_path = context.root / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    artifact = ExperimentArtifact(
        run_id=run_id,
        artifact_id=artifact_id,
        candidate_id=candidate.candidate_id,
        candidate_fingerprint=candidate.candidate_fingerprint,
        hypothesis=candidate.hypothesis,
        dsl=candidate.dsl,
        params=candidate.params,
        data_fingerprint=data_fingerprint,
        trial_scope=trial_scope,
        n_trials=int(n_trials),
        output_path=rel_path,
    )

    abs_path.write_text(
        json.dumps(artifact.to_json_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return artifact
```

- [ ] **Step 5: Implement evaluation adapter**

Create `factor_research/loops/evaluation.py`:

```python
"""Evaluation Loop adapter.

The adapter reads experiment artifacts and writes evaluation reports. It does
not mutate candidates, experiments, registry, or production manifests.
"""

from __future__ import annotations

import json
from typing import Any

from .context import LoopContext
from .types import EvaluationReport, ExperimentArtifact


def evaluate_artifact(
    context: LoopContext,
    artifact: ExperimentArtifact,
    metrics: dict[str, Any],
    reasons: list[str],
) -> EvaluationReport:
    verdict = "review_required" if reasons else "passed_precheck"
    rel_path = f"reports/loops/{artifact.run_id}/evaluation-{artifact.artifact_id}.json"
    abs_path = context.root / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    report = EvaluationReport(
        run_id=artifact.run_id,
        artifact_id=artifact.artifact_id,
        evaluator="deterministic",
        verdict=verdict,
        reasons=list(reasons),
        metrics=dict(metrics),
        report_path=rel_path,
    )
    abs_path.write_text(
        json.dumps(report.to_json_dict(), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return report
```

- [ ] **Step 6: Implement memory adapter**

Create `factor_research/loops/memory.py`:

```python
"""Memory Loop adapter for structured feedback."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from .context import LoopContext
from .types import LoopEvent, LoopName, LoopStatus


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_memory_feedback(
    context: LoopContext,
    run_id: str,
    item_id: str,
    outcome: str,
    reasons: list[str],
    regime_tags: list[str],
) -> LoopEvent:
    path = context.governance_dir / "loop_memory.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "created_at": _now(),
        "run_id": run_id,
        "item_id": item_id,
        "outcome": outcome,
        "reasons": list(reasons),
        "regime_tags": list(regime_tags),
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
        fh.write("\n")

    return LoopEvent(
        run_id=run_id,
        loop=LoopName.MEMORY,
        status=LoopStatus.PASSED,
        message="memory feedback appended",
        payload={"item_id": item_id, "outcome": outcome, "reasons": list(reasons)},
        created_at=row["created_at"],
    )
```

- [ ] **Step 7: Run adapter tests**

Run:

```bash
cd factor_research
python3 tests/test_loop_adapters.py
```

Expected: PASS.

- [ ] **Step 8: Commit this task only**

Run:

```bash
git add factor_research/loops/hypothesis.py factor_research/loops/experiment.py factor_research/loops/evaluation.py factor_research/loops/memory.py factor_research/tests/test_loop_adapters.py
git diff --cached --stat
git diff --cached
git commit -m "feat(loops): add loop adapters and artifacts"
```

---

## Task 6: Six-Loop Orchestrator

**Files:**
- Create: `factor_research/loops/orchestrator.py`
- Test: `factor_research/tests/test_loop_orchestrator.py`

- [ ] **Step 1: Write failing orchestrator tests**

Create `factor_research/tests/test_loop_orchestrator.py`:

```python
import json

from loops.context import LoopContext
from loops.hypothesis import CandidateSeed
from loops.orchestrator import LoopOrchestrator
from loops.policy import GovernancePolicy
from loops.store import LoopEventStore
from loops.types import LoopName, LoopStatus


def _context_with_data(tmp_path):
    lake = tmp_path / "data_lake"
    lake.mkdir()
    (lake / "_manifest.json").write_text(json.dumps({"price": {"latest": "2026-06-26"}}), encoding="utf-8")
    return LoopContext(root=tmp_path)


def test_orchestrator_runs_daily_mvp(tmp_path):
    context = _context_with_data(tmp_path)
    store = LoopEventStore(tmp_path / "data_lake" / "governance" / "loop_events.jsonl")
    orchestrator = LoopOrchestrator(context=context, store=store, policy=GovernancePolicy.default())
    seeds = [CandidateSeed("c1", "fp1", "hypothesis", {"op": "rank"}, {})]

    run = orchestrator.run_daily(mode="dry-run", seeds=seeds)
    latest = store.latest_by_loop(run.run_id)

    assert run.status == LoopStatus.PASSED
    assert latest[LoopName.DATA].status == LoopStatus.PASSED
    assert latest[LoopName.HYPOTHESIS].status == LoopStatus.PASSED
    assert latest[LoopName.EVALUATION].status == LoopStatus.PASSED
    assert latest[LoopName.GOVERNANCE].status == LoopStatus.PASSED


def test_orchestrator_blocks_when_data_loop_blocks(tmp_path):
    context = LoopContext(root=tmp_path)
    store = LoopEventStore(tmp_path / "data_lake" / "governance" / "loop_events.jsonl")
    orchestrator = LoopOrchestrator(context=context, store=store, policy=GovernancePolicy.default())

    run = orchestrator.run_daily(mode="dry-run", seeds=[])

    assert run.status == LoopStatus.BLOCKED
    assert store.latest_by_loop(run.run_id)[LoopName.DATA].status == LoopStatus.BLOCKED


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research
python3 tests/test_loop_orchestrator.py
```

Expected: FAIL with missing `loops.orchestrator`.

- [ ] **Step 3: Implement orchestrator**

Create `factor_research/loops/orchestrator.py`:

```python
"""Six-loop orchestrator for the daily MVP."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from .context import LoopContext
from .data import run_data_loop
from .evaluation import evaluate_artifact
from .experiment import write_experiment_artifact
from .hypothesis import CandidateSeed, run_hypothesis_loop
from .memory import write_memory_feedback
from .policy import GovernancePolicy
from .store import LoopEventStore
from .types import LoopEvent, LoopName, LoopRun, LoopStatus


def _now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class LoopOrchestrator:
    def __init__(self, context: LoopContext, store: LoopEventStore, policy: GovernancePolicy):
        self.context = context
        self.store = store
        self.policy = policy

    def _append(self, event: LoopEvent) -> LoopEvent:
        self.store.append(event)
        return event

    def run_daily(self, mode: str, seeds: list[CandidateSeed]) -> LoopRun:
        run_id = f"loop-{uuid4().hex[:12]}"
        started_at = _now()

        policy_decision = self.policy.decide(
            "run_daily_loop",
            mode,
            {"run_id": run_id, "requested": len(seeds)},
        )
        if not policy_decision.allowed:
            self._append(
                LoopEvent(
                    run_id=run_id,
                    loop=LoopName.GOVERNANCE,
                    status=LoopStatus.BLOCKED,
                    message="daily loop blocked by policy",
                    payload=policy_decision.to_json_dict(),
                    created_at=_now(),
                )
            )
            return LoopRun(run_id, mode, str(self.context.root), started_at, _now(), LoopStatus.BLOCKED)

        data_event = self._append(run_data_loop(self.context, run_id))
        if data_event.status != LoopStatus.PASSED:
            return LoopRun(run_id, mode, str(self.context.root), started_at, _now(), LoopStatus.BLOCKED)

        self._append(run_hypothesis_loop(self.context, run_id, seeds))

        artifacts = [
            write_experiment_artifact(
                self.context,
                run_id,
                seed,
                data_fingerprint="unknown",
                trial_scope="loop_daily_mvp",
                n_trials=len(seeds),
            )
            for seed in seeds
        ]

        self._append(
            LoopEvent(
                run_id=run_id,
                loop=LoopName.EXPERIMENT,
                status=LoopStatus.PASSED if artifacts else LoopStatus.SKIPPED,
                message="experiment artifacts written",
                payload={"artifact_count": len(artifacts)},
                created_at=_now(),
            )
        )

        reports = [
            evaluate_artifact(
                self.context,
                artifact,
                metrics={},
                reasons=["nine_gate_pending"],
            )
            for artifact in artifacts
        ]
        self._append(
            LoopEvent(
                run_id=run_id,
                loop=LoopName.EVALUATION,
                status=LoopStatus.PASSED if reports else LoopStatus.SKIPPED,
                message="evaluation reports written",
                payload={"report_count": len(reports)},
                created_at=_now(),
            )
        )

        for report in reports:
            self._append(
                write_memory_feedback(
                    self.context,
                    run_id=run_id,
                    item_id=report.artifact_id,
                    outcome=report.verdict,
                    reasons=report.reasons,
                    regime_tags=[],
                )
            )

        self._append(
            LoopEvent(
                run_id=run_id,
                loop=LoopName.GOVERNANCE,
                status=LoopStatus.PASSED,
                message="daily loop completed without registry or production side effects",
                payload={"mode": mode},
                created_at=_now(),
            )
        )
        return LoopRun(run_id, mode, str(self.context.root), started_at, _now(), LoopStatus.PASSED)
```

- [ ] **Step 4: Run orchestrator tests**

Run:

```bash
cd factor_research
python3 tests/test_loop_orchestrator.py
```

Expected: PASS.

- [ ] **Step 5: Commit this task only**

Run:

```bash
git add factor_research/loops/orchestrator.py factor_research/tests/test_loop_orchestrator.py
git diff --cached --stat
git diff --cached
git commit -m "feat(loops): add daily loop orchestrator"
```

---

## Task 7: CLI Entry Point

**Files:**
- Create: `factor_research/apps/loop_cli.py`
- Test: `factor_research/tests/test_loop_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `factor_research/tests/test_loop_cli.py`:

```python
import json
import subprocess
import sys
from pathlib import Path


def test_loop_cli_status_handles_empty_store(tmp_path):
    script = Path(__file__).resolve().parents[1] / "apps" / "loop_cli.py"
    result = subprocess.run(
        [sys.executable, str(script), "status", "--root", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "loop_events" in result.stdout


def test_loop_cli_dry_run_writes_events(tmp_path):
    lake = tmp_path / "data_lake"
    lake.mkdir()
    (lake / "_manifest.json").write_text(json.dumps({"price": {"latest": "2026-06-26"}}), encoding="utf-8")

    script = Path(__file__).resolve().parents[1] / "apps" / "loop_cli.py"
    result = subprocess.run(
        [sys.executable, str(script), "dry-run", "--root", str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "status=passed" in result.stdout
    assert (lake / "governance" / "loop_events.jsonl").exists()


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
cd factor_research
python3 tests/test_loop_cli.py
```

Expected: FAIL because `apps/loop_cli.py` does not exist.

- [ ] **Step 3: Implement CLI**

Create `factor_research/apps/loop_cli.py`:

```python
#!/usr/bin/env python3
"""CLI for the Loop OS daily MVP."""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from loops.context import LoopContext
from loops.hypothesis import CandidateSeed
from loops.orchestrator import LoopOrchestrator
from loops.policy import GovernancePolicy
from loops.store import LoopEventStore


def _context(root_arg: str) -> LoopContext:
    root = Path(root_arg).resolve()
    return LoopContext(root=root)


def _store(context: LoopContext) -> LoopEventStore:
    return LoopEventStore(context.governance_dir / "loop_events.jsonl")


def cmd_status(args: argparse.Namespace) -> int:
    context = _context(args.root)
    store = _store(context)
    events = store.read_all()
    print(f"loop_events={len(events)} path={store.path}")
    if events:
        last = events[-1]
        print(f"last_run={last.run_id} last_loop={last.loop.value} last_status={last.status.value}")
    return 0


def cmd_dry_run(args: argparse.Namespace) -> int:
    context = _context(args.root)
    orchestrator = LoopOrchestrator(
        context=context,
        store=_store(context),
        policy=GovernancePolicy.default(),
    )
    seeds = [
        CandidateSeed(
            candidate_id="dry-run-seed",
            candidate_fingerprint="dry-run-seed",
            hypothesis="dry-run plumbing seed; not an alpha claim",
            dsl={"op": "noop"},
            params={},
        )
    ]
    run = orchestrator.run_daily(mode="dry-run", seeds=seeds)
    print(f"run_id={run.run_id} status={run.status.value}")
    return 0 if run.status.value in {"passed", "blocked"} else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Loop OS CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status")
    status.add_argument("--root", default=str(ROOT))
    status.set_defaults(func=cmd_status)

    dry_run = sub.add_parser("dry-run")
    dry_run.add_argument("--root", default=str(ROOT))
    dry_run.set_defaults(func=cmd_dry_run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
cd factor_research
python3 tests/test_loop_cli.py
```

Expected: PASS.

- [ ] **Step 5: Run CLI manually in workspace**

Run:

```bash
cd factor_research
python3 apps/loop_cli.py status --root .
```

Expected: prints `loop_events=<number> path=.../data_lake/governance/loop_events.jsonl`.

- [ ] **Step 6: Commit this task only**

Run:

```bash
git add factor_research/apps/loop_cli.py factor_research/tests/test_loop_cli.py
git diff --cached --stat
git diff --cached
git commit -m "feat(loops): add loop cli"
```

---

## Task 8: Static Loop Contract Guard

**Files:**
- Create: `factor_research/scripts/ci/check_loop_contracts.py`
- Test: `factor_research/tests/test_loop_ci_guard.py`
- Modify: `factor_research/scripts/test_all.sh`

- [ ] **Step 1: Write failing guard tests**

Create `factor_research/tests/test_loop_ci_guard.py`:

```python
import subprocess
import sys
from pathlib import Path


def test_loop_contract_guard_passes_repo():
    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "ci" / "check_loop_contracts.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Loop contract guard passed" in result.stdout


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research
python3 tests/test_loop_ci_guard.py
```

Expected: FAIL because guard script does not exist.

- [ ] **Step 3: Implement guard**

Create `factor_research/scripts/ci/check_loop_contracts.py`:

```python
#!/usr/bin/env python3
"""Guard Loop OS boundaries.

Rules:
- loops package may not import production.
- loops package may not import strategy_registry.
- loops package may not write registry JSON names directly.
- experiment adapter may not mention alpha passed/effective verdict strings.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOOPS = ROOT / "loops"

FORBIDDEN_IMPORT_PREFIXES = {
    "production",
    "strategy_registry",
}

FORBIDDEN_TEXT = {
    "strategy_versions.json",
    "strategy_families.json",
    '"在册"',
    "'在册'",
}


def _module_name(node: ast.AST) -> str:
    if isinstance(node, ast.Import):
        return ",".join(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return node.module or ""
    return ""


def main() -> int:
    errors: list[str] = []
    for path in sorted(LOOPS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text, filename=str(path))
        rel = path.relative_to(ROOT)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                name = _module_name(node)
                if any(name == prefix or name.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES):
                    errors.append(f"{rel}: forbidden import {name}")
        for token in FORBIDDEN_TEXT:
            if token in text:
                errors.append(f"{rel}: forbidden direct registry/status token {token}")

    if errors:
        for error in errors:
            print(error)
        return 1
    print("Loop contract guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run guard tests and guard**

Run:

```bash
cd factor_research
python3 tests/test_loop_ci_guard.py
python3 scripts/ci/check_loop_contracts.py
```

Expected: both pass.

- [ ] **Step 5: Add guard to test_all**

Modify `factor_research/scripts/test_all.sh` by adding the following near the other CI guard calls:

```bash
python3 scripts/ci/check_loop_contracts.py
```

- [ ] **Step 6: Run focused validation**

Run:

```bash
cd factor_research
python3 scripts/ci/check_loop_contracts.py
python3 scripts/ci/check_layer_deps.py
```

Expected: both exit 0.

- [ ] **Step 7: Commit this task only**

Run:

```bash
git add factor_research/scripts/ci/check_loop_contracts.py factor_research/tests/test_loop_ci_guard.py factor_research/scripts/test_all.sh
git diff --cached --stat
git diff --cached
git commit -m "test(loops): guard loop orchestration boundaries"
```

---

## Task 9: Read Service And API Status Surface

**Files:**
- Create: `factor_research/services/read/loops.py`
- Create: `factor_research/api/routers/loops.py`
- Modify: `factor_research/api/main.py`
- Test: `factor_research/tests/test_loop_api.py`

- [ ] **Step 1: Confirm router registration context**

Run:

```bash
cd factor_research
rg "include_router|FastAPI" api services tests -n
```

Expected: confirm `factor_research/api/main.py` is the API app file. Use the existing `from api.routers import (...)` style and do not invent a second API app.

- [ ] **Step 2: Write API/read tests**

Create `factor_research/tests/test_loop_api.py`:

```python
import asyncio

import httpx

from api.main import app


def test_loop_status_api_exposes_read_only_summary():
    async def run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/loops/status")

    response = asyncio.run(run())

    assert response.status_code == 200
    body = response.json()
    assert "loop_events_count" in body
    assert "event_store" in body
    assert "place_real_order" not in str(body)


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
```

- [ ] **Step 3: Implement read service**

Create `factor_research/services/read/loops.py`:

```python
"""Read model for Loop OS status."""

from __future__ import annotations

from pathlib import Path

from loops.context import LoopContext
from loops.store import LoopEventStore


def get_loop_status(root: Path | None = None) -> dict:
    base = root or Path(__file__).resolve().parents[2]
    context = LoopContext(root=base)
    store = LoopEventStore(context.governance_dir / "loop_events.jsonl")
    events = store.read_all()
    last = events[-1].to_json_dict() if events else None
    return {
        "loop_events_count": len(events),
        "event_store": str(store.path),
        "last_event": last,
    }
```

- [ ] **Step 4: Implement API router**

Create `factor_research/api/routers/loops.py`:

```python
"""Loop OS status routes."""

from __future__ import annotations

from fastapi import APIRouter

from services.read.loops import get_loop_status

router = APIRouter(prefix="/loops", tags=["loops"])


@router.get("/status")
def loop_status() -> dict:
    return get_loop_status()
```

- [ ] **Step 5: Register router**

In `factor_research/api/main.py`, extend the existing router import:

```python
from api.routers import (agent, backtest, data, experiments, factors, loops, paper, portfolio,
                         risk, settings, state, strategies, system, trade_readiness, governance)
```

and:

```python
app.include_router(loops.router)
```

Match the repo's current router style exactly.

- [ ] **Step 6: Run API tests**

Run:

```bash
cd factor_research
python3 tests/test_loop_api.py
python3 tests/test_api_contracts.py
```

Expected: PASS.

- [ ] **Step 7: Commit this task only**

Run:

```bash
git add factor_research/services/read/loops.py factor_research/api/routers/loops.py factor_research/tests/test_loop_api.py factor_research/api/main.py
git diff --cached --stat
git diff --cached
git commit -m "feat(loops): expose loop status read API"
```

---

## Task 10: Documentation Updates

**Files:**
- Modify: `WORKFLOW.md`
- Modify: `LOOP_ENGINEERING.md`
- Modify: `SPEC.md`
- Modify: `TASKS.md`

- [ ] **Step 1: Update WORKFLOW**

Add a section named `Loop OS 闭环编排` with this content:

```markdown
## Loop OS 闭环编排

`factor_research/loops/` 是薄编排层，只负责把 Data / Hypothesis / Experiment / Evaluation / Memory / Governance 串成可审计事件流。

边界：
- Data Loop 只读数据健康产物，不联网修数。
- Hypothesis Loop 只收集候选，不判断有效性。
- Experiment Loop 只写可复现实验产物。
- Evaluation Loop 只读实验产物，并调用确定性评估逻辑。
- Memory Loop 只 append-only 沉淀反馈。
- Governance Loop 控预算、审批和禁止动作。

正式入册仍只能走 `workflow/promote.py` → `strategy_registry.register()`；真实交易仍只给人工参考，不由 Loop OS 下单。
```

- [ ] **Step 2: Update LOOP_ENGINEERING**

Add a short note under the L1 automation section:

```markdown
`factor_research/loops/` 是 L1 的编排壳，不是新适应度函数。它不得替代 9-Gate、DSR、holdout、marginal/capacity 或 registry 闸门。
```

- [ ] **Step 3: Update SPEC**

In the central scheduling layer section, add:

```markdown
Loop OS MVP 已提供 append-only `loop_events.jsonl`、daily dry-run 编排、状态 API 和 CI 边界守卫；完整 event-driven 自动触发仍按后续任务推进。
```

- [ ] **Step 4: Update TASKS**

Add one open task if follow-up remains:

```markdown
- [ ] **Loop OS 从 dry-run MVP 接入周度真实候选源** — 当前 `apps/loop_cli.py dry-run` 使用 plumbing seed 验证闭环，不生成真实 alpha 结论。下一步把 Hypothesis Loop 接到受预算约束的 `services/actions/autoresearch_search.py` 候选源，并保持 Evaluation 独立裁决。谁:研究/workflow。
```

If the implementation also wires a real bounded candidate source, mark that line as completed and describe evidence.

- [ ] **Step 5: Run markdown sanity check**

Run:

```bash
rg "Loop OS|loop_events|factor_research/loops" WORKFLOW.md LOOP_ENGINEERING.md SPEC.md TASKS.md
```

Expected: all four docs mention the new layer consistently.

- [ ] **Step 6: Commit documentation only**

Run:

```bash
git add WORKFLOW.md LOOP_ENGINEERING.md SPEC.md TASKS.md
git diff --cached --stat
git diff --cached
git commit -m "docs(loops): document loop closure architecture"
```

---

## Task 11: Full Verification

**Files:**
- No new files unless fixing failures.

- [ ] **Step 1: Run all focused loop tests**

Run:

```bash
cd factor_research
python3 tests/test_loop_contracts.py
python3 tests/test_loop_store.py
python3 tests/test_loop_policy.py
python3 tests/test_loop_adapters.py
python3 tests/test_loop_orchestrator.py
python3 tests/test_loop_cli.py
python3 tests/test_loop_ci_guard.py
```

Expected: all pass.

- [ ] **Step 2: Run governance and architecture guards**

Run:

```bash
cd factor_research
python3 scripts/ci/check_loop_contracts.py
python3 scripts/ci/check_layer_deps.py
python3 scripts/ci/check_lake_writers.py
python3 scripts/ci/check_no_legacy_data.py
python3 scripts/ci/check_registry_evidence.py
python3 scripts/ci/check_holdout_compliance.py
```

Expected: all exit 0.

- [ ] **Step 3: Run full backend suite**

Run:

```bash
cd factor_research
bash scripts/test_all.sh
```

Expected: all pass.

- [ ] **Step 4: Run web checks only if API/router changed affects frontend contract**

Run:

```bash
cd web
npm test
npx tsc --noEmit
npm run lint
```

Expected: all pass. If frontend files were not touched and no API contract used by Web changed, record that web checks were not required.

- [ ] **Step 5: Confirm no unintended runtime state is staged**

Run:

```bash
git status --short
```

Expected: only intended source/test/doc files are modified or untracked. Do not stage generated `data_lake/governance/loop_events.jsonl`, `loop_memory.jsonl`, or `reports/loops/` unless a specific fixture was intentionally created under tests.

- [ ] **Step 6: Commit verification fixes only if needed**

If verification required fixes, stage only the exact changed files:

```bash
git add <explicit-file-1> <explicit-file-2>
git diff --cached --stat
git diff --cached
git commit -m "fix(loops): satisfy loop closure verification"
```

---

## Task 12: Final Handoff Checklist For Claude Code

Before reporting complete, Claude Code must provide:

- List of commits created, in order.
- List of files changed.
- Exact commands run and pass/fail status.
- Confirmation that no registry JSON or production manifest was directly edited.
- Confirmation that no real trade path was added.
- Confirmation that alpha validity remains delegated to existing deterministic gates.
- Any remaining follow-up tasks added to `TASKS.md`.

The final response must not say “complete” unless `bash scripts/test_all.sh` has passed or the exact blocker is documented with command output.

---

## Scope Extensions After MVP

These are not part of the first implementation unless the user explicitly asks to continue:

- Replace dry-run plumbing seed with a bounded real candidate source from `services/actions/autoresearch_search.py`.
- Add weekly mode that runs bounded hypothesis generation, L0/L1 only, and review queue output.
- Add Web page or panel for Loop OS status.
- Add production-monitoring feedback from `paper_trade`, decay monitor, and signal-vs-realized drift into Memory Loop.
- Add a policy-backed approval UI for holdout validation and promote actions.
- Add loop event compaction/read model for long-running operations.
