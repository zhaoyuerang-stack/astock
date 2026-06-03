"""
Scheduled daily data update wrapper.

This script is the production entrypoint for launchd. It updates data first,
checks freshness, then calls run_daily.py --no-update only when data is fresh
enough for the expected latest A-share trading day.
"""
import argparse
import contextlib
import fcntl
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

LOG_DIR = ROOT / "logs/daily_update"
REPORT_DIR = ROOT / "reports/ops/daily_update"
LOCK_PATH = LOG_DIR / ".scheduled_daily_update.lock"
PYTHON = "/usr/bin/python3"
SAMPLE_CODES = ["600519", "000001", "300750", "600036", "601398"]
CALENDAR_ANCHORS = ["600519", "601398", "000001", "600036", "600000", "601988"]


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for stream in self.streams:
            stream.write(data)
            stream.flush()

    def flush(self):
        for stream in self.streams:
            stream.flush()


@contextlib.contextmanager
def tee_log(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", buffering=1) as log:
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = Tee(old_out, log)
        sys.stderr = Tee(old_err, log)
        try:
            yield
        finally:
            sys.stdout = old_out
            sys.stderr = old_err


@contextlib.contextmanager
def file_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def rebuild_trade_calendar_from_prices():
    from collections import Counter

    counter = Counter()
    for code in CALENDAR_ANCHORS:
        fp = ROOT / f"data_lake/price/daily/{code}.parquet"
        if fp.exists():
            counter.update(pd.read_parquet(fp, columns=["date"])["date"].tolist())
    if not counter:
        return None
    cal = pd.DatetimeIndex(sorted(date for date, count in counter.items() if count >= 5))
    if len(cal):
        out = ROOT / "data_lake/meta/trade_calendar.parquet"
        pd.DataFrame({"date": cal}).to_parquet(out, index=False)
        return cal.max()
    return None


def expected_trade_date(today=None):
    today = pd.Timestamp(today or datetime.now().date())
    cal = pd.read_parquet(ROOT / "data_lake/meta/trade_calendar.parquet")["date"]
    cal = pd.to_datetime(cal)
    eligible = cal[cal <= today]
    local_expected = eligible.max() if len(eligible) else None
    # If the local calendar is stale, be conservative on weekdays. This may
    # skip holiday signals, but it prevents overwriting state with old data.
    if today.weekday() < 5 and (local_expected is None or local_expected < today):
        return today, "weekday_heuristic"
    return local_expected, "local_calendar"


def actual_latest_price_date():
    dates = []
    for fp in sorted((ROOT / "data_lake/price/daily").glob("*.parquet")):
        try:
            df = pd.read_parquet(fp, columns=["date"])
        except Exception:
            continue
        if len(df):
            dates.append(pd.to_datetime(df["date"]).max())
    return max(dates) if dates else None


def sample_quality_check():
    from lake.validator import DataValidator

    cal = pd.read_parquet(ROOT / "data_lake/meta/trade_calendar.parquet")["date"]
    validator = DataValidator(calendar=cal)
    bad = []
    checked = []
    for code in SAMPLE_CODES:
        fp = ROOT / f"data_lake/price/daily/{code}.parquet"
        if not fp.exists():
            continue
        result = validator.validate(code, pd.read_parquet(fp))
        checked.append(code)
        if not result["ok"]:
            bad.append({"code": code, "issues": result["issues"]})
    return {"checked": checked, "bad": bad, "ok": not bad}


def run_updates(report, dry_run=False):
    if dry_run:
        print("[dry-run] skip update_prices/update_fundamental")
        return

    from scripts.data import update_lake

    manifest = update_lake.load_manifest()
    try:
        print("[update] prices")
        result = update_lake.update_prices()
        manifest.update(result)
        report["price_update"] = {"ok": True, **result.get("price_daily", {})}
    except Exception as exc:
        report["price_update"] = {"ok": False, "error": str(exc)}
        print(f"[update] price failed: {exc}")
        traceback.print_exc()

    try:
        print("[update] fundamental")
        result = update_lake.update_fundamental()
        manifest.update(result)
        report["fundamental_update"] = {"ok": True, **result.get("fundamental", {})}
    except Exception as exc:
        report["fundamental_update"] = {"ok": False, "error": str(exc)}
        print(f"[update] fundamental failed: {exc}")
        traceback.print_exc()

    try:
        update_lake.save_manifest(manifest)
    except Exception as exc:
        report["manifest_error"] = str(exc)
        print(f"[update] manifest save failed: {exc}")


def run_signal(report, dry_run=False):
    if dry_run:
        print("[dry-run] skip run_daily.py --no-update")
        report["signal"] = {"generated": False, "dry_run": True}
        return

    print("[signal] run_daily.py --no-update")
    proc = subprocess.run(
        [PYTHON, "run_daily.py", "--no-update"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    report["signal"] = {
        "generated": proc.returncode == 0,
        "returncode": proc.returncode,
    }
    if proc.returncode != 0:
        report["signal"]["error"] = proc.stderr[-1000:]


def run_daily_update(args):
    run_date = datetime.now().date().isoformat()
    log_path = LOG_DIR / f"{run_date}.log"
    report_path = REPORT_DIR / f"{run_date}.json"
    report = {
        "run_date": run_date,
        "started_at": now_iso(),
        "finished_at": None,
        "status": "running",
        "dry_run": args.dry_run,
    }

    with tee_log(log_path):
        print("=" * 72)
        print(f"scheduled_daily_update started_at={report['started_at']} dry_run={args.dry_run}")
        with file_lock(LOCK_PATH) as acquired:
            if not acquired:
                report.update({
                    "status": "skipped_locked",
                    "finished_at": now_iso(),
                    "log_path": str(log_path),
                })
                write_json(report_path, report)
                print("[lock] another scheduled update is running; skip")
                return 2

            try:
                before_latest = actual_latest_price_date()
                calendar_max = rebuild_trade_calendar_from_prices()
                expected, expected_source = expected_trade_date(args.today)
                report["calendar_max_after_rebuild"] = str(calendar_max.date()) if calendar_max is not None else None
                report["expected_trade_date"] = str(expected.date()) if expected is not None else None
                report["expected_trade_date_source"] = expected_source
                report["latest_before_update"] = str(before_latest.date()) if before_latest is not None else None
                print(f"[freshness] before={report['latest_before_update']} expected={report['expected_trade_date']}")

                run_updates(report, dry_run=args.dry_run)

                calendar_max = rebuild_trade_calendar_from_prices()
                expected, expected_source = expected_trade_date(args.today)
                report["calendar_max_after_update"] = str(calendar_max.date()) if calendar_max is not None else None
                report["expected_trade_date"] = str(expected.date()) if expected is not None else None
                report["expected_trade_date_source"] = expected_source
                after_latest = actual_latest_price_date()
                report["latest_after_update"] = str(after_latest.date()) if after_latest is not None else None
                fresh = expected is not None and after_latest is not None and after_latest >= expected
                report["data_fresh"] = bool(fresh)
                report["update_failed_but_data_fresh"] = bool(
                    fresh and (
                        not report.get("price_update", {}).get("ok", True)
                        or not report.get("fundamental_update", {}).get("ok", True)
                    )
                )
                print(f"[freshness] after={report['latest_after_update']} fresh={fresh}")

                report["sample_quality"] = sample_quality_check()
                print(f"[quality] sample_ok={report['sample_quality']['ok']} bad={report['sample_quality']['bad']}")

                if fresh:
                    run_signal(report, dry_run=args.dry_run)
                else:
                    report["signal"] = {
                        "generated": False,
                        "reason": "stale_data",
                    }
                    print("[signal] skip because data is stale")

                signal_ok = bool(report.get("signal", {}).get("generated") or args.dry_run)
                report["status"] = "ok" if fresh and signal_ok else "failed"
                return 0 if report["status"] == "ok" else 1
            except Exception as exc:
                report["status"] = "failed"
                report["error"] = str(exc)
                traceback.print_exc()
                return 1
            finally:
                report["finished_at"] = now_iso()
                report["log_path"] = str(log_path)
                write_json(report_path, report)
                print(f"[report] {report_path}")
                print(f"scheduled_daily_update finished status={report['status']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Do not update data or generate signals.")
    parser.add_argument("--today", help="Override local date for freshness tests, YYYY-MM-DD.")
    args = parser.parse_args()
    raise SystemExit(run_daily_update(args))


if __name__ == "__main__":
    main()
