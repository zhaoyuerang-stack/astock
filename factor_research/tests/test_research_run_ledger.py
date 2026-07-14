"""Tests for unified research-run archival.

Run: cd /Users/kiki/astcok/factor_research && python3 tests/test_research_run_ledger.py
"""
from __future__ import annotations

import json
import multiprocessing
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


def _tmp_path(name: str) -> Path:
    return Path(tempfile.mkdtemp()) / name


def _append_research_runs(path: str, worker: int, count: int, start_event) -> None:
    from research_ledger.ledger import ResearchLedger, ResearchRunRecord

    ledger = ResearchLedger(path=path)
    if not start_event.wait(timeout=10):
        raise RuntimeError("timed out waiting for concurrent ledger start")
    for index in range(count):
        ledger.log_research_run(ResearchRunRecord(
            script="tests/concurrent_research_ledger.py",
            hypothesis=f"worker-{worker}/run-{index}",
            data_vintage={},
            metrics={"worker": worker, "index": index},
            verdict="PENDING_REVIEW",
            artifact_paths=[],
            next_action="HUMAN_REVIEW",
            source="test",
            run_at=f"2026-07-11T00:{worker:02d}:{index:02d}",
        ))


def test_default_ledger_path_is_forbidden_under_pytest():
    import pytest
    from research_ledger.ledger import ResearchLedger

    with pytest.raises(RuntimeError, match="temporary ResearchLedger"):
        ResearchLedger()


def test_record_research_run_appends_hash_chain_and_index():
    from research_ledger.ledger import (
        ResearchLedger,
        ResearchRunRecord,
        load_research_run_index,
        record_research_run,
    )

    ledger = ResearchLedger(path=_tmp_path("research_ledger.jsonl"))
    index_path = _tmp_path("index.json")
    record = ResearchRunRecord(
        script="scripts/research/run_nine_gates_all.py",
        hypothesis="illiquidity/v3.1",
        data_vintage={"fingerprint": "abc123", "last_date": "2026-06-18"},
        metrics={"dsr_p": 0.01, "psr": 0.99, "n_trials": 4},
        verdict="PASS",
        artifact_paths=["reports/research/illiquidity_9_gates_report.md"],
        next_action="PROMOTE_REVIEW",
        source="nine_gate",
        run_at="2026-06-18T12:00:00",
    )

    out = record_research_run(record, ledger=ledger, index_path=index_path)

    ok, problems = ledger.verify_chain()
    assert ok, problems
    runs = ledger.list_research_runs()
    assert len(runs) == 1
    assert runs[0].script == "scripts/research/run_nine_gates_all.py"
    assert out["decision_state"] == "promote"
    assert len(out["entry_hash"]) == 64

    index = load_research_run_index(index_path)
    assert index["summary"]["total_runs"] == 1
    assert index["summary"]["counts_by_decision"]["promote"] == 1
    assert index["latest_runs"][0]["hypothesis"] == "illiquidity/v3.1"


def test_research_run_index_classifies_decision_states():
    from research_ledger.ledger import ResearchLedger, ResearchRunRecord, load_research_run_index, record_research_run

    ledger = ResearchLedger(path=_tmp_path("research_ledger.jsonl"))
    index_path = _tmp_path("index.json")
    cases = [
        ("REFUTED", "SKIP", "refuted"),
        ("PENDING_REVIEW", "HUMAN_REVIEW", "pending_review"),
        ("SHADOW", "KEEP_SHADOW", "shadow"),
        ("PASS", "PROMOTE_REVIEW", "promote"),
    ]
    for i, (verdict, next_action, expected) in enumerate(cases):
        out = record_research_run(
            ResearchRunRecord(
                script=f"scripts/research/run_{i}.py",
                hypothesis=f"H{i}",
                data_vintage={},
                metrics={},
                verdict=verdict,
                artifact_paths=[],
                next_action=next_action,
                run_at=f"2026-06-18T12:0{i}:00",
            ),
            ledger=ledger,
            index_path=index_path,
        )
        assert out["decision_state"] == expected

    index = load_research_run_index(index_path)
    assert index["summary"]["counts_by_decision"] == {
        "promote": 1,
        "shadow": 1,
        "pending_review": 1,
        "refuted": 1,
    }
    assert [r["hypothesis"] for r in index["latest_runs"]] == ["H3", "H2", "H1", "H0"]
    assert json.loads(index_path.read_text(encoding="utf-8"))["summary"]["total_runs"] == 4


def test_priority_research_entrypoints_record_runs():
    from research_ledger.ledger import ResearchLedger, load_research_run_index
    from scripts.research.run_nine_gates_all import record_nine_gate_research_run
    from scripts.research.report_nlp_pipeline import record_report_nlp_research_run
    from scripts.research.incubation_policy import record_incubation_policy_research_run

    ledger = ResearchLedger(path=_tmp_path("research_ledger.jsonl"))
    index_path = _tmp_path("index.json")

    record_nine_gate_research_run(
        strategy_name="illiquidity",
        version="v3.1",
        summary={"dsr_p": 0.01, "gate4_verdict": "PASS", "n_trials": 4},
        report_path=Path("reports/research/illiquidity_9_gates_report.md"),
        ledger=ledger,
        index_path=index_path,
    )
    record_report_nlp_research_run(
        stats={"scanned": 2, "processed": 1, "skipped": 0, "failed": 1},
        demo_mode=False,
        artifact_paths=["data_lake/research_signals/logic_chains/x.json"],
        ledger=ledger,
        index_path=index_path,
    )
    record_incubation_policy_research_run(
        strategy_family="ontology_industry",
        version="v1.0-shadow",
        artifact_paths=["data_lake/agent/shadow_incubation_log.json"],
        ledger=ledger,
        index_path=index_path,
    )

    ok, problems = ledger.verify_chain()
    assert ok, problems
    index = load_research_run_index(index_path)
    assert index["summary"]["total_runs"] == 3
    decisions = index["summary"]["counts_by_decision"]
    assert decisions["promote"] == 1
    assert decisions["pending_review"] == 1
    assert decisions["shadow"] == 1


def test_concurrent_research_run_appends_preserve_one_hash_chain(tmp_path):
    from research_ledger.ledger import ResearchLedger

    ledger_path = tmp_path / "research_ledger.jsonl"
    context = multiprocessing.get_context("spawn")
    start_event = context.Event()
    processes = [
        context.Process(
            target=_append_research_runs,
            args=(str(ledger_path), worker, 6, start_event),
        )
        for worker in range(4)
    ]
    try:
        for process in processes:
            process.start()
        start_event.set()
        for process in processes:
            process.join(timeout=30)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)

    assert [process.exitcode for process in processes] == [0, 0, 0, 0]
    ledger = ResearchLedger(path=ledger_path)
    ok, problems = ledger.verify_chain()
    assert ok, problems
    assert len(ledger.list_research_runs()) == 24


def test_tampered_research_ledger_refuses_new_append(tmp_path):
    import pytest
    from research_ledger.ledger import ResearchLedger, ResearchRunRecord

    ledger_path = tmp_path / "research_ledger.jsonl"
    ledger = ResearchLedger(path=ledger_path)
    record = ResearchRunRecord(
        script="tests/tamper.py", hypothesis="H", data_vintage={}, metrics={"x": 1},
        verdict="PENDING_REVIEW", artifact_paths=[], next_action="HUMAN_REVIEW",
        source="test", run_at="2026-07-11T00:00:00",
    )
    ledger.log_research_run(record)
    tampered = json.loads(ledger_path.read_text(encoding="utf-8"))
    tampered["metrics"] = {"x": 999}
    ledger_path.write_text(json.dumps(tampered) + "\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="refusing to append"):
        ledger.log_research_run(ResearchRunRecord(
            script="tests/tamper.py", hypothesis="H2", data_vintage={}, metrics={},
            verdict="PENDING_REVIEW", artifact_paths=[], next_action="HUMAN_REVIEW",
            source="test", run_at="2026-07-11T00:00:01",
        ))


if __name__ == "__main__":
    print("Running research run ledger tests...\n")
    test_record_research_run_appends_hash_chain_and_index()
    print("✅ research run appends to hash-chain ledger and index")
    test_research_run_index_classifies_decision_states()
    print("✅ research run index classifies decision states")
    test_priority_research_entrypoints_record_runs()
    print("✅ priority research entrypoints record runs")
    print("\n🎉 Research run ledger tests passed!")
