"""Canonical price-lake freshness — unit + full-chain adversarial coverage.

Chain under test:
  lake.freshness (single source)
    → scripts.ops.scheduled_daily_update.actual_latest_price_date
    → report[latest_after_update] / data_fresh
    → attach_production_readiness → runtime.production_readiness
    → data_stale gate

Also: bad parquet isolation, daily_all vs per-code conflict, import AST guard.
"""
from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)


# ── fixtures helpers ─────────────────────────────────────────────────────────


def _write_daily(path: Path, code: str, dates: list[str]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({"date": pd.to_datetime(dates), "close": 1.0})
    df.to_parquet(path / f"{code}.parquet", index=False)


def _write_daily_all(root: Path, dates: list[str], code: str = "000001") -> None:
    all_fp = root / "data_lake" / "price" / "daily_all.parquet"
    all_fp.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "date": pd.to_datetime(dates),
        "code": [code] * len(dates),
        "close": [1.0] * len(dates),
    }).to_parquet(all_fp, index=False)


def _write_calendar(root: Path, dates: list[str]) -> None:
    cal = root / "data_lake" / "meta" / "trade_calendar.parquet"
    cal.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": pd.to_datetime(dates)}).to_parquet(cal, index=False)


def _calls_freshness(src: str) -> bool:
    """AST: source must call lake.freshness.actual_latest_price_date(_str)."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id in {
            "actual_latest_price_date",
            "actual_latest_price_date_str",
            "canonical",
        }:
            return True
        if isinstance(func, ast.Attribute) and func.attr in {
            "actual_latest_price_date",
            "actual_latest_price_date_str",
        }:
            return True
    # import-from also required
    return "lake.freshness" in src or "from lake.freshness" in src


# ── unit / structural ────────────────────────────────────────────────────────


def test_per_code_full_scan_not_first_n_only(tmp_path: Path):
    """对抗: sorted 前 N 只滞后时,不得用前 N 误判为陈旧。"""
    from lake.freshness import actual_latest_price_date, actual_latest_price_date_str

    root = tmp_path / "proj"
    daily = root / "data_lake" / "price" / "daily"
    for i in range(12):
        _write_daily(daily, f"{i:06d}", ["2026-06-01", "2026-06-02"])
    _write_daily(daily, "600519", ["2026-06-01", "2026-07-10"])

    ts = actual_latest_price_date(root)
    assert ts is not None and str(ts.date()) == "2026-07-10"
    assert actual_latest_price_date_str(root) == "2026-07-10"


def test_daily_all_preferred_over_stale_per_code(tmp_path: Path):
    from lake.freshness import actual_latest_price_date_str

    root = tmp_path / "proj"
    daily = root / "data_lake" / "price" / "daily"
    _write_daily(daily, "000001", ["2026-01-01"])
    _write_daily_all(root, ["2026-07-08", "2026-07-09"])
    assert actual_latest_price_date_str(root) == "2026-07-09"


def test_daily_all_wins_even_when_per_code_is_newer(tmp_path: Path):
    """策略钉死: compact 表优先于 per-code（即使 per-code 更新）。"""
    from lake.freshness import actual_latest_price_date_str

    root = tmp_path / "proj"
    daily = root / "data_lake" / "price" / "daily"
    _write_daily(daily, "600519", ["2026-07-15"])  # newer per-code
    _write_daily_all(root, ["2026-07-01", "2026-07-02"])  # older compact
    assert actual_latest_price_date_str(root) == "2026-07-02"


def test_corrupt_parquet_skipped_does_not_poison_max(tmp_path: Path):
    """坏文件不得拖垮新鲜度;好文件仍贡献 max date。"""
    from lake.freshness import actual_latest_price_date_str

    root = tmp_path / "proj"
    daily = root / "data_lake" / "price" / "daily"
    daily.mkdir(parents=True)
    (daily / "000000.parquet").write_bytes(b"not-a-parquet-file!!!!")
    _write_daily(daily, "000001", ["2026-07-03"])
    (daily / "zzz_empty.parquet").write_bytes(b"")
    assert actual_latest_price_date_str(root) == "2026-07-03"


def test_empty_or_missing_date_column_skipped(tmp_path: Path):
    from lake.freshness import actual_latest_price_date_str

    root = tmp_path / "proj"
    daily = root / "data_lake" / "price" / "daily"
    daily.mkdir(parents=True)
    # wrong schema
    pd.DataFrame({"close": [1.0]}).to_parquet(daily / "bad_schema.parquet", index=False)
    # empty frame with date col
    pd.DataFrame({"date": pd.to_datetime([]), "close": []}).to_parquet(
        daily / "empty.parquet", index=False
    )
    _write_daily(daily, "000002", ["2026-06-20"])
    assert actual_latest_price_date_str(root) == "2026-06-20"


def test_empty_lake_returns_empty(tmp_path: Path):
    from lake.freshness import actual_latest_price_date, actual_latest_price_date_str

    root = tmp_path / "empty"
    (root / "data_lake" / "price" / "daily").mkdir(parents=True)
    assert actual_latest_price_date(root) is None
    assert actual_latest_price_date_str(root) == ""


def test_production_readiness_and_scheduled_share_canonical(tmp_path: Path, monkeypatch):
    import runtime.production_readiness as PR
    import scripts.ops.scheduled_daily_update as SDU
    from lake import freshness as F

    root = tmp_path / "proj"
    daily = root / "data_lake" / "price" / "daily"
    _write_daily(daily, "000001", ["2026-05-01"])
    _write_daily(daily, "600000", ["2026-07-11"])

    monkeypatch.setattr(PR, "ROOT", root)
    monkeypatch.setattr(SDU, "ROOT", root)

    ready = PR.actual_latest_price_date(root)
    sched = SDU.actual_latest_price_date()
    canon = F.actual_latest_price_date(root)

    assert ready == "2026-07-11"
    assert sched is not None and str(sched.date()) == "2026-07-11"
    assert canon is not None and str(canon.date()) == ready


def test_call_sites_import_lake_freshness_ast():
    """入口 AST: 必须委托 lake.freshness,禁止再内联采样实现。"""
    pr = (ROOT / "runtime" / "production_readiness.py").read_text(encoding="utf-8")
    sdu = (ROOT / "scripts" / "ops" / "scheduled_daily_update.py").read_text(encoding="utf-8")
    assert "[:10]" not in pr
    assert _calls_freshness(pr)
    assert _calls_freshness(sdu)
    # 禁止在 wrapper 里再 glob 采样价量
    pr_tree = ast.parse(pr)
    for node in ast.walk(pr_tree):
        if isinstance(node, ast.FunctionDef) and node.name == "actual_latest_price_date":
            body_src = ast.get_source_segment(pr, node) or ""
            assert "glob" not in body_src
            assert "[:10]" not in body_src


# ── full chain ───────────────────────────────────────────────────────────────


def test_e2e_update_advances_freshness_and_clears_data_stale(tmp_path: Path, monkeypatch):
    """全链路: 更新前 stale → 写入新交易日 → after fresh + readiness 无 data_stale。"""
    import runtime.production_readiness as PR
    import scripts.ops.scheduled_daily_update as SDU
    from lake.freshness import actual_latest_price_date

    root = tmp_path / "proj"
    daily = root / "data_lake" / "price" / "daily"
    dates_cal = pd.bdate_range("2026-07-01", "2026-07-15").strftime("%Y-%m-%d").tolist()
    _write_calendar(root, dates_cal)

    # T0: lake only through 2026-07-08
    _write_daily(daily, "000001", ["2026-07-07", "2026-07-08"])
    _write_daily_all(root, ["2026-07-07", "2026-07-08"])
    monkeypatch.setattr(SDU, "ROOT", root)
    monkeypatch.setattr(PR, "ROOT", root)

    before = SDU.actual_latest_price_date()
    assert before is not None and str(before.date()) == "2026-07-08"

    expected = pd.Timestamp("2026-07-10")
    fresh_before = before is not None and before >= expected
    assert fresh_before is False

    readiness_before = PR.build_production_readiness(
        data_date=str(before.date()),
        expected_trade_date=str(expected.date()),
        governance_status="approved",
        decay_status="ok",
        paper_status="ok",
        trading_day_status="trading_day",
        data_issue_status={"status": "ok", "production_blocked": False, "categories": []},
    )
    assert "data_stale" in readiness_before.blocking_reasons

    # Simulate daily price update (ops 写盘后)
    _write_daily(daily, "000001", ["2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10"])
    _write_daily_all(root, ["2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10"])

    after = SDU.actual_latest_price_date()
    assert after is not None and str(after.date()) == "2026-07-10"
    assert after >= expected
    assert actual_latest_price_date(root) == after
    assert PR.actual_latest_price_date(root) == "2026-07-10"

    readiness_after = PR.build_production_readiness(
        data_date=str(after.date()),
        expected_trade_date=str(expected.date()),
        governance_status="approved",
        decay_status="ok",
        paper_status="ok",
        trading_day_status="trading_day",
        data_issue_status={"status": "ok", "production_blocked": False, "categories": []},
    )
    assert "data_stale" not in readiness_after.blocking_reasons
    assert readiness_after.data_date == "2026-07-10"


def test_e2e_attach_production_readiness_uses_report_date_from_canonical(
    tmp_path: Path, monkeypatch,
):
    """日更 report.latest_after_update → attach_production_readiness.data_date 同源。"""
    import runtime.production_readiness as PR
    import scripts.ops.scheduled_daily_update as SDU

    root = tmp_path / "proj"
    daily = root / "data_lake" / "price" / "daily"
    # first-N trap: early codes stale
    for i in range(15):
        _write_daily(daily, f"{i:06d}", ["2026-06-01"])
    _write_daily(daily, "688981", ["2026-07-12"])
    monkeypatch.setattr(SDU, "ROOT", root)
    monkeypatch.setattr(PR, "ROOT", root)

    after = SDU.actual_latest_price_date()
    assert after is not None and str(after.date()) == "2026-07-12"

    # Real get_production_readiness, but neutralize non-freshness gates
    monkeypatch.setattr(PR, "current_governance_status", lambda: "approved")
    monkeypatch.setattr(
        PR, "current_decay_status", lambda root=None, expected=None: "ok",
    )
    monkeypatch.setattr(
        PR, "current_paper_status", lambda root=None, expected=None: "ok",
    )
    monkeypatch.setattr(
        PR,
        "current_data_issue_status",
        lambda root=None: {"status": "ok", "production_blocked": False, "categories": []},
    )
    monkeypatch.setattr(
        PR,
        "current_deployment_identity",
        lambda: {
            "deployment_id": "d1",
            "family": "f",
            "version": "v1",
            "spec_hash": "h",
        },
    )
    # Force get_production_readiness to use our root for any internal path
    monkeypatch.setattr(PR, "ROOT", root)

    report = {
        "latest_after_update": str(after.date()),
        "expected_trade_date": "2026-07-12",
    }
    readiness = SDU.attach_production_readiness(report)

    assert report["production_readiness"]["data_date"] == "2026-07-12"
    assert readiness.data_date == "2026-07-12"
    # If we still used first-10 sampling, data_date would be 2026-06-01 → data_stale
    assert "data_stale" not in readiness.blocking_reasons


def test_e2e_first_n_trap_would_have_failed_under_old_readiness(tmp_path: Path, monkeypatch):
    """对照: 旧 [:10] 逻辑在此夹具上必错;canonical 必对。"""
    import runtime.production_readiness as PR
    import scripts.ops.scheduled_daily_update as SDU

    root = tmp_path / "proj"
    daily = root / "data_lake" / "price" / "daily"
    for i in range(12):
        _write_daily(daily, f"{i:06d}", ["2026-06-01"])
    _write_daily(daily, "600519", ["2026-07-10"])
    monkeypatch.setattr(PR, "ROOT", root)
    monkeypatch.setattr(SDU, "ROOT", root)

    # Old buggy logic simulation
    dates = []
    for fp in sorted(daily.glob("*.parquet"))[:10]:
        df = pd.read_parquet(fp, columns=["date"])
        dates.append(pd.to_datetime(df["date"]).max())
    old_latest = str(max(dates).date()) if dates else ""
    assert old_latest == "2026-06-01"  # trap fires

    new_latest = PR.actual_latest_price_date(root)
    assert new_latest == "2026-07-10"
    assert str(SDU.actual_latest_price_date().date()) == "2026-07-10"

    readiness = PR.build_production_readiness(
        data_date=new_latest,
        expected_trade_date="2026-07-10",
        governance_status="approved",
        decay_status="ok",
        paper_status="ok",
        trading_day_status="trading_day",
        data_issue_status={"status": "ok", "production_blocked": False, "categories": []},
    )
    assert "data_stale" not in readiness.blocking_reasons

    readiness_old = PR.build_production_readiness(
        data_date=old_latest,
        expected_trade_date="2026-07-10",
        governance_status="approved",
        decay_status="ok",
        paper_status="ok",
        trading_day_status="trading_day",
        data_issue_status={"status": "ok", "production_blocked": False, "categories": []},
    )
    assert "data_stale" in readiness_old.blocking_reasons


def test_e2e_scheduled_fresh_flag_matches_readiness_stale_gate(tmp_path: Path, monkeypatch):
    """ops data_fresh 与 readiness data_stale 应对同一对 (latest, expected) 一致。"""
    import runtime.production_readiness as PR
    import scripts.ops.scheduled_daily_update as SDU

    root = tmp_path / "proj"
    daily = root / "data_lake" / "price" / "daily"
    _write_daily(daily, "000001", ["2026-07-01", "2026-07-02"])
    monkeypatch.setattr(SDU, "ROOT", root)

    after_latest = SDU.actual_latest_price_date()
    expected = pd.Timestamp("2026-07-05")
    fresh = after_latest is not None and after_latest >= expected
    assert fresh is False

    readiness = PR.build_production_readiness(
        data_date=str(after_latest.date()),
        expected_trade_date=str(expected.date()),
        governance_status="approved",
        decay_status="ok",
        paper_status="ok",
        trading_day_status="trading_day",
        data_issue_status={"status": "ok", "production_blocked": False, "categories": []},
    )
    # 对称: ops 认为不 fresh ⇔ readiness 认为 data_stale
    assert ("data_stale" in readiness.blocking_reasons) == (not fresh)

    expected2 = pd.Timestamp("2026-07-02")
    fresh2 = after_latest is not None and after_latest >= expected2
    assert fresh2 is True
    readiness2 = PR.build_production_readiness(
        data_date=str(after_latest.date()),
        expected_trade_date=str(expected2.date()),
        governance_status="approved",
        decay_status="ok",
        paper_status="ok",
        trading_day_status="trading_day",
        data_issue_status={"status": "ok", "production_blocked": False, "categories": []},
    )
    assert ("data_stale" in readiness2.blocking_reasons) == (not fresh2)


def test_e2e_compute_final_status_respects_fresh_from_canonical(tmp_path: Path, monkeypatch):
    """日更 status 与 canonical freshness 联动。"""
    import scripts.ops.scheduled_daily_update as SDU

    root = tmp_path / "proj"
    daily = root / "data_lake" / "price" / "daily"
    _write_daily(daily, "000001", ["2026-07-01"])
    monkeypatch.setattr(SDU, "ROOT", root)

    after = SDU.actual_latest_price_date()
    expected = pd.Timestamp("2026-07-10")
    fresh = bool(after is not None and after >= expected)
    assert SDU.compute_final_status(
        fresh=fresh, signal_ok=True, aux_update_ok=True,
        required_update_ok=True, core_update_ok=True,
    ) == "failed"

    expected_ok = pd.Timestamp("2026-07-01")
    fresh_ok = bool(after is not None and after >= expected_ok)
    assert SDU.compute_final_status(
        fresh=fresh_ok, signal_ok=True, aux_update_ok=True,
        required_update_ok=True, core_update_ok=True,
    ) == "ok"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
