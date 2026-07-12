"""Stratified price-lake quality sampling (daily ops chokepoint).

Audit: scheduled/run_daily only checked 5 large names — insufficient for
A-share full-market claims (main / ChiNext / STAR, mid-small caps).

Design:
  · Always validate fixed **anchors** (liquid / board representatives).
  · Add **stratified random** codes per board (main / ChiNext / STAR / BSE).
  · Deterministic seed from trade date so the same day is reproducible.
  · Does **not** replace full-lake ``validate_final.py``; this is the cheap
    daily gate. Full scan remains weekly / on-demand.
"""
from __future__ import annotations

import hashlib
import random
from pathlib import Path
from typing import Iterable

import pandas as pd

# Liquid anchors spanning boards (always checked when present).
DEFAULT_ANCHORS: tuple[str, ...] = (
    "600519",  # 沪市主板
    "000001",  # 深市主板
    "300750",  # 创业板
    "600036",  # 沪市大盘
    "601398",  # 沪市金融
    "688981",  # 科创板(若在湖内)
    "002594",  # 中小盘代表
)

# Per-stratum sample sizes (in addition to anchors).
DEFAULT_PER_STRATUM: dict[str, int] = {
    "main": 30,
    "chinext": 20,
    "star": 15,
    "bse": 5,
}

STRATUM_ORDER = ("main", "chinext", "star", "bse")


def classify_board(code: str) -> str:
    """Map 6-digit code stem to board stratum."""
    c = str(code).split(".")[0].zfill(6)
    if c.startswith("688") or c.startswith("689"):
        return "star"
    if c.startswith(("300", "301")):
        return "chinext"
    if c.startswith(("8", "4")) and len(c) == 6:
        # 北交所常见 8xxxxx / 43xxxx 等
        if c.startswith(("43", "83", "87", "88")) or c[0] in "84":
            return "bse"
    return "main"


def list_daily_codes(daily_dir: Path) -> list[str]:
    if not daily_dir.is_dir():
        return []
    return sorted(p.stem for p in daily_dir.glob("*.parquet"))


def select_sample_codes(
    available: Iterable[str],
    *,
    anchors: Iterable[str] = DEFAULT_ANCHORS,
    per_stratum: dict[str, int] | None = None,
    seed: str | int = "0",
) -> list[str]:
    """Build deterministic stratified sample: anchors first, then per-board draws."""
    # Filenames use bare stems (e.g. 600519); keep as-is.
    avail_list = sorted({str(c) for c in available})
    avail_set = set(avail_list)

    chosen: list[str] = []
    for a in anchors:
        stem = str(a)
        if stem in avail_set and stem not in chosen:
            chosen.append(stem)

    by_stratum: dict[str, list[str]] = {k: [] for k in STRATUM_ORDER}
    for code in avail_list:
        if code in chosen:
            continue
        by_stratum[classify_board(code)].append(code)

    quotas = dict(DEFAULT_PER_STRATUM if per_stratum is None else per_stratum)
    # Stable RNG from seed string
    seed_int = int(hashlib.sha256(str(seed).encode()).hexdigest()[:16], 16) % (2**32)
    rng = random.Random(seed_int)

    for stratum in STRATUM_ORDER:
        pool = by_stratum.get(stratum) or []
        n = min(int(quotas.get(stratum, 0)), len(pool))
        if n <= 0:
            continue
        pick = rng.sample(pool, n) if n < len(pool) else list(pool)
        for code in sorted(pick):  # stable within draw
            if code not in chosen:
                chosen.append(code)

    return chosen


def run_sample_quality_check(
    root: Path | str,
    *,
    calendar: pd.Series | None = None,
    anchors: Iterable[str] = DEFAULT_ANCHORS,
    per_stratum: dict[str, int] | None = None,
    seed: str | int | None = None,
    codes: list[str] | None = None,
) -> dict:
    """Validate a stratified sample of per-code daily parquets.

    Returns dict compatible with scheduled_daily_update ``sample_quality``:
      checked, bad, ok, plus strata / n_* diagnostics.
    """
    from lake.validator import DataValidator

    base = Path(root)
    daily_dir = base / "data_lake" / "price" / "daily"
    available = list_daily_codes(daily_dir)

    if seed is None:
        seed = pd.Timestamp.utcnow().strftime("%Y-%m-%d")

    if codes is None:
        codes = select_sample_codes(
            available, anchors=anchors, per_stratum=per_stratum, seed=seed,
        )

    if calendar is None:
        cal_fp = base / "data_lake" / "meta" / "trade_calendar.parquet"
        calendar = pd.read_parquet(cal_fp)["date"] if cal_fp.is_file() else None

    validator = DataValidator(calendar=calendar)
    checked: list[str] = []
    bad: list[dict] = []
    results: list[dict] = []
    strata_checked: dict[str, int] = {k: 0 for k in STRATUM_ORDER}
    missing_files: list[str] = []

    for code in codes:
        fp = daily_dir / f"{code}.parquet"
        if not fp.is_file():
            missing_files.append(code)
            continue
        try:
            df = pd.read_parquet(fp)
            result = validator.validate(code, df)
        except Exception as exc:
            result = {
                "code": code,
                "rows": 0,
                "issues": [f"read/validate error: {type(exc).__name__}: {str(exc)[:80]}"],
                "info": [],
                "ok": False,
            }
        checked.append(code)
        strata_checked[classify_board(code)] = strata_checked.get(classify_board(code), 0) + 1
        results.append(result)
        if not result.get("ok"):
            bad.append({"code": code, "issues": list(result.get("issues") or [])})

    # Fail-closed: any issue fails the sample gate (same as old 5-code check).
    # Also fail if we could not check a minimum coverage (anchors missing entirely).
    min_checked = max(5, len(list(anchors)) // 2)
    coverage_ok = len(checked) >= min_checked
    ok = coverage_ok and not bad

    return {
        "checked": checked,
        "bad": bad,
        "ok": bool(ok),
        "n_checked": len(checked),
        "n_bad": len(bad),
        "n_available": len(available),
        "n_requested": len(codes),
        "missing_files": missing_files,
        "strata_checked": {k: v for k, v in strata_checked.items() if v},
        "seed": str(seed),
        "mode": "stratified_sample",
        "coverage_ok": coverage_ok,
        "min_checked": min_checked,
    }
