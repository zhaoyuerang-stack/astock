"""factory/lines L0-L3: 入口自身 assert holdout,不得依赖调用方截断(审计#10)。

对抗: 直接 run_l0(..., full_close 含金库期) → HoldoutBreach,且不得先算 IC 再吞异常。
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from factory.ontology import EconomicThesis, Hypothesis, HypothesisStatus
from factory.lines.line2_validation.l0_ic_scan import precompute_forward_returns, run_l0
from factory.lines.line2_validation.l1_quick_bt import run_l1
from factory.lines.line2_validation.l2_multi_regime import run_l2
from factory.lines.line2_validation.l3_walk_forward import run_l3
from factory.lines.line2_validation.holdout_guard import assert_factory_panels_clean
from governance.holdout import HoldoutBreach, boundary


def _panel(start: str, end: str, n_stocks: int = 8):
    dates = pd.bdate_range(start, end)
    codes = [f"{600000 + i:06d}" for i in range(n_stocks)]
    rng = np.random.default_rng(0)
    close = pd.DataFrame(
        100 + rng.normal(0, 1, size=(len(dates), n_stocks)).cumsum(axis=0),
        index=dates,
        columns=codes,
    )
    volume = pd.DataFrame(1e6, index=dates, columns=codes)
    amount = close * volume
    return close, volume, amount


def _hyp_with_status(status: HypothesisStatus) -> Hypothesis:
    return Hypothesis(
        name="holdout-probe",
        description="probe",
        factor_fn_name="factors.small_cap.small_cap_factor",
        factor_params={},
        data_dependencies=("price/close", "price/volume"),
        status=status,
        thesis=EconomicThesis(mechanism="probe holdout guard", citation="audit#10"),
    )


def _queued_hyp() -> Hypothesis:
    return _hyp_with_status(HypothesisStatus.QUEUED)


def test_assert_factory_panels_clean_rejects_vault_touch():
    close, volume, amount = _panel("2024-06-01", "2025-06-01")
    with pytest.raises(HoldoutBreach):
        assert_factory_panels_clean(close, volume, amount, label="probe")


def test_assert_factory_panels_clean_allows_pre_boundary():
    b = boundary()
    end = (b - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
    close, volume, amount = _panel("2023-01-01", end)
    assert_factory_panels_clean(close, volume, amount, label="clean")


def test_run_l0_rejects_full_close_before_factor_compute():
    """对抗: 直接塞含金库期 close → HoldoutBreach,且 factor_fn 不得被调用。"""
    close, volume, amount = _panel("2024-01-01", "2026-03-01")
    # 构造 forward_ret 时 precompute 也会拦;这里直接造 index 越过边界的 fake forward
    forward_ret = close.pct_change(20).shift(-20)
    hyp = _queued_hyp()
    called = {"n": 0}

    def boom_factor(*a, **k):
        called["n"] += 1
        raise AssertionError("factor must not run on vault-touching panels")

    with mock.patch(
        "factory.lines.line2_validation.l0_ic_scan._resolve_factor_fn",
        return_value=boom_factor,
    ):
        with pytest.raises(HoldoutBreach) as ei:
            run_l0(hyp, close, volume, amount, forward_ret, vintage_id="peek")
    assert called["n"] == 0
    assert "holdout" in str(ei.value).lower() or "金库" in str(ei.value)


def test_run_l0_rejects_when_only_forward_ret_touches_vault():
    """对抗: close 已截断但 forward_ret 含金库 → 仍拦。"""
    b = boundary()
    end_clean = (b - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    close, volume, amount = _panel("2023-01-01", end_clean)
    dirty_fwd, _, _ = _panel("2024-06-01", "2025-06-01")
    forward_ret = dirty_fwd.pct_change(5)
    hyp = _queued_hyp()
    with pytest.raises(HoldoutBreach):
        run_l0(hyp, close, volume, amount, forward_ret, vintage_id="fwd-peek")


def test_precompute_forward_returns_rejects_vault():
    close, _, _ = _panel("2024-01-01", "2025-06-01")
    with pytest.raises(HoldoutBreach):
        precompute_forward_returns(close)


def test_run_l1_l2_l3_reject_vault():
    close, volume, amount = _panel("2024-01-01", "2025-06-01")
    with pytest.raises(HoldoutBreach):
        run_l1(
            _hyp_with_status(HypothesisStatus.L0_PASSED),
            close, volume, amount, direction=1, vintage_id="l1",
        )
    with pytest.raises(HoldoutBreach):
        run_l2(
            _hyp_with_status(HypothesisStatus.L1_PASSED),
            close, volume, amount, direction=1, vintage_id="l2",
        )
    with pytest.raises(HoldoutBreach):
        run_l3(
            _hyp_with_status(HypothesisStatus.L2_PASSED),
            close, volume, amount, direction=1, vintage_id="l3",
        )


def test_run_l0_accepts_clean_panel_without_breach():
    """正向: 截断到 <boundary 的面板可通过闸门(不要求 IC 过闸)。"""
    b = boundary()
    end = (b - pd.Timedelta(days=5)).strftime("%Y-%m-%d")
    close, volume, amount = _panel("2022-01-01", end, n_stocks=30)
    forward_ret = precompute_forward_returns(close)
    hyp = _queued_hyp()
    # 用常数因子避免依赖真实 factors 实现
    factor = pd.DataFrame(
        np.random.default_rng(1).normal(size=close.shape),
        index=close.index,
        columns=close.columns,
    )
    exp = run_l0(
        hyp, close, volume, amount, forward_ret,
        vintage_id="clean", factor=factor,
    )
    # 可能 DISCARD 因 IC,但不得是 HoldoutBreach 吞成 error
    assert "HoldoutBreach" not in (exp.result.error or "")
    assert "金库" not in (exp.result.error or "")


def test_holdout_breach_not_swallowed_as_discard():
    """对抗: HoldoutBreach 必须向上抛,不得变成 Experiment DISCARD。"""
    close, volume, amount = _panel("2024-01-01", "2025-12-01")
    forward_ret = close.pct_change(5)
    hyp = _queued_hyp()
    with pytest.raises(HoldoutBreach):
        run_l0(hyp, close, volume, amount, forward_ret, vintage_id="no-swallow")


def test_evaluate_candidate_rejects_vault():
    from factory.lines.line3_marginal.marginal_eval import evaluate_candidate

    close, volume, amount = _panel("2024-01-01", "2025-06-01")
    hyp = _hyp_with_status(HypothesisStatus.L1_PASSED)
    live = {"book": pd.Series(0.0, index=close.index)}
    with pytest.raises(HoldoutBreach):
        evaluate_candidate(
            hyp, 1, live, close, volume, amount, vintage_id="mg",
        )


def test_compliance_lists_factory_lines():
    from scripts.ci.check_holdout_compliance import REQUIRED, HOLDOUT_CALLS, has_holdout_call

    assert "factory/lines/line2_validation/l0_ic_scan.py" in REQUIRED
    assert "assert_factory_panels_clean" in HOLDOUT_CALLS
    src = (ROOT / "factory/lines/line2_validation/l0_ic_scan.py").read_text(encoding="utf-8")
    assert has_holdout_call(src)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
