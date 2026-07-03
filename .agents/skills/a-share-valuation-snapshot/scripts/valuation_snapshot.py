#!/usr/bin/env python3
"""Build a guarded A-share valuation snapshot from factor_research/data_lake.

This script is read-only. It does not fetch or update market data.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_COLUMNS = [
    "公司",
    "代码",
    "日期",
    "股价",
    "市值",
    "PE(TTM)",
    "PE(2026E)",
    "PB",
    "PS",
    "EV/EBITDA",
    "PEG",
]

ANALYSIS_METRICS = ["市值", "PE(TTM)", "PB", "PS", "EV/EBITDA", "PEG"]
VALUATION_MULTIPLES = ["PE(TTM)", "PB", "PS", "EV/EBITDA", "PEG"]


def parse_codes(raw: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in raw.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" in item:
            code, name = item.split(":", 1)
        else:
            code, name = item, item
        code = code.strip()
        if len(code) != 6 or not code.isdigit():
            raise SystemExit(f"Invalid A-share code: {code!r}")
        out[code] = name.strip() or code
    if not out:
        raise SystemExit("No codes supplied. Use --codes '002371:北方华创,...'")
    return out


def latest_by_code(df: pd.DataFrame, code_col: str, date_col: str, codes: Iterable[str]) -> pd.DataFrame:
    work = df.copy()
    work["code"] = work[code_col].astype(str).str.split(".").str[0]
    work = work[work["code"].isin(set(codes))]
    work["_date_i"] = pd.to_numeric(work[date_col], errors="coerce")
    work = work.dropna(subset=["_date_i"])
    if work.empty:
        return pd.DataFrame()
    idx = work.groupby("code")["_date_i"].idxmax()
    return work.loc[idx].set_index("code")


def fmt_date(yyyymmdd: object) -> str:
    text = str(int(yyyymmdd)) if not isinstance(yyyymmdd, str) else yyyymmdd
    return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except Exception:
        return False


def latest_raw_close(lake: Path, code: str, max_trade_date: int) -> tuple[float | None, str | None]:
    path = lake / "price" / "daily_raw" / f"{code}.parquet"
    if not path.exists():
        return None, None
    df = pd.read_parquet(path)
    if "date" not in df or "raw_close" not in df:
        return None, None
    work = df.dropna(subset=["date", "raw_close"]).copy()
    work["_date_i"] = work["date"].dt.strftime("%Y%m%d").astype(int)
    work = work[work["_date_i"] <= max_trade_date].sort_values("_date_i")
    if work.empty:
        return None, None
    row = work.iloc[-1]
    return float(row["raw_close"]), row["date"].strftime("%Y-%m-%d")


def latest_financial_value(df: pd.DataFrame, code: str, field: str, asof: int) -> tuple[float | None, tuple[int, int] | None]:
    if df.empty or field not in df.columns:
        return None, None
    work = df.copy()
    work["code"] = work["ts_code"].astype(str).str.split(".").str[0]
    work["ann_i"] = pd.to_numeric(work["ann_date"], errors="coerce")
    work["end_i"] = pd.to_numeric(work["end_date"], errors="coerce")
    work = work[(work["code"] == code) & (work["ann_i"] <= asof) & work[field].notna()]
    if work.empty:
        return None, None
    row = work.sort_values(["ann_i", "end_i"]).iloc[-1]
    return float(row[field]), (int(row["ann_i"]), int(row["end_i"]))


def ttm_from_cumulative(df: pd.DataFrame, code: str, field: str, asof: int) -> tuple[float | None, str]:
    if df.empty or field not in df.columns:
        return None, "missing_dataset"
    work = df.copy()
    work["code"] = work["ts_code"].astype(str).str.split(".").str[0]
    work["ann_i"] = pd.to_numeric(work["ann_date"], errors="coerce")
    work["end_i"] = pd.to_numeric(work["end_date"], errors="coerce")
    work = work[(work["code"] == code) & (work["ann_i"] <= asof) & work[field].notna()]
    if work.empty:
        return None, "missing_value"
    latest = work.sort_values(["ann_i", "end_i"]).iloc[-1]
    end = str(int(latest["end_i"]))
    year = int(end[:4])
    month_day = end[4:]
    value = float(latest[field])
    if month_day == "1231":
        return value, f"annual:{int(latest['end_i'])}"
    prev_annual = work[work["end_i"] == int(f"{year - 1}1231")]
    prev_same = work[work["end_i"] == int(f"{year - 1}{month_day}")]
    if prev_annual.empty or prev_same.empty:
        return None, f"missing_ttm_base:{int(latest['end_i'])}"
    prev_a = float(prev_annual.sort_values(["ann_i", "end_i"]).iloc[-1][field])
    prev_s = float(prev_same.sort_values(["ann_i", "end_i"]).iloc[-1][field])
    return value + prev_a - prev_s, f"ttm:{int(latest['end_i'])}"


def maybe_read(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def build_snapshot(repo: Path, codes: dict[str, str]) -> tuple[pd.DataFrame, list[str]]:
    lake = repo / "factor_research" / "data_lake"
    warnings: list[str] = []
    daily_path = lake / "daily_basic" / "daily_basic_all.parquet"
    if not daily_path.exists():
        raise SystemExit(f"Missing daily_basic parquet: {daily_path}")

    daily = pd.read_parquet(daily_path)
    latest = latest_by_code(daily, "ts_code", "trade_date", codes.keys())
    income = maybe_read(lake / "financials" / "income_all.parquet")
    balance = maybe_read(lake / "financials" / "balancesheet_all.parquet")
    indicator = maybe_read(lake / "financials" / "fina_indicator_all.parquet")

    rows: list[dict[str, object]] = []
    for code, name in codes.items():
        if code not in latest.index:
            warnings.append(f"{code} {name}: missing daily_basic row")
            rows.append({"公司": name, "代码": code})
            continue

        row = latest.loc[code]
        asof = int(row["_date_i"])
        close, price_date = latest_raw_close(lake, code, asof)
        daily_date = fmt_date(asof)
        if price_date and price_date != daily_date:
            warnings.append(f"{code} {name}: raw close date {price_date} differs from daily_basic date {daily_date}")

        total_mv_yi = float(row["total_mv"]) / 10000 if finite(row.get("total_mv")) else None
        ps_value = row.get("ps_ttm") if finite(row.get("ps_ttm")) else row.get("ps")

        ebitda, ebitda_context = ttm_from_cumulative(income, code, "ebitda", asof)
        money_cap, _ = latest_financial_value(balance, code, "money_cap", asof)
        st_borr, _ = latest_financial_value(balance, code, "st_borr", asof)
        lt_borr, _ = latest_financial_value(balance, code, "lt_borr", asof)
        ev_ebitda = None
        if ebitda and ebitda > 0 and finite(row.get("total_mv")):
            debt = (st_borr or 0.0) + (lt_borr or 0.0)
            cash = money_cap or 0.0
            ev_wan = float(row["total_mv"]) + (debt - cash) / 10000
            ev_ebitda = ev_wan / (ebitda / 10000)
        elif ebitda_context != "missing_dataset":
            warnings.append(f"{code} {name}: EV/EBITDA unavailable ({ebitda_context})")

        growth, growth_context = latest_financial_value(indicator, code, "netprofit_yoy", asof)
        pe_ttm = float(row["pe_ttm"]) if finite(row.get("pe_ttm")) else None
        peg = pe_ttm / growth if pe_ttm and growth and growth > 0 else None
        if peg is None and growth_context:
            warnings.append(f"{code} {name}: PEG proxy unavailable because netprofit_yoy is not positive or PE missing")

        rows.append(
            {
                "公司": name,
                "代码": code,
                "日期": daily_date,
                "股价": close,
                "市值": total_mv_yi,
                "PE(TTM)": pe_ttm,
                "PE(2026E)": None,
                "PB": float(row["pb"]) if finite(row.get("pb")) else None,
                "PS": float(ps_value) if finite(ps_value) else None,
                "EV/EBITDA": ev_ebitda,
                "PEG": peg,
            }
        )

    snapshot = pd.DataFrame(rows)
    if "日期" in snapshot.columns:
        dates = sorted(str(date) for date in snapshot["日期"].dropna().unique())
        if len(dates) > 1:
            warnings.append(f"Mixed row dates in peer table: {', '.join(dates)}")
    return snapshot, warnings


def numeric_or_none(value: object) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        number = float(value)
    except Exception:
        return None
    return number if math.isfinite(number) else None


def build_analysis(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    numeric = df.copy()
    for metric in ANALYSIS_METRICS:
        if metric in numeric.columns:
            numeric[metric] = pd.to_numeric(numeric[metric], errors="coerce")

    median_rows: list[dict[str, object]] = []
    medians: dict[str, float] = {}
    for metric in ANALYSIS_METRICS:
        if metric not in numeric.columns:
            continue
        series = numeric[metric].dropna()
        series = series[series > 0]
        median = float(series.median()) if not series.empty else float("nan")
        medians[metric] = median
        median_rows.append({"指标": metric, "有效样本数": int(series.count()), "中位数": median if math.isfinite(median) else None})

    deviation_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    for _, row in numeric.iterrows():
        dev_row: dict[str, object] = {"公司": row.get("公司"), "代码": row.get("代码")}
        valuation_devs: list[float] = []
        for metric in ANALYSIS_METRICS:
            value = numeric_or_none(row.get(metric))
            median = medians.get(metric)
            deviation = None
            if value is not None and median is not None and math.isfinite(median) and median > 0:
                deviation = (value / median - 1.0) * 100.0
                if metric in VALUATION_MULTIPLES:
                    valuation_devs.append(deviation)
            dev_row[f"{metric}偏离%"] = deviation
        deviation_rows.append(dev_row)

        composite = float(pd.Series(valuation_devs).median()) if valuation_devs else None
        if len(valuation_devs) < 3:
            label = "估值数据不足"
            composite = None
        elif composite is None:
            label = "估值数据不足"
        elif composite >= 20:
            label = "相对同组偏贵"
        elif composite <= -20:
            label = "相对同组偏便宜"
        else:
            label = "接近同组中位"
        summary_rows.append(
            {
                "公司": row.get("公司"),
                "代码": row.get("代码"),
                "估值综合偏离%": composite,
                "相对位置": label,
                "可用倍数数": len(valuation_devs),
            }
        )

    return pd.DataFrame(median_rows), pd.DataFrame(deviation_rows), pd.DataFrame(summary_rows)


def format_value(value: object) -> str:
    if value is None:
        return "—"
    try:
        if pd.isna(value):
            return "—"
    except Exception:
        pass
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def format_percent(value: object) -> str:
    number = numeric_or_none(value)
    if number is None:
        return "—"
    return f"{number:+.1f}%"


def format_markdown(df: pd.DataFrame, percent_columns: set[str] | None = None) -> str:
    percent_columns = percent_columns or set()
    display = df.copy()
    for col in display.columns:
        if col in {"公司", "代码", "日期", "指标", "相对位置"}:
            continue
        if col in percent_columns or col.endswith("偏离%"):
            display[col] = display[col].map(format_percent)
        elif col in {"有效样本数", "可用倍数数"}:
            display[col] = display[col].map(lambda value: "—" if pd.isna(value) else str(int(value)))
        else:
            display[col] = display[col].map(format_value)
    return display.to_markdown(index=False)


def clean_json(value: object) -> object:
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--codes", required=True, help="Comma list like '002371:北方华创,688012:中微公司'")
    parser.add_argument("--repo", default=".", help="Repository root containing factor_research/data_lake")
    parser.add_argument("--include-date", action="store_true", help="Keep 日期 in the markdown table")
    parser.add_argument("--analysis", action="store_true", help="Emit peer medians, deviations, and composite relative valuation labels")
    parser.add_argument("--json", action="store_true", help="Emit JSON records and warnings instead of markdown")
    args = parser.parse_args()

    codes = parse_codes(args.codes)
    df, warnings = build_snapshot(Path(args.repo).resolve(), codes)
    if not args.include_date and "日期" in df.columns:
        df = df.drop(columns=["日期"])

    median_df, deviation_df, summary_df = build_analysis(df)

    if args.json:
        payload = {"rows": df.to_dict("records"), "warnings": warnings}
        if args.analysis:
            payload.update(
                {
                    "medians": median_df.to_dict("records"),
                    "deviations": deviation_df.to_dict("records"),
                    "summary": summary_df.to_dict("records"),
                }
            )
        print(json.dumps(clean_json(payload), ensure_ascii=False, indent=2, allow_nan=False))
        return

    print(format_markdown(df))
    if args.analysis:
        print("\nPeer medians:")
        print(format_markdown(median_df))
        print("\nRelative deviations vs peer median:")
        print(format_markdown(deviation_df))
        print("\nComposite valuation position:")
        print(format_markdown(summary_df, percent_columns={"估值综合偏离%"}))
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")
    print("\nNotes:")
    print("- PE(2026E) is intentionally blank unless a real consensus forecast source is supplied.")
    print("- EV/EBITDA and PEG are local historical estimates, not vendor consensus metrics.")


if __name__ == "__main__":
    main()
