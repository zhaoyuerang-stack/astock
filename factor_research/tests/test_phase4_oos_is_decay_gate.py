"""Phase4 must treat Phase2 oos_is_decay FAIL as a hard registration block.

Regression for audit #7:
  _check_blocked had cost/correlation/WF/offset but not oos_is_decay.
  OOS collapse vs IS only wrote a lesson and could still register 「候选」.

Includes full integration adversarial paths (register + force + holdout ledger).
"""
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
import workflow.phase4_register as phase4_mod
from workflow.phase4_register import Phase4Register


def _tmp_registry():
    orig = reg.REGISTRY
    reg.REGISTRY = Path(tempfile.mktemp(suffix=".json"))
    return orig


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


def _decay_fail_block(**extra):
    base = {
        "verdict": "FAIL",
        "is_annual": 0.40,
        "oos_annual": 0.05,
        "ratio": 0.125,
        "threshold": 0.3,
    }
    base.update(extra)
    return base


def _passing_p2_p3():
    p2 = {
        "config": {"top_n": 25},
        "segments": {
            "IS  2018-2022": {"annual": 0.20, "maxdd": -0.10, "sharpe": 1.5, "calmar": 2.0},
            "OOS 2023-2024": {"annual": 0.18, "maxdd": -0.12, "sharpe": 1.3},
            "压力 2010-2017": {"annual": 0.15, "maxdd": -0.15, "sharpe": 1.0},
        },
        "cost_sensitivity": {"verdict": "PASS"},
        "correlation": {"verdict": "PASS"},
        "offset_sensitivity": {"verdict": "PASS"},
        "oos_is_decay": {
            "verdict": "PASS",
            "is_annual": 0.20,
            "oos_annual": 0.18,
            "ratio": 0.90,
            "threshold": 0.3,
        },
    }
    p3 = {"aggregate": {"verdict": "PASS", "annual": 0.19, "maxdd": -0.11, "sharpe": 1.4}}
    return p2, p3


def _registry_has_family(family_id: str) -> bool:
    if not reg.REGISTRY.exists():
        return False
    data = json.loads(reg.REGISTRY.read_text(encoding="utf-8"))
    fams = data.get("families") or []
    return any(f.get("id") == family_id for f in fams)


def _registry_version_status(family_id: str) -> str | None:
    if not reg.REGISTRY.exists():
        return None
    data = json.loads(reg.REGISTRY.read_text(encoding="utf-8"))
    for fam in data.get("families") or []:
        if fam.get("id") == family_id:
            versions = fam.get("versions") or []
            if not versions:
                return None
            return versions[-1].get("status")
    return None


# ── unit: _check_blocked ─────────────────────────────────────────────────────


def test_check_blocked_oos_is_decay_fail_returns_reason():
    p2, p3 = _passing_p2_p3()
    p2["oos_is_decay"] = _decay_fail_block(ratio=0.17, is_annual=0.30, oos_annual=0.05)
    reason = Phase4Register("fam-decay", "v1.0")._check_blocked([], p2, p3)
    assert reason is not None
    assert "oos_is_decay" in reason
    assert "0.17" in reason


def test_check_blocked_oos_is_decay_pass_not_blocked_by_decay():
    p2, p3 = _passing_p2_p3()
    reason = Phase4Register("fam-ok", "v1.0")._check_blocked([], p2, p3)
    assert reason is None or "oos_is_decay" not in (reason or "")


def test_check_blocked_oos_is_decay_skip_does_not_block():
    """Missing IS/OOS segments → SKIP, not a soft-fail open registration hole."""
    p2, p3 = _passing_p2_p3()
    p2["oos_is_decay"] = {"verdict": "SKIP", "detail": "Missing IS or OOS segment."}
    reason = Phase4Register("fam-skip", "v1.0")._check_blocked([], p2, p3)
    assert reason is None or "oos_is_decay" not in (reason or "")


def test_check_blocked_is_annual_nonpositive_detail_surface():
    p2, p3 = _passing_p2_p3()
    p2["oos_is_decay"] = {
        "verdict": "FAIL",
        "detail": "IS annual ≤ 0 (+0.0%).",
    }
    reason = Phase4Register("fam-isneg", "v1.0")._check_blocked([], p2, p3)
    assert reason is not None
    assert "oos_is_decay FAIL" in reason
    assert "IS annual" in reason


def test_adversarial_decay_fail_not_silenced_by_other_pass_fields():
    """对抗: cost/corr/WF 全 PASS 不能掩盖 oos_is_decay FAIL。"""
    p2, p3 = _passing_p2_p3()
    p2["cost_sensitivity"] = {"verdict": "PASS"}
    p2["correlation"] = {"verdict": "PASS"}
    p2["offset_sensitivity"] = {"verdict": "PASS"}
    p3["aggregate"] = {"verdict": "PASS", "annual": 0.25, "sharpe": 2.0}
    p2["oos_is_decay"] = _decay_fail_block(ratio=0.0, is_annual=0.5, oos_annual=0.0)
    reason = Phase4Register("fam-adv", "v1.0")._check_blocked([], p2, p3)
    assert reason is not None
    assert "oos_is_decay" in reason


def test_adversarial_string_case_only_exact_FAIL_blocks():
    """对抗: 仅精确 verdict==FAIL 阻断;小写不得被当成 PASS 放行(也不误伤)."""
    p2, p3 = _passing_p2_p3()
    p2["oos_is_decay"] = {"verdict": "fail", "ratio": 0.1}
    reason = Phase4Register("fam-case", "v1.0")._check_blocked([], p2, p3)
    assert reason is None or "oos_is_decay" not in reason

    p2["oos_is_decay"] = {"verdict": "FAIL", "ratio": 0.1}
    reason2 = Phase4Register("fam-case2", "v1.0")._check_blocked([], p2, p3)
    assert reason2 is not None and "oos_is_decay" in reason2


# ── integration: register() end-to-end ───────────────────────────────────────


def test_register_blocks_oos_is_decay_fail_without_force():
    """集成: 无 force 时不得登记「候选」、不写台账。"""
    orig = _tmp_registry()
    try:
        p2, p3 = _passing_p2_p3()
        p2["oos_is_decay"] = _decay_fail_block()
        report = Phase4Register("fam-decay-reg", "v1.0").register(
            [], p2, p3, hypothesis="overfit candidate",
        )
        assert report.registered is False
        assert report.status == "blocked"
        assert "oos_is_decay" in report.detail
        assert not reg.REGISTRY.exists()
        assert not _registry_has_family("fam-decay-reg")
    finally:
        if reg.REGISTRY.exists():
            reg.REGISTRY.unlink(missing_ok=True)
        reg.REGISTRY = orig


def test_integration_good_holdout_alone_cannot_bypass_decay_without_force(tmp_path: Path):
    """集成对抗: 合法 holdout 不能单独绕过 oos_is_decay(缺 force 时 phase 先拦)。"""
    orig_reg = _tmp_registry()
    orig_ho, _ = _with_holdout_ledger(tmp_path, "good-ho-decay", sharpe=1.2, n=50)
    try:
        p2, p3 = _passing_p2_p3()
        p2["oos_is_decay"] = _decay_fail_block()
        report = Phase4Register("fam-ho-no-force", "v1.0").register(
            [], p2, p3,
            hypothesis="x",
            force=False,
            holdout_id="good-ho-decay",
        )
        assert report.registered is False
        assert report.status == "blocked"
        assert "oos_is_decay" in report.detail
        assert "holdout" not in report.detail.lower()  # 死在 phase 门,未到 holdout
        assert not _registry_has_family("fam-ho-no-force")
    finally:
        phase4_mod._HOLDOUT_VALIDATIONS = orig_ho
        if reg.REGISTRY.exists():
            reg.REGISTRY.unlink(missing_ok=True)
        reg.REGISTRY = orig_reg


def test_integration_force_overrides_decay_with_good_holdout(tmp_path: Path):
    """集成: decay FAIL + force + 合法 holdout → 可登记「候选」(非在册)。"""
    orig_reg = _tmp_registry()
    orig_ho, _ = _with_holdout_ledger(tmp_path, "good-ho-decay2", sharpe=1.1, n=50)
    try:
        p2, p3 = _passing_p2_p3()
        p2["oos_is_decay"] = _decay_fail_block()
        report = Phase4Register("fam-force-decay-ok", "v1.0").register(
            [], p2, p3,
            hypothesis="forced overfit path",
            force=True,
            holdout_id="good-ho-decay2",
        )
        assert report.registered is True, report.detail
        assert report.status == "候选"
        assert _registry_has_family("fam-force-decay-ok")
        assert _registry_version_status("fam-force-decay-ok") == "候选"
    finally:
        phase4_mod._HOLDOUT_VALIDATIONS = orig_ho
        if reg.REGISTRY.exists():
            reg.REGISTRY.unlink(missing_ok=True)
        reg.REGISTRY = orig_reg


def test_integration_force_cannot_bypass_empty_holdout_with_decay_fail(tmp_path: Path):
    """集成对抗: force 覆盖 phase 后,空 holdout_id 仍硬阻断。"""
    orig_reg = _tmp_registry()
    try:
        p2, p3 = _passing_p2_p3()
        p2["oos_is_decay"] = _decay_fail_block()
        report = Phase4Register("fam-force-empty-ho", "v1.0").register(
            [], p2, p3, hypothesis="x", force=True, holdout_id="",
        )
        assert report.registered is False
        assert report.status == "blocked"
        assert "holdout_id" in report.detail or "金库" in report.detail
        assert not _registry_has_family("fam-force-empty-ho")
    finally:
        if reg.REGISTRY.exists():
            reg.REGISTRY.unlink(missing_ok=True)
        reg.REGISTRY = orig_reg


def test_integration_force_cannot_bypass_fabricated_holdout_with_decay_fail():
    """集成对抗: force + 伪造 holdout id → 阻断,台账不写。"""
    orig_reg = _tmp_registry()
    try:
        p2, p3 = _passing_p2_p3()
        p2["oos_is_decay"] = _decay_fail_block()
        report = Phase4Register("fam-force-fake-ho", "v1.0").register(
            [], p2, p3,
            hypothesis="x",
            force=True,
            holdout_id="i-made-this-holdout-up",
        )
        assert report.registered is False
        assert "无 holdout 校验记录" in report.detail
        assert not _registry_has_family("fam-force-fake-ho")
    finally:
        if reg.REGISTRY.exists():
            reg.REGISTRY.unlink(missing_ok=True)
        reg.REGISTRY = orig_reg


def test_integration_force_cannot_bypass_weak_holdout_sharpe_with_decay_fail(tmp_path: Path):
    """集成对抗: force 过 phase 后,弱夏普 holdout 仍硬阻断。"""
    orig_reg = _tmp_registry()
    orig_ho, _ = _with_holdout_ledger(tmp_path, "weak-ho-decay", sharpe=0.1, n=40)
    try:
        p2, p3 = _passing_p2_p3()
        p2["oos_is_decay"] = _decay_fail_block()
        report = Phase4Register("fam-force-weak-ho", "v1.0").register(
            [], p2, p3,
            hypothesis="x",
            force=True,
            holdout_id="weak-ho-decay",
        )
        assert report.registered is False
        assert "holdout" in report.detail.lower() or "夏普" in report.detail
        assert not _registry_has_family("fam-force-weak-ho")
    finally:
        phase4_mod._HOLDOUT_VALIDATIONS = orig_ho
        if reg.REGISTRY.exists():
            reg.REGISTRY.unlink(missing_ok=True)
        reg.REGISTRY = orig_reg


def test_integration_force_cannot_bypass_holdout_dsr_with_decay_fail(tmp_path: Path):
    """集成对抗: force + holdout 夏普够但 DSR 不显著 → 阻断。"""
    orig_reg = _tmp_registry()
    orig_ho, _ = _with_holdout_ledger(
        tmp_path, "dsr-fail-decay", sharpe=2.0, dsr_sig=False, n=100,
    )
    try:
        p2, p3 = _passing_p2_p3()
        p2["oos_is_decay"] = _decay_fail_block()
        report = Phase4Register("fam-force-dsr", "v1.0").register(
            [], p2, p3,
            hypothesis="x",
            force=True,
            holdout_id="dsr-fail-decay",
        )
        assert report.registered is False
        assert "DSR" in report.detail
        assert not _registry_has_family("fam-force-dsr")
    finally:
        phase4_mod._HOLDOUT_VALIDATIONS = orig_ho
        if reg.REGISTRY.exists():
            reg.REGISTRY.unlink(missing_ok=True)
        reg.REGISTRY = orig_reg


def test_integration_other_gates_pass_cannot_register_on_decay_fail(tmp_path: Path):
    """集成对抗: cost/corr/WF/offset 全 PASS + 好 holdout,无 force 仍不得登记。"""
    orig_reg = _tmp_registry()
    orig_ho, _ = _with_holdout_ledger(tmp_path, "good-ho-mask", sharpe=1.5, n=60)
    try:
        p2, p3 = _passing_p2_p3()
        p2["cost_sensitivity"] = {"verdict": "PASS"}
        p2["correlation"] = {"verdict": "PASS"}
        p2["offset_sensitivity"] = {"verdict": "PASS"}
        p3["aggregate"] = {"verdict": "PASS", "annual": 0.30, "sharpe": 2.5}
        p2["oos_is_decay"] = _decay_fail_block(ratio=0.05)
        report = Phase4Register("fam-mask-decay", "v1.0").register(
            [], p2, p3,
            hypothesis="pretty metrics but oos collapse",
            force=False,
            holdout_id="good-ho-mask",
        )
        assert report.registered is False
        assert report.status == "blocked"
        assert "oos_is_decay" in report.detail
        assert not _registry_has_family("fam-mask-decay")
    finally:
        phase4_mod._HOLDOUT_VALIDATIONS = orig_ho
        if reg.REGISTRY.exists():
            reg.REGISTRY.unlink(missing_ok=True)
        reg.REGISTRY = orig_reg


def test_integration_decay_pass_with_good_holdout_registers(tmp_path: Path):
    """正向集成: decay PASS + 好 holdout → 可登记(对照,防闸门误伤)。"""
    orig_reg = _tmp_registry()
    orig_ho, _ = _with_holdout_ledger(tmp_path, "good-ho-pass", sharpe=1.2, n=50)
    try:
        p2, p3 = _passing_p2_p3()
        assert p2["oos_is_decay"]["verdict"] == "PASS"
        report = Phase4Register("fam-decay-pass", "v1.0").register(
            [], p2, p3,
            hypothesis="healthy oos",
            force=False,
            holdout_id="good-ho-pass",
        )
        assert report.registered is True, report.detail
        assert _registry_has_family("fam-decay-pass")
    finally:
        phase4_mod._HOLDOUT_VALIDATIONS = orig_ho
        if reg.REGISTRY.exists():
            reg.REGISTRY.unlink(missing_ok=True)
        reg.REGISTRY = orig_reg


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
