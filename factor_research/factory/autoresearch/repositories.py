"""Append-only repositories for Auto Factor Research artifacts."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterator

from .models import Candidate, CandidateDecision, CandidateEvaluationResult, CandidateStatus


DEFAULT_ROOT = Path(__file__).resolve().parents[2] / "data_lake" / "factory" / "autoresearch"
DEFAULT_CANDIDATE_PATH = DEFAULT_ROOT / "candidates.jsonl"
DEFAULT_EXPERIMENT_PATH = DEFAULT_ROOT / "experiment_log.jsonl"
DEFAULT_REVIEW_PATH = DEFAULT_ROOT / "review_queue.jsonl"


def _json_ready(value):
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {k: _json_ready(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_ready(v) for v in value]
    return value


class CandidateRepository:
    """JSONL candidate store. Same fingerprint is treated as duplicate."""

    def __init__(self, path: Path = DEFAULT_CANDIDATE_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._cache: dict[str, Candidate] = {}
        self._load()

    def add(self, candidate: Candidate) -> bool:
        if candidate.fingerprint in self._cache:
            return False
        self._append(candidate)
        return True

    def record(self, candidate: Candidate) -> None:
        self._append(candidate)

    def get(self, fingerprint: str) -> Candidate | None:
        return self._cache.get(fingerprint)

    def all(self) -> list[Candidate]:
        return list(self._cache.values())

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    candidate = self._deserialize(json.loads(line))
                    self._cache[candidate.fingerprint] = candidate

    def _append(self, candidate: Candidate) -> None:
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(_json_ready(asdict(candidate)), ensure_ascii=False) + "\n")
        self._cache[candidate.fingerprint] = candidate

    @staticmethod
    def _deserialize(rec: dict) -> Candidate:
        return Candidate(
            fingerprint=rec["fingerprint"],
            ast=rec["ast"],
            status=CandidateStatus(rec.get("status", "generated")),
            source=rec.get("source", "agent"),
            created_at=rec.get("created_at", ""),
            notes=rec.get("notes", ""),
        )


class ExperimentLog:
    """Append-only evaluation log."""

    def __init__(self, path: Path = DEFAULT_EXPERIMENT_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, result: CandidateEvaluationResult) -> None:
        rec = _json_ready(asdict(result))
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def iter_all(self) -> Iterator[CandidateEvaluationResult]:
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                yield CandidateEvaluationResult(
                    fingerprint=rec["fingerprint"],
                    status=CandidateStatus(rec["status"]),
                    decision=CandidateDecision(rec["decision"]),
                    metrics=rec.get("metrics", {}),
                    reason=rec.get("reason", ""),
                )


class ReviewQueue:
    """Human review queue. Promotion stops here; it never writes registry."""

    def __init__(self, path: Path = DEFAULT_REVIEW_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._items: dict[str, dict] = {}
        self._load()

    def add(self, candidate: Candidate, result: CandidateEvaluationResult) -> bool:
        if candidate.fingerprint in self._items:
            return False
        rec = {
            "fingerprint": candidate.fingerprint,
            "status": candidate.status.value,
            "candidate": candidate.ast,
            "decision": result.decision.value,
            "reason": result.reason,
            "metrics": result.metrics,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._items[candidate.fingerprint] = rec
        return True

    def all(self) -> list[dict]:
        return list(self._items.values())

    def get(self, fingerprint: str) -> dict | None:
        return self._items.get(fingerprint)

    def pending(self) -> list[dict]:
        return [r for r in self._items.values() if r.get("status") == CandidateStatus.PROMOTED_TO_REVIEW.value]

    def record_decision(
        self,
        fingerprint: str,
        status: CandidateStatus,
        *,
        action: str,
        notes: str = "",
        reviewed_at: str = "",
    ) -> dict:
        """Append a human review decision. Latest record per fingerprint wins on load."""
        rec = dict(self._items[fingerprint])
        rec.update(
            {
                "status": status.value,
                "review_action": action,
                "reviewer_notes": notes,
                "reviewed_at": reviewed_at,
            }
        )
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._items[fingerprint] = rec
        return rec

    def _load(self) -> None:
        if not self.path.exists():
            return
        with self.path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    self._items[rec["fingerprint"]] = rec
