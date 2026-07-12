"""历史「候选」无 dsr_p 必须打 nine_gate_audit 标签(审计:默认 promote 不跑 9-Gate 遗留)。"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import strategy_registry as reg
from scripts.ci.check_registry_evidence import (
    extract_versions,
    find_candidate_missing_dsr_unflagged,
)


def _tmp_registry(monkeypatch, payload: dict):
    path = Path(tempfile.mktemp(suffix=".json"))
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    monkeypatch.setattr(reg, "REGISTRY", path)
    return path


def _ledger_with_candidates():
    return {
        "families": [
            {
                "id": "fam-empty",
                "name": "empty ng",
                "status": "active",
                "versions": [{
                    "version": "v1.0",
                    "status": "候选",
                    "desc": "x",
                    "config": {},
                    "data_scope": {},
                    "metrics": {"annual": 0.1, "maxdd": -0.1},
                    "notes": "no audit",
                    "evidence": {},
                    "admission": {},
                    "nine_gate": {},
                }],
            },
            {
                "id": "fam-stub",
                "name": "wf stub",
                "status": "active",
                "versions": [{
                    "version": "v1.0",
                    "status": "候选",
                    "desc": "x",
                    "config": {},
                    "data_scope": {},
                    "metrics": {},
                    "notes": "wf only",
                    "evidence": {},
                    "admission": {},
                    "nine_gate": {"wf_sharpe": 1.2, "wf_verdict": "PASS"},
                }],
            },
            {
                "id": "fam-shadow",
                "name": "shadow",
                "status": "active",
                "versions": [{
                    "version": "v1.0-shadow",
                    "status": "候选",
                    "desc": "x",
                    "config": {},
                    "data_scope": {},
                    "metrics": {},
                    "notes": "观察版本：不得参与生产组合",
                    "evidence": {},
                    "admission": {},
                    "nine_gate": {},
                }],
            },
            {
                "id": "fam-ok",
                "name": "has dsr",
                "status": "active",
                "versions": [{
                    "version": "v1.0",
                    "status": "候选",
                    "desc": "x",
                    "config": {},
                    "data_scope": {},
                    "metrics": {},
                    "notes": "",
                    "evidence": {},
                    "admission": {},
                    "nine_gate": {"dsr_p": 0.2, "passed_all": False},
                }],
            },
        ]
    }


def test_classify_nine_gate_payload():
    assert reg.classify_nine_gate_payload({}) == "EMPTY"
    assert reg.classify_nine_gate_payload({"wf_sharpe": 1.0}) == "STUB_NO_DSR"
    assert reg.classify_nine_gate_payload({"dsr_p": 0.1}) == "COMPLETE"


def test_guard_flags_unflagged_candidates():
    rows = extract_versions(_ledger_with_candidates())
    v = find_candidate_missing_dsr_unflagged(rows)
    keys = {k for k, _ in v}
    assert "G6-cand-no-dsr:fam-empty/v1.0" in keys
    assert "G6-cand-no-dsr:fam-stub/v1.0" in keys
    assert "G6-cand-no-dsr:fam-shadow/v1.0-shadow" in keys
    assert not any("fam-ok" in k for k in keys)


def test_flag_candidates_missing_dsr_idempotent(monkeypatch):
    path = _tmp_registry(monkeypatch, _ledger_with_candidates())
    try:
        t1 = reg.flag_candidates_missing_dsr(apply=True, date_str="2026-07-12")
        assert len(t1) == 3
        by_id = {x["id"]: x for x in t1}
        assert by_id["fam-empty/v1.0"]["status"] == "PENDING"
        assert by_id["fam-empty/v1.0"]["classification"] == "EMPTY"
        assert by_id["fam-stub/v1.0"]["classification"] == "STUB_NO_DSR"
        assert by_id["fam-shadow/v1.0-shadow"]["status"] == "EXEMPT_SHADOW"

        data = json.loads(path.read_text(encoding="utf-8"))
        rows = extract_versions(data)
        assert find_candidate_missing_dsr_unflagged(rows) == []

        t2 = reg.flag_candidates_missing_dsr(apply=True, date_str="2026-07-12")
        assert t2 == []  # 幂等
    finally:
        path.unlink(missing_ok=True)


def test_attach_nine_gate_clears_pending(monkeypatch):
    path = _tmp_registry(monkeypatch, _ledger_with_candidates())
    try:
        reg.flag_candidates_missing_dsr(apply=True, date_str="2026-07-12")
        reg.attach_nine_gate(
            "fam-empty", "v1.0",
            {"dsr_p": 0.03, "passed_all": False, "status": "PERSISTED"},
        )
        data = json.loads(path.read_text(encoding="utf-8"))
        v = data["families"][0]["versions"][0]
        assert v["nine_gate"]["dsr_p"] == 0.03
        assert v["evidence"]["nine_gate_audit"]["status"] == "COMPLETE"
    finally:
        path.unlink(missing_ok=True)


def test_adversarial_stub_wf_not_counts_as_complete():
    """对抗: 仅有 wf_* 不得被当成 COMPLETE。"""
    assert reg.classify_nine_gate_payload({
        "wf_sharpe": 1.5, "wf_annual": 0.2, "wf_verdict": "PASS",
    }) == "STUB_NO_DSR"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
