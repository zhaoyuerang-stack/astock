"""Production signal readiness gate.

This module intentionally lives outside ``services`` so ``run_daily.py`` can use
the same production gate without violating layer dependency rules.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from contracts.views import ProductionReadinessView

ROOT = Path(__file__).resolve().parents[1]
CHINA_TZ = ZoneInfo("Asia/Shanghai")

GOVERNANCE_ALLOWED = {"approved", "audit_passed", "passed", "ok"}
PAPER_ALLOWED = {"ok", "ready", "normal"}
PAPER_WARN = {"", "unknown", "missing"}
TRADING_ALLOWED = {"", "trading_day", "expected_closed_day", "ok"}


def _today_for_expected() -> pd.Timestamp:
    # Before the China open, the latest closed trading day is still yesterday.
    return pd.Timestamp((datetime.now(CHINA_TZ) - pd.Timedelta(hours=9)).date())


def _date_str(value) -> str:
    if value is None or value == "":
        return ""
    try:
        return str(pd.Timestamp(value).date())
    except Exception:
        return str(value)


def _parse_date(value):
    if value is None or value == "":
        return None
    try:
        return pd.Timestamp(value)
    except Exception:
        return None


def actual_latest_price_date(root: Path = ROOT) -> str:
    dates = []
    for fp in sorted((root / "data_lake/price/daily").glob("*.parquet")):
        try:
            df = pd.read_parquet(fp, columns=["date"])
        except Exception:
            continue
        if len(df):
            dates.append(pd.to_datetime(df["date"]).max())
    return _date_str(max(dates)) if dates else ""


def latest_expected_trade_date(root: Path = ROOT, today=None) -> tuple[str, str]:
    if today is None:
        today_ts = _today_for_expected()
    else:
        today_ts = pd.Timestamp(today)
    cal_path = root / "data_lake/meta/trade_calendar.parquet"
    if not cal_path.exists():
        return "", "calendar_missing"
    try:
        cal = pd.read_parquet(cal_path)["date"]
        cal = pd.to_datetime(cal)
    except Exception:
        return "", "calendar_unreadable"
    eligible = cal[cal <= today_ts]
    if len(eligible):
        return _date_str(eligible.max()), "local_calendar"
    return "", "calendar_empty"


def _nine_gate_audit_state(nine_gate: dict) -> dict:
    ng = nine_gate or {}
    if ng.get("status") == "FAILED_TO_RUN":
        return {"code": "RUN_FAILED", "audited": False, "passed": False}

    dsr_p = ng.get("dsr_p")
    if dsr_p is None:
        return {"code": "PENDING", "audited": False, "passed": None}

    passed = (ng.get("gate4_verdict") == "PASS") if ng.get("gate4_verdict") else (dsr_p < 0.05)
    return {"code": "PASSED" if passed else "FAILED", "audited": True, "passed": bool(passed)}


def current_governance_status() -> str:
    try:
        import strategy_registry
        from app_config.settings import get_settings

        sc = get_settings().strategy
        data = strategy_registry._load()
        fam = next((f for f in data.get("families", []) if f.get("id") == sc.family), None)
        version = next(
            (v for v in (fam or {}).get("versions", []) if v.get("version") == sc.version),
            None,
        )
        if version is None or version.get("status") != "在册":
            return "not_registered"
        audit = _nine_gate_audit_state(version.get("nine_gate") or {})
        if audit["code"] == "RUN_FAILED":
            return "nine_gate_failed"
        if not audit["audited"]:
            return "dsr_pending"
        if audit["passed"] is False:
            return "dsr_not_significant"
        return "approved"
    except Exception:
        return "governance_unknown"


def current_decay_status(root: Path = ROOT) -> str:
    fp = root / "reports/decay_status.json"
    if not fp.exists():
        return "unknown"
    try:
        return str(json.loads(fp.read_text(encoding="utf-8")).get("status") or "unknown")
    except Exception:
        return "unreadable"


def current_paper_status(root: Path = ROOT) -> str:
    fp = root / "paper/account.json"
    if not fp.exists():
        return "missing"
    try:
        account = json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return "corrupt"
    if account.get("halted") or account.get("blocked"):
        return "blocked"
    if account.get("last_error"):
        return "error"
    return "ok"


def current_data_issue_status(root: Path = ROOT) -> dict:
    fp = root / "reports/data/data_issue_triage.json"
    if not fp.exists():
        return {"status": "unknown", "production_blocked": False, "categories": []}
    try:
        payload = json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return {"status": "unreadable", "production_blocked": False, "categories": []}
    summary = payload.get("summary") or {}
    categories = sorted((summary.get("counts_by_category") or {}).keys())
    blocked = bool(summary.get("production_blocked"))
    return {
        "status": "block_production" if blocked else "ok",
        "production_blocked": blocked,
        "categories": categories,
    }


def build_production_readiness(
    *,
    data_date: str = "",
    expected_trade_date: str = "",
    governance_status: str = "",
    decay_status: str = "",
    paper_status: str = "",
    trading_day_status: str = "",
    data_issue_status: dict | str | None = None,
) -> ProductionReadinessView:
    blocking_reasons: list[str] = []
    warnings: list[str] = []

    data_date = _date_str(data_date)
    expected_trade_date = _date_str(expected_trade_date)
    data_ts = _parse_date(data_date)
    expected_ts = _parse_date(expected_trade_date)

    if not data_date:
        blocking_reasons.append("data_date_missing")
    if not expected_trade_date:
        warnings.append("expected_trade_date_missing")
    if data_ts is not None and expected_ts is not None and data_ts < expected_ts:
        blocking_reasons.append("data_stale")

    gov = (governance_status or "governance_unknown").strip()
    if gov not in GOVERNANCE_ALLOWED:
        blocking_reasons.append(f"governance:{gov}")

    decay = (decay_status or "unknown").strip()
    if decay.startswith("🔴") or "预警" in decay or decay.lower() in {"red", "failed", "fail", "breach"}:
        blocking_reasons.append("decay:red")
    elif decay.startswith("🟡") or "观察" in decay or decay.lower() in {"yellow", "watch", "warn", "warning"}:
        warnings.append("decay:watch")
    elif decay.lower() in {"", "unknown", "unreadable"}:
        warnings.append(f"decay:{decay or 'unknown'}")

    paper = (paper_status or "unknown").strip()
    if paper in PAPER_WARN:
        warnings.append(f"paper:{paper or 'unknown'}")
    elif paper not in PAPER_ALLOWED:
        blocking_reasons.append(f"paper:{paper}")

    trading = (trading_day_status or "").strip()
    if trading and trading not in TRADING_ALLOWED:
        blocking_reasons.append(f"trading_day:{trading}")

    if isinstance(data_issue_status, dict):
        issue_status = str(data_issue_status.get("status") or "unknown")
        issue_categories = [str(c) for c in data_issue_status.get("categories", [])]
        if data_issue_status.get("production_blocked"):
            blocking_reasons.append("data_issue:block_production")
    else:
        issue_status = str(data_issue_status or "unknown")
        issue_categories = []
        if issue_status == "block_production":
            blocking_reasons.append("data_issue:block_production")

    return ProductionReadinessView(
        allowed=not blocking_reasons,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        data_date=data_date,
        expected_trade_date=expected_trade_date,
        governance_status=gov,
        decay_status=decay,
        paper_status=paper,
        trading_day_status=trading,
        data_issue_status=issue_status,
        data_issue_categories=issue_categories,
        generated_at=datetime.now(CHINA_TZ).isoformat(timespec="seconds"),
    )


def get_production_readiness(
    root: Path = ROOT,
    *,
    data_date: str | None = None,
    expected_trade_date: str | None = None,
    governance_status: str | None = None,
    decay_status: str | None = None,
    paper_status: str | None = None,
    trading_day_status: str | None = None,
    data_issue_status: dict | str | None = None,
) -> ProductionReadinessView:
    root = Path(root)
    if data_date is None:
        data_date = actual_latest_price_date(root)
    expected_source = ""
    if expected_trade_date is None:
        expected_trade_date, expected_source = latest_expected_trade_date(root)
    if governance_status is None:
        governance_status = current_governance_status()
    if decay_status is None:
        decay_status = current_decay_status(root)
    if paper_status is None:
        paper_status = current_paper_status(root)
    if trading_day_status is None:
        trading_day_status = "trading_day" if expected_trade_date else (expected_source or "unknown")
    if data_issue_status is None:
        data_issue_status = current_data_issue_status(root)

    return build_production_readiness(
        data_date=data_date or "",
        expected_trade_date=expected_trade_date or "",
        governance_status=governance_status or "",
        decay_status=decay_status or "",
        paper_status=paper_status or "",
        trading_day_status=trading_day_status or "",
        data_issue_status=data_issue_status,
    )
