"""Phase4 must treat Phase2 oos_is_decay FAIL as a hard registration block.

Regression for audit #7:
  _check_blocked had cost/correlation/WF/offset but not oos_is_decay.
  OOS collapse vs IS only wrote a lesson and could still register 「候选」.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import strategy_registry as reg
from workflow.phase4_register import Phase4Register


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
        "cost_sensitivity": {"verdict": "PASS"},
        "correlation": {"verdict": "PASS"},
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


def test_check_blocked_oos_is_decay_fail_returns_reason():
    p2, p3 = _passing_p2_p3()
    p2["oos_is_decay"] = {
        "verdict": "FAIL",
        "is_annual": 0.30,
        "oos_annual": 0.05,
        "ratio": 0.17,
        "threshold": 0.3,
    }
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


def test_register_blocks_oos_is_decay_fail_without_force():
    """对抗: 无 force 时不得登记「候选」。"""
    orig = _tmp_registry()
    try:
        p2, p3 = _passing_p2_p3()
        p2["oos_is_decay"] = {
            "verdict": "FAIL",
            "is_annual": 0.40,
            "oos_annual": 0.05,
            "ratio": 0.125,
            "threshold": 0.3,
        }
        report = Phase4Register("fam-decay-reg", "v1.0").register(
            [], p2, p3, hypothesis="overfit candidate",
        )
        assert report.registered is False
        assert report.status == "blocked"
        assert "oos_is_decay" in report.detail
        # 未写出任何台账文件(blocked 在 register() 写台账之前 return)
        assert not reg.REGISTRY.exists()
    finally:
        if reg.REGISTRY.exists():
            reg.REGISTRY.unlink(missing_ok=True)
        reg.REGISTRY = orig


def test_adversarial_decay_fail_not_silenced_by_other_pass_fields():
    """对抗: cost/corr/WF 全 PASS 不能掩盖 oos_is_decay FAIL。"""
    p2, p3 = _passing_p2_p3()
    p2["cost_sensitivity"] = {"verdict": "PASS"}
    p2["correlation"] = {"verdict": "PASS"}
    p2["offset_sensitivity"] = {"verdict": "PASS"}
    p3["aggregate"] = {"verdict": "PASS", "annual": 0.25, "sharpe": 2.0}
    p2["oos_is_decay"] = {
        "verdict": "FAIL",
        "ratio": 0.0,
        "is_annual": 0.5,
        "oos_annual": 0.0,
        "threshold": 0.3,
    }
    reason = Phase4Register("fam-adv", "v1.0")._check_blocked([], p2, p3)
    assert reason is not None
    assert "oos_is_decay" in reason


def test_adversarial_string_case_only_exact_FAIL_blocks():
    """对抗: 仅精确 verdict==FAIL 阻断;小写/混写不得被当成 PASS 放行(也不误伤)."""
    p2, p3 = _passing_p2_p3()
    # phase2 只产出大写 FAIL;小写不是合法 verdict,不应误报 block
    p2["oos_is_decay"] = {"verdict": "fail", "ratio": 0.1}
    reason = Phase4Register("fam-case", "v1.0")._check_blocked([], p2, p3)
    # 与 cost_sensitivity 一致:严格 == "FAIL"
    assert reason is None or "oos_is_decay" not in reason

    p2["oos_is_decay"] = {"verdict": "FAIL", "ratio": 0.1}
    reason2 = Phase4Register("fam-case2", "v1.0")._check_blocked([], p2, p3)
    assert reason2 is not None and "oos_is_decay" in reason2


def test_force_can_override_oos_is_decay_phase_gate_only():
    """force 可覆盖 phase 门(与 cost FAIL 同轨);holdout 仍另闸——此处只断言 phase 覆盖语义。"""
    p2, p3 = _passing_p2_p3()
    p2["oos_is_decay"] = {"verdict": "FAIL", "ratio": 0.1}
    blocked = Phase4Register("fam-f", "v1.0")._check_blocked([], p2, p3)
    assert blocked is not None
    # force path is register()-level; unit contract: _check_blocked still returns reason
    # (caller decides force). Documented same as cost_sensitivity.


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
