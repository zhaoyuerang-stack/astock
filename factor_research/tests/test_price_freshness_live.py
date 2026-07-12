"""Live / full-lake / launchd / network drills for price freshness.

Markers:
  · requires_data_lake — needs real data_lake (FULL profile)
  · network tests skip if tushare unreachable (not if token missing → fail with reason)

These are adversarial against the **real machine state**, not only tmp fixtures.
"""
from __future__ import annotations

import json
import os
import plistlib
import re
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

pytestmark = pytest.mark.requires_data_lake

DAILY_ALL = ROOT / "data_lake" / "price" / "daily_all.parquet"
PLIST_REPO = ROOT / "scripts" / "ops" / "com.astcok.daily-update.plist"
PLIST_LOADED = Path.home() / "Library" / "LaunchAgents" / "com.astcok.daily-update.plist"
PYTHON_LAUNCHD = Path("/opt/homebrew/bin/python3")
SDU = ROOT / "scripts" / "ops" / "scheduled_daily_update.py"

# Perf budgets (real 13M-row daily_all ~380MB): fail if canonical regresses badly.
COLD_MS_BUDGET = 3000.0
WARM_MS_BUDGET = 1000.0
PER_CODE_FULL_MS_BUDGET = 120_000.0  # full 5k scan allowed slow; just ensure finishes


def _ms(fn, *a, **k):
    t0 = time.perf_counter()
    out = fn(*a, **k)
    return out, (time.perf_counter() - t0) * 1000.0


# ── 13M-row daily_all performance ────────────────────────────────────────────


def test_live_daily_all_perf_budget():
    """真湖 daily_all 性能:canonical 须亚秒~数秒级,远快于全量逐只。"""
    from lake.freshness import actual_latest_price_date

    assert DAILY_ALL.is_file(), "daily_all missing"
    size_mb = DAILY_ALL.stat().st_size / 1e6
    assert size_mb > 50, f"daily_all unexpectedly small ({size_mb:.1f} MB)"

    # cold-ish (process may be warm from imports)
    ts, cold_ms = _ms(actual_latest_price_date, ROOT)
    assert ts is not None
    # warm
    ts2, warm_ms = _ms(actual_latest_price_date, ROOT)
    assert ts2 == ts

    assert cold_ms < COLD_MS_BUDGET, f"cold {cold_ms:.0f}ms exceeds {COLD_MS_BUDGET}ms"
    assert warm_ms < WARM_MS_BUDGET, f"warm {warm_ms:.0f}ms exceeds {WARM_MS_BUDGET}ms"

    # row count sanity
    import pyarrow.parquet as pq
    n = pq.ParquetFile(DAILY_ALL).metadata.num_rows
    assert n > 1_000_000, f"expected multi-million rows, got {n}"


def test_live_canonical_beats_or_matches_first10_and_is_self_consistent():
    """真湖: canonical ≥ first-10; readiness 字符串与 Timestamp 同源。"""
    import runtime.production_readiness as PR
    import scripts.ops.scheduled_daily_update as SDU
    from lake.freshness import actual_latest_price_date, actual_latest_price_date_str

    canon = actual_latest_price_date(ROOT)
    assert canon is not None

    daily = ROOT / "data_lake" / "price" / "daily"
    dates = []
    for fp in sorted(daily.glob("*.parquet"))[:10]:
        try:
            df = pd.read_parquet(fp, columns=["date"])
        except Exception:
            continue
        if len(df):
            dates.append(pd.to_datetime(df["date"]).max())
    first10 = max(dates) if dates else None
    if first10 is not None:
        # first10 may lag; must never exceed true max
        assert first10 <= canon + pd.Timedelta(days=0)

    assert PR.actual_latest_price_date(ROOT) == actual_latest_price_date_str(ROOT)
    assert SDU.actual_latest_price_date() == canon
    assert str(canon.date()) == actual_latest_price_date_str(ROOT)


def test_live_full_per_code_scan_agrees_when_forced(monkeypatch):
    """对抗: 临时屏蔽 daily_all → 全量逐只扫描须与 compact max 一致(或可解释接近)。

    若 per-code 滞后于 compact(未 compact 的新日),允许 per-code ≤ compact。
    """
    from lake import freshness as F

    with_compact = F.actual_latest_price_date(ROOT)
    assert with_compact is not None

    # Force fallback path by renaming daily_all out of the way via monkeypatch on exists
    real_exists = Path.exists

    def fake_exists(self):
        if self.name == "daily_all.parquet" and "price" in self.parts:
            return False
        return real_exists(self)

    monkeypatch.setattr(Path, "exists", fake_exists)
    t0 = time.perf_counter()
    without = F.actual_latest_price_date(ROOT)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0
    assert elapsed_ms < PER_CODE_FULL_MS_BUDGET
    assert without is not None
    # compact is preferred authority; per-code full scan should not invent future days
    assert without <= with_compact + pd.Timedelta(days=0)


# ── launchd 真进程入口 ───────────────────────────────────────────────────────


def test_live_launchd_plist_matches_repo_and_is_loaded():
    """真 launchd: Agent 已 load,ProgramArguments 与仓内 plist 一致。"""
    assert PLIST_REPO.is_file()
    assert PLIST_LOADED.is_file(), f"LaunchAgent not installed: {PLIST_LOADED}"

    with PLIST_REPO.open("rb") as f:
        repo = plistlib.load(f)
    with PLIST_LOADED.open("rb") as f:
        loaded = plistlib.load(f)

    assert repo["Label"] == "com.astcok.daily-update"
    assert loaded["Label"] == repo["Label"]
    assert loaded["ProgramArguments"] == repo["ProgramArguments"]
    assert Path(loaded["ProgramArguments"][0]).name == "python3"
    assert Path(loaded["ProgramArguments"][1]).resolve() == SDU.resolve()
    assert Path(loaded["WorkingDirectory"]).resolve() == ROOT.resolve()

    # launchctl print — process domain
    uid = os.getuid()
    proc = subprocess.run(
        ["launchctl", "print", f"gui/{uid}/com.astcok.daily-update"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert proc.returncode == 0, proc.stderr
    out = proc.stdout
    assert "com.astcok.daily-update" in out
    assert str(SDU) in out or "scheduled_daily_update.py" in out
    assert "state =" in out


def test_live_launchd_equivalent_dry_run_force():
    """用与 launchd 相同的解释器+脚本路径跑 --dry-run --force(不写湖、不 kickstart 真更新)。"""
    assert PYTHON_LAUNCHD.is_file()
    # Use today's report date from lake to avoid weekday heuristic surprises
    from lake.freshness import actual_latest_price_date_str

    today = actual_latest_price_date_str(ROOT) or "2026-07-11"
    env = os.environ.copy()
    # avoid spamming desktop/obsidian if notify config present — still may fire
    proc = subprocess.run(
        [
            str(PYTHON_LAUNCHD),
            str(SDU),
            "--dry-run",
            "--force",
            f"--today={today}",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
        env=env,
    )
    combined = (proc.stdout or "") + "\n" + (proc.stderr or "")
    assert proc.returncode == 0, combined[-2000:]
    assert "scheduled_daily_update started_at=" in combined
    assert "dry_run=True" in combined or "[dry-run]" in combined
    assert re.search(r"fresh=(True|False)", combined)
    assert "latest_before_update" in combined or "before=" in combined
    # freshness path exercised
    assert "after=" in combined or "latest_after_update" in combined


# ── 真网拉数 ────────────────────────────────────────────────────────────────


def test_live_network_tushare_agrees_with_lake_latest():
    """真网: tushare daily 最新交易日 ≥ 湖内 latest(湖可略滞后,不得超前网侧)。

    若接口失败则 skip(环境/封禁),有 token 却失败会写明原因。
    """
    from lake.freshness import actual_latest_price_date
    from lake.sources.tushare import call

    lake_ts = actual_latest_price_date(ROOT)
    assert lake_ts is not None
    lake_ymd = lake_ts.strftime("%Y%m%d")

    start = (lake_ts - pd.Timedelta(days=14)).strftime("%Y%m%d")
    end = (lake_ts + pd.Timedelta(days=7)).strftime("%Y%m%d")
    try:
        df = call(
            "daily",
            {"ts_code": "600519.SH", "start_date": start, "end_date": end},
        )
    except Exception as exc:
        pytest.skip(f"tushare network unavailable: {exc}")

    assert len(df) > 0, "tushare daily returned empty"
    net_max = str(df["trade_date"].max())
    # Lake should not be ahead of the exchange feed for the same stock window
    assert net_max >= lake_ymd or net_max == lake_ymd, (
        f"lake {lake_ymd} ahead of network {net_max} — clock/lake corruption?"
    )
    # Soft: if lake lags by many sessions, still pass but expose lag days
    lag = (pd.Timestamp(net_max) - pd.Timestamp(lake_ymd)).days
    assert lag < 30, f"lake lag {lag}d too large (net={net_max} lake={lake_ymd})"


def test_live_network_trade_cal_open_days_cover_lake_latest():
    from lake.freshness import actual_latest_price_date
    from lake.sources.tushare import call

    lake_ts = actual_latest_price_date(ROOT)
    assert lake_ts is not None
    start = (lake_ts - pd.Timedelta(days=20)).strftime("%Y%m%d")
    end = (lake_ts + pd.Timedelta(days=5)).strftime("%Y%m%d")
    try:
        cal = call("trade_cal", {"exchange": "SSE", "start_date": start, "end_date": end})
    except Exception as exc:
        pytest.skip(f"tushare trade_cal unavailable: {exc}")

    open_days = set(
        cal.loc[cal["is_open"].astype(int) == 1, "cal_date"].astype(str).tolist()
    )
    lake_ymd = lake_ts.strftime("%Y%m%d")
    assert lake_ymd in open_days, (
        f"lake latest {lake_ymd} not an SSE open day in trade_cal — calendar/lake mismatch"
    )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
