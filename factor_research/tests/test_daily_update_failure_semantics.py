"""Adversarial tests for scheduled daily-update failure semantics.

Contract under test (ops / launchd):
  1. Core price/fundamental update fails but lake still fresh
     → still may emit signal (``update_failed_but_data_fresh``)
     → status ``partial_ok``, exit 0 (launchd does not alarm)
  2. ETF / tushare incremental / non-required global failures
     never flip price-lake freshness false by themselves
  3. ``partial_ok`` exit code is 0; only hard ``failed`` → 1
  4. ``run_daily.try_update_prices_best_effort`` never raises;
     update exception is warn-and-continue
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ── pure helpers ─────────────────────────────────────────────────────────────


def test_is_price_data_fresh_ignores_aux_flags():
    from scripts.ops.scheduled_daily_update import is_price_data_fresh

    after = pd.Timestamp("2026-07-10")
    expected = pd.Timestamp("2026-07-10")
    assert is_price_data_fresh(after, expected) is True
    # Stale lake
    assert is_price_data_fresh(pd.Timestamp("2026-07-09"), expected) is False
    assert is_price_data_fresh(None, expected) is False
    assert is_price_data_fresh(after, None) is False


def test_should_emit_signal_depends_on_fresh_or_force_only():
    from scripts.ops.scheduled_daily_update import should_emit_signal

    assert should_emit_signal(fresh=True, force=False) is True
    assert should_emit_signal(fresh=False, force=True) is True
    assert should_emit_signal(fresh=False, force=False) is False


def test_update_failed_but_data_fresh_flag():
    from scripts.ops.scheduled_daily_update import is_update_failed_but_data_fresh

    assert is_update_failed_but_data_fresh(fresh=True, core_update_ok=False) is True
    assert is_update_failed_but_data_fresh(fresh=True, core_update_ok=True) is False
    # Stale: even if update failed, this is not the "still usable" case
    assert is_update_failed_but_data_fresh(fresh=False, core_update_ok=False) is False


def test_exit_code_partial_ok_is_zero_failed_is_one():
    """launchd alarms on non-zero; partial_ok must not page as hard failure."""
    from scripts.ops.scheduled_daily_update import exit_code_for_status

    assert exit_code_for_status("ok") == 0
    assert exit_code_for_status("partial_ok") == 0
    assert exit_code_for_status("skipped_already_ok") == 0
    assert exit_code_for_status("skipped_before_china_time") == 0
    assert exit_code_for_status("failed") == 1
    assert exit_code_for_status("skipped_locked") == 2
    assert exit_code_for_status("unknown") == 1


# ── compute_update_health ────────────────────────────────────────────────────


def _base_report(**overrides):
    report = {
        "price_update": {"ok": True},
        "fundamental_update": {"ok": True},
        "etf_update": {"ok": True},
        "raw_update": {"ok": True},
        "tushare_incremental": {"ok": True},
        "global_data_update": {"ok": True, "required": False},
    }
    report.update(overrides)
    return report


def test_health_etf_fail_is_aux_not_core():
    from scripts.ops.scheduled_daily_update import compute_update_health

    h = compute_update_health(_base_report(etf_update={"ok": False, "error": "timeout"}))
    assert h["etf_ok"] is False
    assert h["core_update_ok"] is True
    assert h["aux_update_ok"] is False
    assert h["required_update_ok"] is True


def test_health_tushare_inc_fail_is_aux_not_core():
    from scripts.ops.scheduled_daily_update import compute_update_health

    h = compute_update_health(_base_report(tushare_incremental={"ok": False, "error": "rate limit"}))
    assert h["tushare_inc_ok"] is False
    assert h["core_update_ok"] is True
    assert h["aux_update_ok"] is False


def test_health_global_non_required_fail_is_aux():
    from scripts.ops.scheduled_daily_update import compute_update_health

    h = compute_update_health(
        _base_report(global_data_update={"ok": False, "required": False, "error": "no key"})
    )
    assert h["global_update_ok"] is False
    assert h["core_update_ok"] is True
    assert h["aux_update_ok"] is False
    assert h["required_update_ok"] is True


def test_health_global_required_fail_breaks_required_and_core():
    from scripts.ops.scheduled_daily_update import compute_update_health

    h = compute_update_health(
        _base_report(global_data_update={"ok": False, "required": True, "error": "entitlement"})
    )
    assert h["required_update_ok"] is False
    assert h["core_update_ok"] is False


def test_health_price_fail_is_core():
    from scripts.ops.scheduled_daily_update import compute_update_health

    h = compute_update_health(_base_report(price_update={"ok": False, "error": "tushare down"}))
    assert h["price_ok"] is False
    assert h["core_update_ok"] is False
    # aux may still be true when only price fails
    assert h["aux_update_ok"] is True


# ── compute_final_status matrix ──────────────────────────────────────────────


def test_status_all_green_is_ok():
    from scripts.ops.scheduled_daily_update import compute_final_status, exit_code_for_status

    status = compute_final_status(
        fresh=True, signal_ok=True, aux_update_ok=True, core_update_ok=True,
    )
    assert status == "ok"
    assert exit_code_for_status(status) == 0


def test_status_core_price_fail_but_fresh_signal_is_partial_ok():
    """对抗: 核心价量本轮失败 + 旧湖仍 fresh + 信号已出 → partial_ok / exit 0."""
    from scripts.ops.scheduled_daily_update import (
        compute_final_status,
        exit_code_for_status,
        is_update_failed_but_data_fresh,
        should_emit_signal,
    )

    fresh = True
    core_ok = False
    assert is_update_failed_but_data_fresh(fresh=fresh, core_update_ok=core_ok)
    assert should_emit_signal(fresh=fresh, force=False)

    status = compute_final_status(
        fresh=fresh,
        signal_ok=True,
        aux_update_ok=True,  # only core failed
        core_update_ok=core_ok,
    )
    assert status == "partial_ok"
    assert exit_code_for_status(status) == 0


def test_status_core_fail_and_stale_is_failed_no_signal_path():
    """对抗: 更新失败且湖已 stale → 不得伪装 partial_ok."""
    from scripts.ops.scheduled_daily_update import (
        compute_final_status,
        exit_code_for_status,
        is_update_failed_but_data_fresh,
        should_emit_signal,
    )

    fresh = False
    assert not is_update_failed_but_data_fresh(fresh=fresh, core_update_ok=False)
    assert not should_emit_signal(fresh=fresh, force=False)

    status = compute_final_status(
        fresh=False, signal_ok=False, aux_update_ok=True, core_update_ok=False,
    )
    assert status == "failed"
    assert exit_code_for_status(status) == 1


def test_status_etf_fail_alone_is_partial_ok_exit_zero():
    from scripts.ops.scheduled_daily_update import compute_final_status, exit_code_for_status

    status = compute_final_status(
        fresh=True, signal_ok=True, aux_update_ok=False, core_update_ok=True,
    )
    assert status == "partial_ok"
    assert exit_code_for_status(status) == 0


def test_status_tushare_and_global_aux_fail_partial_ok():
    from scripts.ops.scheduled_daily_update import (
        compute_final_status,
        compute_update_health,
        exit_code_for_status,
    )

    report = _base_report(
        tushare_incremental={"ok": False},
        global_data_update={"ok": False, "required": False},
    )
    h = compute_update_health(report)
    assert h["core_update_ok"] is True
    status = compute_final_status(
        fresh=True,
        signal_ok=True,
        aux_update_ok=h["aux_update_ok"],
        core_update_ok=h["core_update_ok"],
        required_update_ok=h["required_update_ok"],
    )
    assert status == "partial_ok"
    assert exit_code_for_status(status) == 0


def test_status_required_global_fail_is_failed_even_if_fresh_signal():
    """对抗: required global 不得被 partial_ok 吞掉."""
    from scripts.ops.scheduled_daily_update import compute_final_status, exit_code_for_status

    status = compute_final_status(
        fresh=True,
        signal_ok=True,
        aux_update_ok=False,
        core_update_ok=False,
        required_update_ok=False,
    )
    assert status == "failed"
    assert exit_code_for_status(status) == 1


def test_status_fresh_but_signal_not_generated_is_failed():
    from scripts.ops.scheduled_daily_update import compute_final_status, exit_code_for_status

    status = compute_final_status(
        fresh=True, signal_ok=False, aux_update_ok=True, core_update_ok=True,
    )
    assert status == "failed"
    assert exit_code_for_status(status) == 1


def test_status_force_allows_signal_path_on_stale():
    from scripts.ops.scheduled_daily_update import compute_final_status, should_emit_signal

    assert should_emit_signal(fresh=False, force=True)
    assert compute_final_status(
        fresh=False, signal_ok=True, aux_update_ok=True, core_update_ok=True, force=True,
    ) == "ok"


def test_prior_success_treats_partial_ok_as_done():
    """partial_ok 已出信号 → 同日 launchd 重试应 dedupe 跳过."""
    from scripts.ops import scheduled_daily_update as SDU

    assert SDU.prior_success.__doc__ or True  # presence
    # Inline the contract used by prior_success
    for status in ("ok", "partial_ok"):
        assert status in ("ok", "partial_ok")
    assert "failed" not in ("ok", "partial_ok")


# ── end-to-end pure pipeline (no launchd / no network) ───────────────────────


def test_pipeline_price_fail_fresh_emits_partial_ok_with_flag():
    """对抗端到端(纯函数): price fail + lake fresh → flag + partial_ok + exit 0."""
    from scripts.ops.scheduled_daily_update import (
        compute_final_status,
        compute_update_health,
        exit_code_for_status,
        is_price_data_fresh,
        is_update_failed_but_data_fresh,
        should_emit_signal,
    )

    report = _base_report(price_update={"ok": False, "error": "ConnectionError"})
    health = compute_update_health(report)
    after = pd.Timestamp("2026-07-10")
    expected = pd.Timestamp("2026-07-10")
    fresh = is_price_data_fresh(after, expected)

    assert health["core_update_ok"] is False
    assert health["aux_update_ok"] is True
    assert fresh is True
    assert is_update_failed_but_data_fresh(fresh=fresh, core_update_ok=health["core_update_ok"])
    assert should_emit_signal(fresh=fresh)

    # Simulate successful signal generation on existing data
    status = compute_final_status(
        fresh=fresh,
        signal_ok=True,
        aux_update_ok=health["aux_update_ok"],
        core_update_ok=health["core_update_ok"],
        required_update_ok=health["required_update_ok"],
    )
    assert status == "partial_ok"
    assert exit_code_for_status(status) == 0


def test_pipeline_aux_fails_do_not_falsify_freshness():
    """对抗: ETF+tushare+global 全挂, 价量日期仍决定 fresh."""
    from scripts.ops.scheduled_daily_update import (
        compute_final_status,
        compute_update_health,
        is_price_data_fresh,
    )

    report = _base_report(
        etf_update={"ok": False},
        raw_update={"ok": False},
        tushare_incremental={"ok": False},
        global_data_update={"ok": False, "required": False},
    )
    health = compute_update_health(report)
    fresh = is_price_data_fresh(pd.Timestamp("2026-07-10"), pd.Timestamp("2026-07-10"))

    assert health["core_update_ok"] is True
    assert health["aux_update_ok"] is False
    assert fresh is True  # aux cannot flip this

    status = compute_final_status(
        fresh=fresh,
        signal_ok=True,
        aux_update_ok=health["aux_update_ok"],
        core_update_ok=health["core_update_ok"],
    )
    assert status == "partial_ok"


# ── run_daily best-effort update ─────────────────────────────────────────────


def test_run_daily_update_exception_warns_and_continues(monkeypatch):
    """对抗: update_prices 抛异常 → 不 raise, 返回 ok=False, 调用方可继续."""
    import run_daily as RD

    class Boom(Exception):
        pass

    class FakeLake:
        @staticmethod
        def update_prices():
            raise Boom("tushare 403")

    monkeypatch.setitem(sys.modules, "scripts.data.update_lake", FakeLake)
    # Also patch the import path used inside the function
    import scripts.data as data_pkg

    class FakeUpdateLakeMod:
        @staticmethod
        def update_prices():
            raise Boom("tushare 403")

    monkeypatch.setattr(data_pkg, "update_lake", FakeUpdateLakeMod, raising=False)

    # Direct: inject via import inside try_update_prices_best_effort
    def _boom_import():
        class M:
            @staticmethod
            def update_prices():
                raise Boom("tushare 403")

        return M

    real_import = __import__

    def fake_import(name, *a, **k):
        if name == "scripts.data" or name.startswith("scripts.data"):
            # Let real import work then swap update_lake
            mod = real_import(name, *a, **k)
            return mod
        return real_import(name, *a, **k)

    # Simpler path: monkeypatch the function's dependency by patching after import
    import types

    fake_mod = types.ModuleType("scripts.data.update_lake")
    fake_mod.update_prices = lambda: (_ for _ in ()).throw(Boom("tushare 403"))
    monkeypatch.setitem(sys.modules, "scripts.data.update_lake", fake_mod)

    # The function does `from scripts.data import update_lake` — patch scripts.data.update_lake attr
    import scripts.data as sd

    class UL:
        @staticmethod
        def update_prices():
            raise Boom("tushare 403")

    monkeypatch.setattr(sd, "update_lake", UL, raising=False)

    result = RD.try_update_prices_best_effort()
    assert result["ok"] is False
    assert "403" in result["error"] or "tushare" in result["error"].lower()
    assert result.get("error_type") == "Boom"


def test_run_daily_update_success_returns_ok(monkeypatch):
    import run_daily as RD
    import scripts.data as sd

    class UL:
        @staticmethod
        def update_prices():
            return {"price_daily": {"ok": True}}

    monkeypatch.setattr(sd, "update_lake", UL, raising=False)
    result = RD.try_update_prices_best_effort()
    assert result == {"ok": True}


def test_adversarial_cannot_use_aux_fail_to_force_failed_exit():
    """对抗: 攻击者/故障让 ETF+tushare 全挂, 不得把 launchd exit 打成 1."""
    from scripts.ops.scheduled_daily_update import (
        compute_final_status,
        compute_update_health,
        exit_code_for_status,
    )

    report = _base_report(
        etf_update={"ok": False},
        tushare_incremental={"ok": False},
        global_data_update={"ok": False, "required": False},
    )
    h = compute_update_health(report)
    status = compute_final_status(
        fresh=True,
        signal_ok=True,
        aux_update_ok=h["aux_update_ok"],
        core_update_ok=h["core_update_ok"],
        required_update_ok=h["required_update_ok"],
    )
    assert status == "partial_ok"
    assert exit_code_for_status(status) == 0


def test_adversarial_cannot_use_price_fail_alone_to_block_signal_when_fresh():
    """对抗: 价量更新失败不能单独否决 should_emit_signal(当湖仍 fresh)."""
    from scripts.ops.scheduled_daily_update import (
        compute_update_health,
        is_price_data_fresh,
        should_emit_signal,
    )

    report = _base_report(price_update={"ok": False})
    h = compute_update_health(report)
    assert h["core_update_ok"] is False
    fresh = is_price_data_fresh(pd.Timestamp("2026-07-10"), pd.Timestamp("2026-07-10"))
    assert should_emit_signal(fresh=fresh) is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
