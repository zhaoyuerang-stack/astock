"""Research Ledger for Immutable Experiment Logging.

Records all experiment attempts, successful or failed, to guard against p-hacking
and preserve research histories.
"""
from __future__ import annotations

import json
import hashlib
import fcntl
import os
import threading
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

DEFAULT_LEDGER_PATH = (
    Path(__file__).resolve().parent.parent
    / "data_lake" / "governance" / "research_ledger.jsonl"
)
DEFAULT_RESEARCH_RUN_INDEX_PATH = (
    Path(__file__).resolve().parent.parent
    / "reports" / "research_ledger" / "index.json"
)

_PROCESS_LEDGER_WRITE_LOCK = threading.RLock()

@dataclass
class LedgerEntry:
    experiment_id: str
    parent_experiment_id: Optional[str]
    hypothesis_text: str
    llm_prompt_hash: Optional[str]
    factor_ast_hash: str
    code_commit_hash: str
    data_snapshot_hash: str
    universe_version: str
    cost_model_version: str
    random_seed: int
    tried_parameters: Dict[str, Any]
    result_metrics: Dict[str, Any]
    rejection_reason: Optional[str]
    reviewer: str
    run_at: str
    notes: str = ""
    prev_hash: str = ""      # 前一条的 entry_hash（hash chain 链接）
    entry_hash: str = ""     # 本条内容哈希 = sha256(prev_hash + canonical(payload))

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> LedgerEntry:
        # 容忍未来新增字段：只取本 dataclass 已声明的键，避免旧/新行互不兼容时炸
        fields = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in fields})


@dataclass
class ResearchRunRecord:
    """Machine-readable summary for one research script run.

    This is appended to the same hash-chain ledger as experiments, with
    ``record_type=research_run``. The JSON index under reports/ is derived from
    these rows and can be rebuilt at any time.
    """

    script: str
    hypothesis: str
    data_vintage: Dict[str, Any]
    metrics: Dict[str, Any]
    verdict: str
    artifact_paths: List[str]
    next_action: str
    source: str = ""
    run_at: str = ""
    notes: str = ""
    record_type: str = "research_run"
    run_id: str = ""

    def to_dict(self) -> dict:
        rec = asdict(self)
        if not rec.get("run_at"):
            rec["run_at"] = datetime.now().isoformat(timespec="seconds")
        if not rec.get("run_id"):
            payload = json.dumps(
                {
                    "script": rec.get("script", ""),
                    "hypothesis": rec.get("hypothesis", ""),
                    "run_at": rec.get("run_at", ""),
                    "source": rec.get("source", ""),
                },
                sort_keys=True,
                ensure_ascii=False,
            )
            rec["run_id"] = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
        return rec

    @classmethod
    def from_dict(cls, data: dict) -> ResearchRunRecord:
        fields = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in fields})


def _payload_hash(rec: dict) -> str:
    """对除链字段外的内容做确定性哈希（防篡改的内容指纹）。"""
    payload = {k: v for k, v in rec.items() if k not in ("prev_hash", "entry_hash")}
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _chain_hash(prev_hash: str, rec: dict) -> str:
    """链式哈希：把前一条 entry_hash 编织进本条，任何历史记录被改都会断链。"""
    return hashlib.sha256((prev_hash + _payload_hash(rec)).encode("utf-8")).hexdigest()


class ResearchLedger:
    """Immutable ledger logging all factor search and testing experiments."""

    def __init__(self, path: Path | str | None = None):
        if path is None and os.environ.get("PYTEST_CURRENT_TEST"):
            raise RuntimeError(
                "tests must inject a temporary ResearchLedger path; refusing to write the canonical lake"
            )
        self.path = Path(path) if path is not None else DEFAULT_LEDGER_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _write_transaction(self):
        """Serialize the tail-read + append operation across processes."""
        lock_path = self.path.with_name(f".{self.path.name}.lock")
        with _PROCESS_LEDGER_WRITE_LOCK:
            with lock_path.open("a+b") as lock_file:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _last_hash(self) -> str:
        """Read and verify the whole chain before accepting a new tail.

        Appending behind malformed, legacy, or tampered history would make the
        new record look legitimate while preserving a broken prefix.  Fail
        closed and require an explicit migration/repair instead.
        """
        last = ""
        if not self.path.exists():
            return last
        with open(self.path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        f"research ledger line {lineno} is invalid JSON; refusing to append"
                    ) from exc
                entry_hash = str(rec.get("entry_hash") or "")
                if not entry_hash:
                    raise RuntimeError(
                        "research ledger contains unhashed legacy rows; "
                        "run migrate_chain before appending"
                    )
                if rec.get("prev_hash", "") != last:
                    raise RuntimeError(
                        f"research ledger chain breaks at line {lineno}; refusing to append"
                    )
                if _chain_hash(last, rec) != entry_hash:
                    raise RuntimeError(
                        f"research ledger content hash fails at line {lineno}; refusing to append"
                    )
                last = entry_hash
        return last

    def _append_record(self, rec: dict) -> dict:
        with self._write_transaction():
            rec["prev_hash"] = self._last_hash()
            rec["entry_hash"] = _chain_hash(rec["prev_hash"], rec)
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
                f.flush()
                os.fsync(f.fileno())
        return rec

    def log_experiment(self, entry: LedgerEntry) -> None:
        """Append a new experiment entry to the ledger（链式哈希，防 p-hacking 事后篡改）。"""
        self._append_record(entry.to_dict())

    def log_research_run(self, record: ResearchRunRecord) -> dict:
        """Append one research script run to the immutable ledger."""
        return self._append_record(record.to_dict())

    def verify_chain(self) -> tuple[bool, list[str]]:
        """校验 hash 链完整性：内容篡改 → entry_hash 不匹配；删/插行 → prev_hash 断链。

        返回 (ok, problems)。兼容旧格式：无 entry_hash 的遗留行跳过校验但记一笔提示。
        """
        problems: list[str] = []
        prev = ""
        legacy = 0
        if not self.path.exists():
            return True, problems
        with open(self.path, "r", encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    problems.append(f"line {i}: JSON 解析失败")
                    continue
                if not rec.get("entry_hash"):
                    legacy += 1
                    continue
                if _chain_hash(rec.get("prev_hash", ""), rec) != rec["entry_hash"]:
                    problems.append(f"line {i} ({rec.get('experiment_id')}): entry_hash 不匹配，内容被篡改")
                elif prev and rec.get("prev_hash", "") != prev:
                    problems.append(f"line {i} ({rec.get('experiment_id')}): prev_hash 断链（疑插入/删除）")
                prev = rec["entry_hash"]
        if legacy:
            problems.append(f"提示：{legacy} 条遗留行无 hash（建议运行 migrate_chain 回填）")
        return (not any("篡改" in p or "断链" in p or "解析失败" in p for p in problems)), problems

    def migrate_chain(self) -> int:
        """一次性把全部历史行回填为 hash 链（内容不变，仅补 prev_hash/entry_hash）。

        使存量审计历史变为可验。返回回填的行数。
        """
        if not self.path.exists():
            return 0
        recs = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    recs.append(json.loads(line))
        prev = ""
        for rec in recs:
            rec.pop("entry_hash", None)
            rec.pop("prev_hash", None)
            rec["prev_hash"] = prev
            rec["entry_hash"] = _chain_hash(prev, rec)
            prev = rec["entry_hash"]
        tmp = self.path.with_suffix(".jsonl.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for rec in recs:
                f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
        tmp.replace(self.path)
        return len(recs)

    def iter_all(self) -> Iterator[LedgerEntry]:
        """Iterate through all ledger entries."""
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield LedgerEntry.from_dict(json.loads(line))
                except Exception:
                    pass

    def list_all(self) -> List[LedgerEntry]:
        return list(self.iter_all())

    def iter_research_runs(self) -> Iterator[ResearchRunRecord]:
        """Iterate only ``record_type=research_run`` rows."""
        if not self.path.exists():
            return
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    if rec.get("record_type") == "research_run":
                        yield ResearchRunRecord.from_dict(rec)
                except Exception:
                    continue

    def list_research_runs(self) -> List[ResearchRunRecord]:
        return list(self.iter_research_runs())

    def get_by_id(self, experiment_id: str) -> Optional[LedgerEntry]:
        for entry in self.iter_all():
            if entry.experiment_id == experiment_id:
                return entry
        return None


def calculate_ast_hash(ast_dict: dict) -> str:
    """Generate deterministic hash for a factor AST to verify uniqueness."""
    serialized = json.dumps(ast_dict, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def classify_research_decision(verdict: str, next_action: str) -> str:
    """Map raw script verdict/action onto UI decision buckets."""
    v = str(verdict or "").upper()
    a = str(next_action or "").upper()
    if v in {"REFUTED", "FAILED", "FAIL", "REJECTED"} or a in {"SKIP", "DEPRIORITIZE", "RETIRE_REVIEW"}:
        return "refuted"
    if v in {"PENDING_REVIEW", "REVIEW"} or a in {"REVIEW", "HUMAN_REVIEW", "PENDING_REVIEW"}:
        return "pending_review"
    if v == "SHADOW" or a in {"SHADOW", "KEEP_SHADOW"}:
        return "shadow"
    if v in {"PROMOTE_CANDIDATE", "PROMOTABLE"} or a in {"PROMOTE", "PROMOTE_REVIEW"}:
        return "promote"
    return "informational"


def _run_view(record: ResearchRunRecord) -> dict:
    rec = record.to_dict()
    return {
        "run_id": rec.get("run_id", ""),
        "script": rec.get("script", ""),
        "hypothesis": rec.get("hypothesis", ""),
        "source": rec.get("source", ""),
        "run_at": rec.get("run_at", ""),
        "data_vintage": rec.get("data_vintage", {}) or {},
        "metrics": rec.get("metrics", {}) or {},
        "verdict": rec.get("verdict", ""),
        "next_action": rec.get("next_action", ""),
        "decision_state": classify_research_decision(rec.get("verdict", ""), rec.get("next_action", "")),
        "artifact_paths": rec.get("artifact_paths", []) or [],
        "notes": rec.get("notes", ""),
    }


def build_research_run_index(ledger: ResearchLedger | None = None, *, limit: int = 100) -> dict:
    """Build a read-optimized index from hash-chain research run records."""
    ledger = ledger or ResearchLedger()
    rows = [_run_view(r) for r in ledger.list_research_runs()]
    rows.sort(key=lambda r: r.get("run_at", ""), reverse=True)
    counts_by_decision: dict[str, int] = {}
    counts_by_verdict: dict[str, int] = {}
    counts_by_next_action: dict[str, int] = {}
    for row in rows:
        counts_by_decision[row["decision_state"]] = counts_by_decision.get(row["decision_state"], 0) + 1
        verdict = row.get("verdict", "")
        action = row.get("next_action", "")
        counts_by_verdict[verdict] = counts_by_verdict.get(verdict, 0) + 1
        counts_by_next_action[action] = counts_by_next_action.get(action, 0) + 1
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "total_runs": len(rows),
            "counts_by_decision": counts_by_decision,
            "counts_by_verdict": counts_by_verdict,
            "counts_by_next_action": counts_by_next_action,
        },
        "latest_runs": rows[:limit],
    }


def write_research_run_index(
    ledger: ResearchLedger | None = None,
    path: Path | str = DEFAULT_RESEARCH_RUN_INDEX_PATH,
    *,
    limit: int = 100,
) -> dict:
    index = build_research_run_index(ledger=ledger, limit=limit)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(index, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    return index


def load_research_run_index(path: Path | str = DEFAULT_RESEARCH_RUN_INDEX_PATH) -> dict:
    p = Path(path)
    if not p.exists():
        return write_research_run_index(path=p)
    return json.loads(p.read_text(encoding="utf-8"))


def record_research_run(
    record: ResearchRunRecord,
    *,
    ledger: ResearchLedger | None = None,
    index_path: Path | str | None = DEFAULT_RESEARCH_RUN_INDEX_PATH,
) -> dict:
    """Append a research run and refresh the read index."""
    ledger = ledger or ResearchLedger()
    appended = ledger.log_research_run(record)
    if index_path is None:
        index_path = DEFAULT_RESEARCH_RUN_INDEX_PATH
    write_research_run_index(ledger=ledger, path=index_path)
    view = _run_view(ResearchRunRecord.from_dict(appended))
    # The immutable entry identity is required to bind downstream registry
    # evidence to this exact hash-chain record.  It is intentionally returned
    # to the caller but remains absent from the lossy UI index.
    view["entry_hash"] = appended.get("entry_hash", "")
    view["prev_hash"] = appended.get("prev_hash", "")
    return view
