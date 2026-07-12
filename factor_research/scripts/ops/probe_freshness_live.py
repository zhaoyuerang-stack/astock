#!/usr/bin/env python3
"""Live drill: daily_all perf + launchd identity + network vs lake freshness.

Usage (cwd=factor_research):
  /opt/homebrew/bin/python3 scripts/ops/probe_freshness_live.py
  /opt/homebrew/bin/python3 scripts/ops/probe_freshness_live.py --with-dry-run

Does **not** kickstart launchd (avoids mutating the lake mid-session).
Uses the same python+script path as com.astcok.daily-update when --with-dry-run.
"""
from __future__ import annotations

import argparse
import os
import plistlib
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-dry-run", action="store_true",
                    help="Run scheduled_daily_update --dry-run --force (same argv as launchd + flags)")
    args = ap.parse_args()

    from lake.freshness import actual_latest_price_date, actual_latest_price_date_str

    print("=" * 72)
    print("probe_freshness_live")
    print("=" * 72)

    # ── perf ──
    all_fp = ROOT / "data_lake/price/daily_all.parquet"
    print(f"[lake] daily_all exists={all_fp.is_file()} "
          f"size_mb={all_fp.stat().st_size/1e6 if all_fp.is_file() else 0:.1f}")
    t0 = time.perf_counter()
    ts = actual_latest_price_date(ROOT)
    cold = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    ts2 = actual_latest_price_date(ROOT)
    warm = (time.perf_counter() - t0) * 1000
    print(f"[perf] canonical latest={ts} cold={cold:.1f}ms warm={warm:.1f}ms")
    print(f"[perf] readiness_str={actual_latest_price_date_str(ROOT)}")

    # ── launchd ──
    uid = os.getuid()
    label = "com.astcok.daily-update"
    proc = subprocess.run(
        ["launchctl", "print", f"gui/{uid}/{label}"],
        capture_output=True, text=True, timeout=15,
    )
    print(f"[launchd] print rc={proc.returncode}")
    if proc.returncode == 0:
        for line in proc.stdout.splitlines():
            if any(k in line for k in ("state =", "path =", "program =", "last exit", "runs =")):
                print(f"  {line.strip()}")
    else:
        print(f"  (not loaded or print failed) {proc.stderr[:200]}")

    plist = Path.home() / "Library/LaunchAgents" / f"{label}.plist"
    if plist.is_file():
        with plist.open("rb") as f:
            data = plistlib.load(f)
        print(f"[launchd] ProgramArguments={data.get('ProgramArguments')}")
        print(f"[launchd] WorkingDirectory={data.get('WorkingDirectory')}")

    # ── network ──
    try:
        from lake.sources.tushare import call
        end = (ts or pd_timestamp_today()).strftime("%Y%m%d")
        start = (ts - __import__("pandas").Timedelta(days=10)).strftime("%Y%m%d") if ts is not None else "20260701"
        df = call("daily", {"ts_code": "600519.SH", "start_date": start, "end_date": end})
        net_max = str(df["trade_date"].max()) if len(df) else None
        lake_ymd = ts.strftime("%Y%m%d") if ts is not None else None
        print(f"[network] tushare 600519 max={net_max} lake={lake_ymd} lag_ok={net_max and lake_ymd and net_max >= lake_ymd}")
    except Exception as exc:
        print(f"[network] FAIL {type(exc).__name__}: {exc}")

    # ── optional dry-run ──
    if args.with_dry_run:
        py = "/opt/homebrew/bin/python3"
        sdu = str(ROOT / "scripts/ops/scheduled_daily_update.py")
        today = actual_latest_price_date_str(ROOT) or "2026-07-11"
        print(f"[dry-run] {py} {sdu} --dry-run --force --today={today}")
        proc = subprocess.run(
            [py, sdu, "--dry-run", "--force", f"--today={today}"],
            cwd=str(ROOT), text=True, capture_output=True, timeout=180,
        )
        print(f"[dry-run] rc={proc.returncode}")
        for line in (proc.stdout or "").splitlines()[-25:]:
            print(f"  {line}")
        if proc.returncode != 0:
            print((proc.stderr or "")[-500:])
            return proc.returncode

    print("=" * 72)
    print("probe_freshness_live done")
    return 0


def pd_timestamp_today():
    import pandas as pd
    return pd.Timestamp.today().normalize()


if __name__ == "__main__":
    raise SystemExit(main())
