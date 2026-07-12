"""check_registry_evidence 守卫的 fixture 测试(检测器吃 dict,不依赖实时台账状态)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research_ledger.receipts import diversifier_admission_with_receipt
from scripts.ci.check_registry_evidence import (
    _record_entry_hash,
    _record_run_id,
    build_nine_gate_receipt,
    extract_versions,
    find_cross_family_ic_copies,
    find_diversifier_receipt_gaps,
    find_nine_gate_receipt_gaps,
    find_standalone_evidence_gaps,
    research_chain_problems,
    check,
)

IC_A = {"ic_mean": 0.078, "nw_icir": 0.126, "ic_decay": {"1": 0.02}}
IC_B = {"ic_mean": 0.041, "nw_icir": 0.21, "ic_decay": {"1": 0.01}}
IC_RICH = {
    "ic_mean": 0.078,
    "nw_icir": 0.126,
    "neut_nw_icir": 0.119,
    "icir_retention": 0.944,
    "monotonicity_corr": 0.91,
    "ic_win_rate": 0.58,
    "ic_decay": {"1": 0.0201, "5": 0.0178, "20": 0.0104},
}


def _ledger(families):
    return {"families": families}


def _active_standalone(family="famE", version="v1.0", *, nine_gate=None, evidence=None):
    ng = nine_gate or dict(IC_RICH, passed_all=True, dsr_p=0.01, pbo=0.2)
    if evidence is None:
        evidence = {
            "nine_gate_receipt": build_nine_gate_receipt(
                family, version, ng, run_id="a" * 16, entry_hash="b" * 64,
            )
        }
    return {
        "id": family,
        "status": "在册",
        "versions": [{
            "version": version,
            "admission": {"track": "standalone"},
            "nine_gate": ng,
            "evidence": evidence,
        }],
    }


def _research_record(family="famE", version="v1.0", *, nine_gate=None, run_at="2026-07-10T12:00:00"):
    ng = nine_gate or dict(IC_RICH, passed_all=True, dsr_p=0.01, pbo=0.2)
    record = {
        "record_type": "research_run",
        "script": "scripts/research/run_nine_gates_all.py",
        "hypothesis": f"{family}/{version}",
        "source": "nine_gate",
        "metrics": ng,
        "run_at": run_at,
        "prev_hash": "",
    }
    record["run_id"] = _record_run_id(record)
    record["entry_hash"] = _record_entry_hash(record)
    return record


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


def test_cross_family_single_decimal_perturbation_still_flagged():
    # 逐位 hash 的老绕法：照抄整块后仅改最后一位小数。结构相同且其余值逐位一致，应命中 G1-near。
    perturbed = dict(IC_RICH)
    perturbed["ic_mean"] = 0.0781
    led = _ledger([
        {"id": "famA", "versions": [{"version": "v1", "nine_gate": IC_RICH}]},
        {"id": "famB", "versions": [{"version": "v1", "nine_gate": perturbed}]},
    ])
    violations = find_cross_family_ic_copies(extract_versions(led))
    assert any(key.startswith("G1-near:") and "近似复制" in msg for key, msg in violations)


def test_independently_different_ic_blocks_not_false_positive():
    independent = dict(IC_RICH)
    independent.update({
        "ic_mean": 0.052,
        "nw_icir": 0.31,
        "neut_nw_icir": 0.25,
        "icir_retention": 0.81,
        "monotonicity_corr": 0.72,
        "ic_win_rate": 0.54,
        "ic_decay": {"1": 0.014, "5": 0.009, "20": 0.002},
    })
    led = _ledger([
        {"id": "famA", "versions": [{"version": "v1", "nine_gate": IC_RICH}]},
        {"id": "famB", "versions": [{"version": "v1", "nine_gate": independent}]},
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


def test_dsr_insignificant_standalone_flagged():
    # active+standalone 但 dsr_p>=0.05 → G3 违规(ADR-020:DSR 多重测试惩罚下不显著)
    led = _ledger([
        {"id": "famG", "status": "在册", "versions": [
            {"version": "v1.0", "admission": {"track": "standalone"},
             "nine_gate": dict(IC_B, dsr_p=0.34)}]},
    ])
    v = find_standalone_evidence_gaps(extract_versions(led))
    assert len(v) == 1 and "DSR不显著" in v[0][1] and v[0][0].startswith("G3-dsr-fail")


def test_dsr_none_standalone_flagged():
    # active+standalone,nine_gate 非空(非 G2-empty)但 dsr_p 缺算 → G3 违规(industry-neglect v1.3 型)
    led = _ledger([
        {"id": "famH", "status": "在册", "versions": [
            {"version": "v1.3", "admission": {"track": "standalone"},
             "nine_gate": dict(IC_B)}]},  # 无 dsr_p
    ])
    v = find_standalone_evidence_gaps(extract_versions(led))
    assert len(v) == 1 and "DSR未实算" in v[0][1] and v[0][0].startswith("G3-dsr-none")


def test_dsr_insignificant_diversifier_not_flagged():
    # diversifier 凭组合边际入册,不受 DSR 约束 → 即便 dsr_p=0.9 也不报 G3
    adm = diversifier_admission_with_receipt(
        "famI", "v1.0", rationale="负相关",
        corr_to_book=-0.1, residual_sharpe=0.7,
        run_id="a" * 16, entry_hash="b" * 64,
    )
    led = _ledger([
        {"id": "famI", "status": "在册", "versions": [
            {"version": "v1.0", "admission": adm,
             "nine_gate": dict(IC_B, dsr_p=0.9)}]},
    ])
    assert find_standalone_evidence_gaps(extract_versions(led)) == []


def test_g5_diversifier_missing_receipt_flagged():
    led = _ledger([
        {"id": "famD", "status": "在册", "versions": [{
            "version": "v1.0",
            "admission": {
                "track": "diversifier",
                "rationale": "手填",
                "corr_to_book": -0.1,
                "residual_sharpe": 0.8,
            },
            "nine_gate": {},
            "evidence": {},
        }]},
    ])
    v = find_diversifier_receipt_gaps(extract_versions(led))
    assert len(v) == 1 and v[0][0].startswith("G5-receipt-missing")


def test_g5_diversifier_tampered_numbers_flagged():
    adm = diversifier_admission_with_receipt(
        "famD", "v1.0", rationale="ok",
        corr_to_book=-0.1, residual_sharpe=0.8,
        run_id="a" * 16, entry_hash="b" * 64,
    )
    adm["residual_sharpe"] = 1.5  # 拆收据改数
    led = _ledger([
        {"id": "famD", "status": "在册", "versions": [{
            "version": "v1.0", "admission": adm, "nine_gate": {}, "evidence": {},
        }]},
    ])
    v = find_diversifier_receipt_gaps(extract_versions(led))
    assert len(v) == 1 and v[0][0].startswith("G5-receipt-mismatch")


def test_g5_self_bound_receipt_fails_without_external_ledger():
    adm = diversifier_admission_with_receipt(
        "famD", "v1.0", rationale="ok",
        corr_to_book=-0.1, residual_sharpe=0.8,
        run_id="a" * 16, entry_hash="b" * 64,
    )
    led = _ledger([
        {"id": "famD", "status": "在册", "versions": [{
            "version": "v1.0", "admission": adm, "nine_gate": {}, "evidence": {},
        }]},
    ])
    v = find_diversifier_receipt_gaps(extract_versions(led), research_records=None)
    assert len(v) == 1 and v[0][0].startswith("G5-ledger-unavailable")


def test_clean_ledger_passes():
    record = _research_record()
    ng = record["metrics"]
    receipt = build_nine_gate_receipt(
        "famE", "v1.0", ng,
        run_id=record["run_id"], entry_hash=record["entry_hash"],
    )
    led = _ledger([
        _active_standalone(nine_gate=ng, evidence={"nine_gate_receipt": receipt}),
        {"id": "famF", "status": "候选", "versions": [  # 候选无证据 → 不要求,不报
            {"version": "v1.0", "admission": {"track": None}, "nine_gate": {}}]},
    ])
    assert check(led, research_records=[record]) == 0


def test_self_bound_receipt_fails_closed_without_external_ledger():
    assert check(_ledger([_active_standalone()]), research_records=None) == 1


def test_receipt_cannot_be_satisfied_by_comment_or_note_text():
    # 字符串/注释提到字段名不算结构化收据。
    rows = extract_versions(_ledger([
        _active_standalone(evidence={"note": "nine_gate_receipt run_id entry_hash 都已检查"}),
    ]))
    violations = find_nine_gate_receipt_gaps(rows)
    assert len(violations) == 1 and violations[0][0].startswith("G4-receipt-missing")


def test_receipt_detects_nine_gate_numeric_tamper():
    family = _active_standalone()
    family["versions"][0]["nine_gate"]["ic_mean"] += 0.0001
    violations = find_nine_gate_receipt_gaps(extract_versions(_ledger([family])))
    assert len(violations) == 1 and violations[0][0].startswith("G4-receipt-mismatch")


def test_receipt_copied_to_another_family_fails_identity_binding():
    original = _active_standalone("famA")
    copied_evidence = dict(original["versions"][0]["evidence"])
    copied = _active_standalone("famB", evidence=copied_evidence)
    violations = find_nine_gate_receipt_gaps(extract_versions(_ledger([copied])))
    assert len(violations) == 1 and violations[0][0].startswith("G4-receipt-mismatch")


def test_receipt_verifies_against_external_research_record():
    ng = dict(IC_RICH, passed_all=True, dsr_p=0.01, pbo=0.2)
    record = _research_record(nine_gate=ng)
    receipt = build_nine_gate_receipt(
        "famE", "v1.0", ng, run_id=record["run_id"], entry_hash=record["entry_hash"],
    )
    rows = extract_versions(_ledger([
        _active_standalone(nine_gate=ng, evidence={"nine_gate_receipt": receipt}),
    ]))
    assert find_nine_gate_receipt_gaps(rows, research_records=[record]) == []

    tampered = dict(record)
    tampered["metrics"] = dict(ng, ic_mean=0.999)
    violations = find_nine_gate_receipt_gaps(rows, research_records=[tampered])
    assert len(violations) == 1 and violations[0][0].startswith("G4-ledger-chain")


def test_rebound_receipt_still_cannot_relabel_external_run_family():
    ng = dict(IC_RICH, passed_all=True, dsr_p=0.01, pbo=0.2)
    record = _research_record("famA", nine_gate=ng, run_at="2026-07-10T12:01:00")
    forged = build_nine_gate_receipt(
        "famB", "v1.0", ng, run_id=record["run_id"], entry_hash=record["entry_hash"],
    )
    rows = extract_versions(_ledger([
        _active_standalone("famB", nine_gate=ng, evidence={"nine_gate_receipt": forged}),
    ]))
    violations = find_nine_gate_receipt_gaps(rows, research_records=[record])
    assert len(violations) == 1 and violations[0][0].startswith("G4-run-mismatch")


def test_disconnected_but_self_consistent_record_is_rejected():
    record = _research_record()
    record["prev_hash"] = "f" * 64
    record["entry_hash"] = _record_entry_hash(record)
    assert research_chain_problems([record])
    violations = find_nine_gate_receipt_gaps(
        extract_versions(_ledger([_active_standalone()])),
        research_records=[record],
    )
    assert violations[0][0].startswith("G4-ledger-chain")


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
