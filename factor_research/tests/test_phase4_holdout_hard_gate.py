"""Phase4 holdout 金库硬闸 + 对抗用例。

覆盖:
  · 空 / 空白 holdout_id 阻断
  · force=True 不得绕过:空 id、伪造 id、弱夏普、DSR 不显著
  · force 仅可覆盖 phase 门,且仍须合法 holdout
  · candidate_id 精确匹配(部分 id 不冒充)
  · force-promote AST 守卫:字面 force=True 可拦;变量/非 bool 字面为已知静态上限
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import strategy_registry as reg
import workflow.phase4_register as phase4_mod
from scripts.ci.check_no_force_promote import scan_source
from workflow.phase4_register import Phase4Register, _holdout_gate


def _tmp_registry():
    orig = reg.REGISTRY
    reg.REGISTRY = Path(tempfile.mktemp(suffix=".json"))
    return orig


def _passing_p2_p3():
    p2 = {
        "config": {"top_n": 25},
        "segments": {
            "IS  2018-2022": {"annual": 0.20, "maxdd": -0.10, "sharpe": 1.5, "calmar": 2.0},
            "OOS 2023-2024": {"annual": 0.18, "maxdd": -0.12, "sharpe": 1.3},
            "压力 2010-2017": {"annual": 0.15, "maxdd": -0.15, "sharpe": 1.0},
        },
    }
    p3 = {"aggregate": {"verdict": "PASS", "annual": 0.19, "maxdd": -0.11, "sharpe": 1.4}}
    return p2, p3


def _write_ledger(path: Path, candidate_id: str, *, sharpe: float, dsr_sig=True, n: int = 40):
    rec = {
        "candidate_id": candidate_id,
        "holdout_metrics": {"sharpe": sharpe, "n": n, "annual": 0.2, "maxdd": -0.1},
        "holdout_dsr_sig": dsr_sig,
        "holdout_trials": 1 if dsr_sig is not False else 50,
        "peek_count": 1,
        "boundary": "2025-01-01",
    }
    path.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")


def _with_holdout_ledger(tmp_path: Path, candidate_id: str, **kwargs):
    ledger = tmp_path / "holdout_validations.jsonl"
    _write_ledger(ledger, candidate_id, **kwargs)
    orig = phase4_mod._HOLDOUT_VALIDATIONS
    phase4_mod._HOLDOUT_VALIDATIONS = ledger
    return orig, ledger


# ── 单元: _holdout_gate ──


def test_holdout_gate_empty_id_blocks():
    block, summary = _holdout_gate("")
    assert block is not None
    assert "无 holdout_id" in block
    assert summary == {}


def test_A1_whitespace_holdout_id_blocks():
    """对抗:空白字符串不得当有效 holdout_id。"""
    block, summary = _holdout_gate("   \t")
    assert block is not None
    assert "无 holdout_id" in block
    assert summary == {}


def test_holdout_gate_missing_record_blocks(tmp_path: Path):
    ledger = tmp_path / "holdout_validations.jsonl"
    ledger.write_text("", encoding="utf-8")
    block, _ = _holdout_gate("missing-id", path=ledger)
    assert block is not None
    assert "无 holdout 校验记录" in block


def test_holdout_gate_passing_record_ok(tmp_path: Path):
    ledger = tmp_path / "holdout_validations.jsonl"
    _write_ledger(ledger, "ok-1", sharpe=0.9, n=30)
    block, summary = _holdout_gate("ok-1", path=ledger)
    assert block is None
    assert summary["holdout_sharpe"] == 0.9


def test_A10_partial_candidate_id_does_not_match(tmp_path: Path):
    """对抗:部分 id 前缀不得冒充完整 candidate_id。"""
    ledger = tmp_path / "holdout_validations.jsonl"
    _write_ledger(ledger, "abc", sharpe=2.0, n=50)
    block, _ = _holdout_gate("ab", path=ledger)
    assert block is not None
    assert "无 holdout 校验记录" in block


# ── 集成: Phase4Register + force ──


def test_phase4_empty_holdout_id_blocks_even_with_force():
    """A2: force=True + 空 holdout_id → 仍阻断。"""
    orig_reg = _tmp_registry()
    try:
        p2, p3 = _passing_p2_p3()
        report = Phase4Register("fam-no-ho", "v1.0").register(
            [], p2, p3, hypothesis="x", force=True, holdout_id="",
        )
        assert report.registered is False
        assert "holdout_id" in report.detail or "金库" in report.detail
    finally:
        reg.REGISTRY = orig_reg


def test_A3_force_with_fabricated_holdout_id_blocks():
    """对抗:force + 无账本记录的伪造 id → 阻断。"""
    orig_reg = _tmp_registry()
    try:
        p2, p3 = _passing_p2_p3()
        report = Phase4Register("adv-fake-id", "v1.0").register(
            [], p2, p3, hypothesis="x", force=True, holdout_id="i-made-this-up",
        )
        assert report.registered is False
        assert "无 holdout 校验记录" in report.detail
    finally:
        reg.REGISTRY = orig_reg


def test_phase4_force_cannot_bypass_failed_holdout(tmp_path: Path):
    """A4: force 可覆盖 phase 失败,但弱夏普 holdout 仍硬阻断。"""
    orig_reg = _tmp_registry()
    orig_ho, _ = _with_holdout_ledger(tmp_path, "weak-ho", sharpe=0.1, n=40)
    try:
        p2, p3 = _passing_p2_p3()
        p2["cost_sensitivity"] = {"verdict": "FAIL"}
        report = Phase4Register("fam-force-ho", "v1.0").register(
            [], p2, p3, hypothesis="x", force=True, holdout_id="weak-ho",
        )
        assert report.registered is False
        assert "holdout" in report.detail.lower() or "夏普" in report.detail
    finally:
        phase4_mod._HOLDOUT_VALIDATIONS = orig_ho
        reg.REGISTRY = orig_reg


def test_A5_force_cannot_bypass_holdout_dsr_fail(tmp_path: Path):
    """对抗:force + holdout 夏普够但 DSR 明确不显著 → 阻断。"""
    orig_reg = _tmp_registry()
    orig_ho, _ = _with_holdout_ledger(
        tmp_path, "dsr-fail", sharpe=2.0, dsr_sig=False, n=100,
    )
    try:
        p2, p3 = _passing_p2_p3()
        report = Phase4Register("adv-dsr", "v1.0").register(
            [], p2, p3, hypothesis="x", force=True, holdout_id="dsr-fail",
        )
        assert report.registered is False
        assert "DSR" in report.detail
    finally:
        phase4_mod._HOLDOUT_VALIDATIONS = orig_ho
        reg.REGISTRY = orig_reg


def test_phase4_force_overrides_phase_but_passes_with_good_holdout(tmp_path: Path):
    """A6: phase 失败 + force + 合法 holdout → 可登记为候选(非在册)。"""
    orig_reg = _tmp_registry()
    orig_ho, _ = _with_holdout_ledger(tmp_path, "good-ho", sharpe=1.1, n=50)
    try:
        p2, p3 = _passing_p2_p3()
        p2["cost_sensitivity"] = {"verdict": "FAIL"}
        report = Phase4Register("fam-force-ok", "v1.0").register(
            [], p2, p3, hypothesis="x", force=True, holdout_id="good-ho",
        )
        assert report.registered is True, report.detail
        assert report.status == "候选"  # force 路径默认不进 在册
    finally:
        phase4_mod._HOLDOUT_VALIDATIONS = orig_ho
        reg.REGISTRY = orig_reg


# ── AST 守卫边界(字面可拦;变量/非 bool 为已知静态上限) ──


def test_A7_factory_cli_has_no_literal_force_true():
    """对抗:factory_cli 源码不得含字面 force=True。"""
    src = (ROOT / "apps" / "factory_cli.py").read_text(encoding="utf-8")
    violations = scan_source(src, label="apps/factory_cli.py")
    assert violations == []


def test_A8_ast_guard_misses_force_variable_known_limit():
    """已知静态上限:force=变量 扫不到——运行时 holdout 硬闸兜底。"""
    src = "f = True\npromote_hypothesis(h, force=f)\n"
    assert scan_source(src, label="x") == []


def test_A9_ast_guard_misses_force_int_known_limit():
    """已知静态上限:force=1 扫不到——运行时 holdout 硬闸兜底。"""
    src = "promote_hypothesis(h, force=1)\n"
    assert scan_source(src, label="x") == []


def test_ast_guard_flags_literal_force_true():
    src = "promote_hypothesis(h, force=True)\n"
    v = scan_source(src, label="x")
    assert len(v) == 1
    assert "force=True" in v[0]


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-q"]))
