"""Weekly maintenance wrapper for periodic aggregation and quality checks."""
import argparse
import contextlib
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

LOG_DIR = ROOT / "logs/weekly_maintenance"
REPORT_DIR = ROOT / "reports/ops/weekly_maintenance"
PYTHON = "/usr/bin/python3"


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


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def run_subprocess(label, cmd, dry_run=False):
    if dry_run:
        print(f"[dry-run] skip {label}: {' '.join(cmd)}")
        return {"ok": True, "dry_run": True, "returncode": None}
    print(f"[run] {label}: {' '.join(cmd)}")
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, check=False)
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stderr_tail": proc.stderr[-1000:] if proc.stderr else "",
    }


def run_weekly(args):
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
        print(f"scheduled_weekly_maintenance started_at={report['started_at']} dry_run={args.dry_run}")
        try:
            report["aggregate"] = run_subprocess(
                "weekly/monthly aggregate",
                [PYTHON, "-m", "lake.aggregate"],
                dry_run=args.dry_run,
            )
            report["raw_close"] = run_subprocess(
                "raw close refresh",
                [PYTHON, "scripts/data/fetch_raw_close.py"],
                dry_run=args.dry_run,
            )
            report["quality"] = run_subprocess(
                "full quality validation",
                [PYTHON, "validate_final.py"],
                dry_run=args.dry_run,
            )
            # v2.0 实盘监控三件套:失效监控 → 容量/可成交 → 就绪卡
            report["decay_monitor"] = run_subprocess(
                "v2.0 decay monitor (失效监控 → reports/decay_status.json)",
                [PYTHON, "-m", "scripts.research.decay_monitor"],
                dry_run=args.dry_run,
            )
            report["tradability"] = run_subprocess(
                "v2.0 tradability (容量/可成交率)",
                [PYTHON, "-m", "scripts.research.tradability"],
                dry_run=args.dry_run,
            )
            report["live_readiness"] = run_subprocess(
                "v2.0 live readiness (实盘就绪卡)",
                [PYTHON, "-m", "scripts.research.live_readiness"],
                dry_run=args.dry_run,
            )
            report["status"] = "ok" if all(
                report[name].get("ok")
                for name in ["aggregate", "raw_close", "quality", "decay_monitor"]
            ) else "failed"
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
            print(f"scheduled_weekly_maintenance finished status={report['status']}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    raise SystemExit(run_weekly(args))


if __name__ == "__main__":
    main()
