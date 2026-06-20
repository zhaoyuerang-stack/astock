"""check_registry_evidence 守卫的 fixture 测试(检测器吃 dict,不依赖实时台账状态)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.ci.check_registry_evidence import (
    extract_versions, find_cross_family_ic_copies, find_standalone_evidence_gaps, check,
)

IC_A = {"ic_mean": 0.078, "nw_icir": 0.126, "ic_decay": {"1": 0.02}}
IC_B = {"ic_mean": 0.041, "nw_icir": 0.21, "ic_decay": {"1": 0.01}}


def _ledger(families):
    return {"families": families}


def test_cross_family_ic_copy_flagged():
    # 两个不同 family 共享逐位相同 IC 块 → G1 违规
    led = _ledger([
        {"id": "famA", "status": "在册", "versions": [
            {"version": "v1.0", "admission": {"track": "standalone"}, "nine_gate": dict(IC_A, passed_all=True, dsr_p=0.01, pbo=0.2)}]},
        {"id": "famB", "status": "在册", "versions": [
            {"version": "v1.0", "admission": {"track": "standalone"}, "nine_gate": dict(IC_A, passed_all=True, dsr_p=0.01, pbo=0.3)}]},
    ])
    rows = extract_versions(led)
    v = find_cross_family_ic_copies(rows)
    assert len(v) == 1 and "famA" in v[0][1] and "famB" in v[0][1]


def test_within_family_shared_ic_allowed():
    # 同 family 多版本共享 IC 块 → 合法,不报
    led = _ledger([
        {"id": "famA", "status": "在册", "versions": [
            {"version": "v1.0", "admission": {"track": "standalone"}, "nine_gate": dict(IC_A, dsr_p=0.01, pbo=0.2)},
            {"version": "v1.1", "admission": {"track": "standalone"}, "nine_gate": dict(IC_A, dsr_p=0.02, pbo=0.2)}]},
    ])
    assert find_cross_family_ic_copies(extract_versions(led)) == []


def test_empty_evidence_standalone_flagged():
    # active+standalone 但 nine_gate/evidence 皆空 → G2 违规(industry-neglect v1.3 型)
    led = _ledger([
        {"id": "famC", "status": "在册", "versions": [
            {"version": "v1.3", "admission": {"track": "standalone"}, "nine_gate": {}, "evidence": {}}]},
    ])
    v = find_standalone_evidence_gaps(extract_versions(led))
    assert len(v) == 1 and "证据全空" in v[0][1]


def test_passed_all_with_skipped_gate_flagged():
    # passed_all=true 但 pbo=None → G2 跳门违规(illiquidity-large-cap 型)
    led = _ledger([
        {"id": "famD", "status": "在册", "versions": [
            {"version": "v1.0", "admission": {"track": "standalone"},
             "nine_gate": dict(IC_B, passed_all=True, dsr_p=0.01, pbo=None)}]},
    ])
    v = find_standalone_evidence_gaps(extract_versions(led))
    assert len(v) == 1 and "pbo" in v[0][1]


def test_clean_ledger_passes():
    led = _ledger([
        {"id": "famE", "status": "在册", "versions": [
            {"version": "v1.0", "admission": {"track": "standalone"},
             "nine_gate": dict(IC_B, passed_all=True, dsr_p=0.01, pbo=0.2)}]},
        {"id": "famF", "status": "候选", "versions": [  # 候选无证据 → 不要求,不报
            {"version": "v1.0", "admission": {"track": None}, "nine_gate": {}}]},
    ])
    assert check(led) == 0


def test_new_violation_returns_nonzero():
    # 不在 PENDING_REMEDIATION 基线里的新违规 → check 必须 exit 1(守卫的核心职责)
    led = _ledger([
        {"id": "newFamX", "status": "在册", "versions": [
            {"version": "v1.0", "admission": {"track": "standalone"}, "nine_gate": {}, "evidence": {}}]},
    ])
    assert check(led) == 1


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-q"]))
