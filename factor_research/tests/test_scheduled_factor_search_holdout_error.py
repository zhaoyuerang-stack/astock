"""scheduled_factor_search: holdout 异常不得软化 review 叙事(审计#9)。

历史: validate_on_holdout 异常 → ho_ok=False + note, markdown 写
「⚠️ 未能校验,需人工复核」,且不写 review_queue holdout 字段;
9-Gate 报告仍可 passed_all=True 看起来全绿。

现契约: 异常 → holdout_status=error, holdout_ok=False, 晋级裁决=否,
markdown 硬 ❌ holdout_error, 禁止「跳过不影响报告」软话。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from scripts.ops.scheduled_factor_search import (
    HOLDOUT_ERROR,
    HOLDOUT_FAIL,
    HOLDOUT_PASS,
    classify_holdout_outcome,
    promotion_eligible,
    render_holdout_markdown,
)


def test_classify_exception_is_error_not_soft_skip():
    out = classify_holdout_outcome(error=RuntimeError("ledger locked"))
    assert out["holdout_ok"] is False
    assert out["holdout_status"] == HOLDOUT_ERROR
    assert "RuntimeError" in out["holdout_error"]
    assert "ledger locked" in out["holdout_error"]
    assert out["holdout_sharpe"] is None


def test_classify_fail_on_low_sharpe():
    out = classify_holdout_outcome(
        ho={"sharpe": 0.2, "holdout_dsr_sig": True, "peek_count": 1, "annual": 0.05},
    )
    assert out["holdout_ok"] is False
    assert out["holdout_status"] == HOLDOUT_FAIL


def test_classify_fail_on_dsr_insignificant():
    out = classify_holdout_outcome(
        ho={"sharpe": 1.2, "holdout_dsr_sig": False, "peek_count": 1},
    )
    assert out["holdout_ok"] is False
    assert out["holdout_status"] == HOLDOUT_FAIL


def test_classify_pass_on_sharpe_and_dsr():
    out = classify_holdout_outcome(
        ho={
            "sharpe": 0.9,
            "holdout_dsr_sig": True,
            "holdout_dsr_p": 0.01,
            "holdout_trials": 3,
            "peek_count": 1,
            "annual": 0.2,
            "maxdd": -0.1,
            "n": 40,
        },
    )
    assert out["holdout_ok"] is True
    assert out["holdout_status"] == HOLDOUT_PASS
    assert out["holdout_error"] is None


def test_classify_short_segment_dsr_none_falls_back_to_sharpe():
    """短段 DSR 未算(None)时只靠夏普门。"""
    out = classify_holdout_outcome(
        ho={"sharpe": 0.8, "holdout_dsr_sig": None, "peek_count": 1},
    )
    assert out["holdout_ok"] is True
    assert out["holdout_status"] == HOLDOUT_PASS


def test_promotion_eligible_requires_both():
    assert promotion_eligible(nine_gate_passed=True, holdout_status=HOLDOUT_PASS) is True
    assert promotion_eligible(nine_gate_passed=True, holdout_status=HOLDOUT_FAIL) is False
    assert promotion_eligible(nine_gate_passed=True, holdout_status=HOLDOUT_ERROR) is False
    assert promotion_eligible(nine_gate_passed=False, holdout_status=HOLDOUT_PASS) is False


def test_markdown_error_is_hard_fail_not_soft_review():
    """对抗: 异常叙事不得含「需人工复核」软化,必须 holdout_error + 可提交 promote=否。"""
    out = classify_holdout_outcome(error=ValueError("peek already used"))
    md = render_holdout_markdown(
        boundary_date="2025-01-01",
        outcome=out,
        nine_gate_passed=True,  # 9-Gate 全绿也不得放行
    )
    assert "holdout_error" in md
    assert "可提交 promote: ❌ 否" in md
    assert "需人工复核" not in md
    assert "未能校验" not in md
    assert "跳过" not in md or "不得" in md  # 禁止「跳过不影响」类软话
    assert "不影响" not in md
    assert "ValueError" in md
    assert "peek already used" in md
    # 9-Gate 好看不得变成总 PASS
    assert "9-Gate passed_all: ✅ PASS" in md
    assert "Holdout 金库: **error**" in md


def test_adversarial_nine_gate_pretty_cannot_make_eligible_on_error():
    """对抗: 9-Gate passed_all=True + holdout error → 仍不可 promote。"""
    out = classify_holdout_outcome(error=OSError("disk full"))
    assert promotion_eligible(
        nine_gate_passed=True, holdout_status=out["holdout_status"],
    ) is False
    md = render_holdout_markdown(
        boundary_date="2025-01-01", outcome=out, nine_gate_passed=True,
    )
    assert "可提交 promote: ❌ 否" in md


def test_markdown_fail_uses_holdout_failed_not_error():
    out = classify_holdout_outcome(ho={"sharpe": 0.1, "holdout_dsr_sig": True, "n": 30})
    md = render_holdout_markdown(
        boundary_date="2025-01-01", outcome=out, nine_gate_passed=False,
    )
    assert "holdout_failed" in md
    assert "holdout_error" not in md
    assert "可提交 promote: ❌ 否" in md


def test_markdown_pass_allows_promote_when_nine_gate_pass():
    out = classify_holdout_outcome(
        ho={"sharpe": 1.0, "holdout_dsr_sig": True, "peek_count": 1, "n": 50, "annual": 0.25, "maxdd": -0.1},
    )
    md = render_holdout_markdown(
        boundary_date="2025-01-01", outcome=out, nine_gate_passed=True,
    )
    assert "可提交 promote: ✅ 是" in md
    assert "holdout_error" not in md


def test_error_takes_priority_over_ho_dict():
    """对抗: 同时给 ho 与 error 时以 error 为准(异常路径不得被假 metrics 洗白)。"""
    out = classify_holdout_outcome(
        ho={"sharpe": 9.9, "holdout_dsr_sig": True},
        error=RuntimeError("boom"),
    )
    assert out["holdout_status"] == HOLDOUT_ERROR
    assert out["holdout_ok"] is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
