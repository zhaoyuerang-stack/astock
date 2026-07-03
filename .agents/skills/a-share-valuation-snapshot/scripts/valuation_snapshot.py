#!/usr/bin/env python3
"""Build a guarded A-share valuation snapshot from factor_research/data_lake.

This script is read-only. It does not fetch or update market data.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
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
INDEX_COMPONENTS = [
    "财务质量",
    "增长可信度",
    "估值吸引力",
    "风险惩罚",
    "数据可信度",
    "买入指数",
]


def normalize_code(code: object) -> str:
    text = str(code).strip()
    if "." in text:
        text = text.split(".", 1)[0]
    if len(text) != 6 or not text.isdigit():
        raise SystemExit(f"Invalid A-share code: {text!r}")
    return text


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
        code = normalize_code(code)
        out[code] = name.strip() or code
    if not out:
        raise SystemExit("No codes supplied. Use --codes or --codes-file.")
    return out


def parse_codes_file(path: Path) -> dict[str, str]:
    """Read a stock universe from CSV/TSV or plain text.

    Accepted shapes:
    - CSV/TSV with columns: code/name, ts_code/name, 股票代码/公司
    - CSV/TSV without a header: first column code, second column optional name
    - Plain text: one "code[:name]" or "code,name" per line
    """
    if not path.exists():
        raise SystemExit(f"codes file not found: {path}")
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        raise SystemExit(f"codes file is empty: {path}")

    delimiter = "\t" if "\t" in text.splitlines()[0] else ","
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    header = [cell.strip().lower() for cell in rows[0]]
    code_keys = {"code", "ts_code", "symbol", "股票代码", "证券代码", "代码"}
    name_keys = {"name", "company", "stock_name", "股票名称", "证券简称", "公司", "公司名称", "名称"}
    has_header = bool(set(header) & code_keys)

    out: dict[str, str] = {}
    if has_header:
        code_idx = next(i for i, cell in enumerate(header) if cell in code_keys)
        name_idx = next((i for i, cell in enumerate(header) if cell in name_keys), None)
        data_rows = rows[1:]
    else:
        code_idx = 0
        name_idx = 1 if len(rows[0]) > 1 else None
        data_rows = rows

    for row in data_rows:
        if not row or not row[0].strip():
            continue
        if len(row) == 1 and (":" in row[0] or "：" in row[0]):
            code, name = row[0].replace("：", ":", 1).split(":", 1)
        else:
            if code_idx >= len(row):
                continue
            code = row[code_idx]
            name = row[name_idx] if name_idx is not None and name_idx < len(row) else code
        normalized = normalize_code(code)
        out[normalized] = str(name).strip() or normalized
    if not out:
        raise SystemExit(f"codes file contains no valid A-share codes: {path}")
    return out


def merge_code_inputs(raw_codes: str | None, codes_file: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if codes_file:
        out.update(parse_codes_file(Path(codes_file)))
    if raw_codes:
        out.update(parse_codes(raw_codes))
    if not out:
        raise SystemExit("No codes supplied. Provide --codes or --codes-file.")
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


def asof_from_date(date_value: object) -> int | None:
    if date_value is None:
        return None
    text = str(date_value).replace("-", "")
    return int(text) if text.isdigit() else None


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


def clip(value: float | None, low: float = 0.0, high: float = 100.0) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return min(high, max(low, value))


def score_linear(value: float | None, bad: float, good: float, higher_better: bool = True) -> float | None:
    if value is None or not math.isfinite(value) or bad == good:
        return None
    raw = (value - bad) / (good - bad) * 100.0
    if not higher_better:
        raw = 100.0 - raw
    return clip(raw)


def mean_available(values: Iterable[float | None]) -> float | None:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return sum(clean) / len(clean) if clean else None


def max_available(values: Iterable[float | None]) -> float | None:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return max(clean) if clean else None


def percentile_scores(values: dict[str, float | None], higher_better: bool = True) -> dict[str, float | None]:
    series = pd.Series({k: v for k, v in values.items() if v is not None and math.isfinite(float(v))}, dtype=float)
    if series.empty:
        return {k: None for k in values}
    ranks = series.rank(pct=True, method="average")
    if len(series) == 1:
        ranks[:] = 0.5
    scores = ranks * 100.0 if higher_better else (1.0 - ranks) * 100.0
    return {k: (float(scores[k]) if k in scores else None) for k in values}


def latest_report_row(df: pd.DataFrame, code: str, asof: int | None) -> pd.Series | None:
    if df.empty or asof is None:
        return None
    work = df.copy()
    work["code"] = work["ts_code"].astype(str).str.split(".").str[0]
    work["ann_i"] = pd.to_numeric(work.get("ann_date"), errors="coerce")
    work["end_i"] = pd.to_numeric(work.get("end_date"), errors="coerce")
    work = work[(work["code"] == code) & (work["ann_i"] <= asof)].dropna(subset=["ann_i", "end_i"])
    if work.empty:
        return None
    return work.sort_values(["ann_i", "end_i"]).iloc[-1]


def prior_year_same_row(df: pd.DataFrame, code: str, latest_row: pd.Series | None) -> pd.Series | None:
    if df.empty or latest_row is None or pd.isna(latest_row.get("end_i")):
        return None
    end_text = str(int(latest_row["end_i"]))
    target = int(f"{int(end_text[:4]) - 1}{end_text[4:]}")
    work = df.copy()
    work["code"] = work["ts_code"].astype(str).str.split(".").str[0]
    work["ann_i"] = pd.to_numeric(work.get("ann_date"), errors="coerce")
    work["end_i"] = pd.to_numeric(work.get("end_date"), errors="coerce")
    work = work[(work["code"] == code) & (work["end_i"] == target)].dropna(subset=["ann_i", "end_i"])
    if work.empty:
        return None
    return work.sort_values(["ann_i", "end_i"]).iloc[-1]


def row_float(row: pd.Series | None, field: str) -> float | None:
    if row is None or field not in row:
        return None
    return numeric_or_none(row.get(field))


def yoy_from_rows(latest: pd.Series | None, prior: pd.Series | None, field: str) -> float | None:
    current = row_float(latest, field)
    previous = row_float(prior, field)
    if current is None or previous is None or previous == 0:
        return None
    return (current / abs(previous) - 1.0) * 100.0


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


def build_buy_index(repo: Path, snapshot: pd.DataFrame, summary: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    lake = repo / "factor_research" / "data_lake"
    indicator = maybe_read(lake / "financials" / "fina_indicator_all.parquet")
    income = maybe_read(lake / "financials" / "income_all.parquet")
    balance = maybe_read(lake / "financials" / "balancesheet_all.parquet")
    cashflow = maybe_read(lake / "financials" / "cashflow_all.parquet")

    latest_market_date = max(asof_from_date(d) or 0 for d in snapshot.get("日期", pd.Series(dtype=object)).dropna())
    premium_by_code = summary.set_index("代码")["估值综合偏离%"].to_dict() if not summary.empty else {}

    raw_metrics: dict[str, dict[str, float | None]] = {}
    for _, snap in snapshot.iterrows():
        code = str(snap.get("代码"))
        asof = asof_from_date(snap.get("日期"))
        ind = latest_report_row(indicator, code, asof)
        ind_prior = prior_year_same_row(indicator, code, ind)
        bal = latest_report_row(balance, code, asof)
        bal_prior = prior_year_same_row(balance, code, bal)
        cf_ttm, _ = ttm_from_cumulative(cashflow, code, "n_cashflow_act", asof or 0)
        ni_ttm, _ = ttm_from_cumulative(income, code, "n_income", asof or 0)
        fcf_ttm, _ = ttm_from_cumulative(cashflow, code, "free_cashflow", asof or 0)

        receivable_yoy = yoy_from_rows(bal, bal_prior, "accounts_receiv")
        inventory_yoy = yoy_from_rows(bal, bal_prior, "inventories")
        revenue_yoy = row_float(ind, "or_yoy")
        netprofit_yoy = row_float(ind, "netprofit_yoy")
        margin_trend = None
        if row_float(ind, "grossprofit_margin") is not None and row_float(ind_prior, "grossprofit_margin") is not None:
            margin_trend = row_float(ind, "grossprofit_margin") - row_float(ind_prior, "grossprofit_margin")

        cash_to_profit = None
        if cf_ttm is not None and ni_ttm is not None and ni_ttm != 0:
            cash_to_profit = cf_ttm / abs(ni_ttm)
        net_cash_ratio = None
        cash = row_float(bal, "money_cap")
        debt = (row_float(bal, "st_borr") or 0.0) + (row_float(bal, "lt_borr") or 0.0)
        market_cap_yi = numeric_or_none(snap.get("市值"))
        if cash is not None and market_cap_yi and market_cap_yi > 0:
            net_cash_ratio = ((cash - debt) / 100000000.0) / market_cap_yi

        raw_metrics[code] = {
            "revenue_yoy": revenue_yoy,
            "netprofit_yoy": netprofit_yoy,
            "gross_margin": row_float(ind, "grossprofit_margin"),
            "net_margin": row_float(ind, "netprofit_margin"),
            "margin_trend": margin_trend,
            "receivable_yoy": receivable_yoy,
            "inventory_yoy": inventory_yoy,
            "debt_to_assets": row_float(ind, "debt_to_assets"),
            "current_ratio": row_float(ind, "current_ratio"),
            "assets_turn": row_float(ind, "assets_turn"),
            "ar_turn": row_float(ind, "ar_turn"),
            "cash_to_profit": cash_to_profit,
            "fcf_ttm": fcf_ttm,
            "net_cash_ratio": net_cash_ratio,
            "premium": numeric_or_none(premium_by_code.get(code)),
            "asof": float(asof) if asof else None,
            "ann_i": row_float(ind, "ann_i"),
        }

    revenue_scores = percentile_scores({c: m["revenue_yoy"] for c, m in raw_metrics.items()})
    profit_growth_scores = percentile_scores({c: m["netprofit_yoy"] for c, m in raw_metrics.items()})
    gross_margin_scores = percentile_scores({c: m["gross_margin"] for c, m in raw_metrics.items()})
    net_margin_scores = percentile_scores({c: m["net_margin"] for c, m in raw_metrics.items()})
    assets_turn_scores = percentile_scores({c: m["assets_turn"] for c, m in raw_metrics.items()})
    ar_turn_scores = percentile_scores({c: m["ar_turn"] for c, m in raw_metrics.items()})
    debt_scores = percentile_scores({c: m["debt_to_assets"] for c, m in raw_metrics.items()}, higher_better=False)

    rows: list[dict[str, object]] = []
    detail_rows: list[dict[str, object]] = []
    for _, snap in snapshot.iterrows():
        code = str(snap.get("代码"))
        name = snap.get("公司")
        m = raw_metrics.get(code, {})
        revenue_yoy = m.get("revenue_yoy")
        receivable_stress = score_linear((m.get("receivable_yoy") or 0.0) - (revenue_yoy or 0.0), 0, 80)
        inventory_stress = score_linear((m.get("inventory_yoy") or 0.0) - (revenue_yoy or 0.0), 0, 80)
        revenue_quality = mean_available([revenue_scores.get(code), 100 - (receivable_stress or 0), 100 - (inventory_stress or 0)])

        profit_quality = mean_available([gross_margin_scores.get(code), net_margin_scores.get(code), profit_growth_scores.get(code)])
        cashflow_quality = mean_available([
            score_linear(m.get("cash_to_profit"), 0.0, 1.2),
            75.0 if (m.get("fcf_ttm") or 0.0) > 0 else 35.0 if m.get("fcf_ttm") is not None else None,
        ])
        balance_strength = mean_available([
            debt_scores.get(code),
            score_linear(m.get("current_ratio"), 0.8, 2.5),
            score_linear(m.get("net_cash_ratio"), -0.2, 0.2),
        ])
        operating_efficiency = mean_available([assets_turn_scores.get(code), ar_turn_scores.get(code)])

        financial_quality = mean_available([
            0.25 * revenue_quality if revenue_quality is not None else None,
            0.25 * profit_quality if profit_quality is not None else None,
            0.25 * cashflow_quality if cashflow_quality is not None else None,
            0.15 * balance_strength if balance_strength is not None else None,
            0.10 * operating_efficiency if operating_efficiency is not None else None,
        ])
        if financial_quality is not None:
            # mean_available on weighted terms divides by count; rescale by expected five components.
            financial_quality = clip(financial_quality * 5.0)

        margin_signal = score_linear(m.get("margin_trend"), -5, 5)
        inventory_reasonable = 100 - (inventory_stress or 0) if m.get("inventory_yoy") is not None else None
        growth_credibility = mean_available([
            revenue_scores.get(code),
            profit_growth_scores.get(code),
            margin_signal,
            inventory_reasonable,
        ])

        premium = m.get("premium")
        valuation_attractiveness = None
        if premium is not None:
            valuation_attractiveness = 100.0 / (1.0 + math.exp(float(premium) / 35.0))

        cashflow_mismatch = score_linear(0.8 - (m.get("cash_to_profit") or 0.0), 0, 0.8) if m.get("cash_to_profit") is not None else None
        leverage_stress = score_linear(m.get("debt_to_assets"), 35, 80)
        data_staleness = None
        asof = asof_from_date(snap.get("日期"))
        if asof and latest_market_date:
            days = (pd.to_datetime(str(latest_market_date)) - pd.to_datetime(str(asof))).days
            data_staleness = clip(days * 8.0)
        risk_penalty = max_available([receivable_stress, inventory_stress, cashflow_mismatch, leverage_stress, data_staleness]) or 0.0
        risk_control = 100.0 - risk_penalty

        available_inputs = [
            revenue_quality,
            profit_quality,
            cashflow_quality,
            balance_strength,
            operating_efficiency,
            growth_credibility,
            valuation_attractiveness,
            risk_penalty,
        ]
        field_coverage = len([v for v in available_inputs if v is not None]) / len(available_inputs)
        freshness_score = 1.0 - ((data_staleness or 0.0) / 100.0)
        report_score = 1.0
        ann_i = m.get("ann_i")
        asof_i = asof_from_date(snap.get("日期"))
        if ann_i and asof_i:
            age_days = (pd.to_datetime(str(asof_i)) - pd.to_datetime(str(int(ann_i)))).days
            report_score = 1.0 if age_days <= 120 else 0.85 if age_days <= 240 else 0.70
        data_confidence = min(field_coverage, freshness_score, report_score)
        if valuation_attractiveness is None:
            data_confidence = min(data_confidence, 0.50)

        base_index = mean_available([
            0.30 * financial_quality if financial_quality is not None else None,
            0.25 * growth_credibility if growth_credibility is not None else None,
            0.30 * valuation_attractiveness if valuation_attractiveness is not None else None,
            0.15 * risk_control,
        ])
        if base_index is not None:
            base_index = clip(base_index * 4.0)
        final_index = clip((base_index or 0.0) * data_confidence)

        rows.append({
            "公司": name,
            "代码": code,
            "财务质量": financial_quality,
            "增长可信度": growth_credibility,
            "估值吸引力": valuation_attractiveness,
            "风险惩罚": risk_penalty,
            "数据可信度": data_confidence,
            "买入指数": final_index,
            "市值": snap.get("市值"),
        })
        detail_rows.append({
            "公司": name,
            "代码": code,
            "收入质量": revenue_quality,
            "利润质量": profit_quality,
            "现金流质量": cashflow_quality,
            "资产负债表": balance_strength,
            "运营效率": operating_efficiency,
            "估值溢价%": premium,
            "应收压力": receivable_stress,
            "存货压力": inventory_stress,
            "现金流错配": cashflow_mismatch,
            "杠杆压力": leverage_stress,
            "数据滞后惩罚": data_staleness,
        })

    index_df = pd.DataFrame(rows).sort_values("买入指数", ascending=False)
    detail_df = pd.DataFrame(detail_rows)
    return index_df, detail_df


def configure_plot_fonts() -> None:
    os.environ.setdefault("MPLCONFIGDIR", "/private/tmp/matplotlib")
    os.environ.setdefault("XDG_CACHE_HOME", "/private/tmp")
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            font_manager.fontManager.addfont(path)
            plt.rcParams["font.family"] = font_manager.FontProperties(fname=path).get_name()
            break
    plt.rcParams["axes.unicode_minus"] = False


def render_buy_index_png(index_df: pd.DataFrame, output_png: Path) -> None:
    configure_plot_fonts()
    import matplotlib.pyplot as plt
    import numpy as np

    if index_df.empty:
        raise SystemExit("No buy index rows to plot")

    output_png.parent.mkdir(parents=True, exist_ok=True)
    plot_df = index_df.copy()
    for col in ["财务质量", "估值吸引力", "风险惩罚", "买入指数", "市值", "数据可信度"]:
        plot_df[col] = pd.to_numeric(plot_df[col], errors="coerce")
    plot_df = plot_df.dropna(subset=["财务质量", "估值吸引力", "风险惩罚", "买入指数"])
    if plot_df.empty:
        raise SystemExit("No plottable buy index rows")

    sizes = np.sqrt(plot_df["市值"].fillna(plot_df["市值"].median()).clip(lower=1)) * 18
    fig, ax = plt.subplots(figsize=(12, 8), dpi=180)
    scatter = ax.scatter(
        plot_df["估值吸引力"],
        plot_df["财务质量"],
        s=sizes,
        c=plot_df["风险惩罚"],
        cmap="RdYlGn_r",
        vmin=0,
        vmax=100,
        alpha=0.82,
        edgecolors="#1F2937",
        linewidths=0.8,
    )
    ax.axvline(50, color="#9CA3AF", linewidth=1.2, linestyle="--")
    ax.axhline(60, color="#9CA3AF", linewidth=1.2, linestyle="--")
    ax.fill_between([50, 100], 60, 100, color="#DCFCE7", alpha=0.25)
    ax.fill_between([0, 50], 60, 100, color="#FEF3C7", alpha=0.25)
    ax.fill_between([50, 100], 0, 60, color="#E0F2FE", alpha=0.20)
    ax.fill_between([0, 50], 0, 60, color="#FEE2E2", alpha=0.20)

    for _, row in plot_df.iterrows():
        label = f"{row['公司']}\n{row['买入指数']:.0f}"
        ax.annotate(label, (row["估值吸引力"], row["财务质量"]), xytext=(5, 5), textcoords="offset points", fontsize=8)

    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xlabel("估值吸引力（越右越便宜/越有安全边际）")
    ax.set_ylabel("财务质量（越上越强）")
    ax.set_title("A股财报估值吸引力指数：质量 x 估值 x 风险", fontsize=15, pad=14)
    ax.text(75, 92, "重点观察区\n高质量 + 有估值吸引力", ha="center", va="center", fontsize=9, color="#166534")
    ax.text(25, 92, "好公司但贵\n需增长解释估值", ha="center", va="center", fontsize=9, color="#92400E")
    ax.text(75, 12, "便宜但质量弱\n警惕价值陷阱", ha="center", va="center", fontsize=9, color="#075985")
    ax.text(25, 12, "低质量 + 低吸引力", ha="center", va="center", fontsize=9, color="#991B1B")
    cbar = fig.colorbar(scatter, ax=ax, pad=0.015)
    cbar.set_label("风险惩罚（越红风险越高）")
    ax.grid(True, color="#E5E7EB", linewidth=0.8)
    fig.text(0.01, 0.015, "点大小=市值；指数为规则型财报估值吸引力，不是自动买卖建议。", fontsize=8, color="#4B5563")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    fig.savefig(output_png, format="png")
    plt.close(fig)


def explain_buy_index(index_df: pd.DataFrame, detail_df: pd.DataFrame) -> list[str]:
    if index_df.empty:
        return []
    detail = detail_df.set_index("代码") if not detail_df.empty else pd.DataFrame()
    lines: list[str] = []
    for _, row in index_df.iterrows():
        code = str(row["代码"])
        d = detail.loc[code] if code in detail.index else pd.Series(dtype=object)
        strengths: list[str] = []
        risks: list[str] = []
        if numeric_or_none(row.get("财务质量")) is not None and row["财务质量"] >= 70:
            strengths.append("财务质量较强")
        if numeric_or_none(row.get("估值吸引力")) is not None and row["估值吸引力"] >= 60:
            strengths.append("估值相对有吸引力")
        if numeric_or_none(row.get("增长可信度")) is not None and row["增长可信度"] >= 70:
            strengths.append("增长信号较强")
        if numeric_or_none(row.get("风险惩罚")) is not None and row["风险惩罚"] >= 55:
            risks.append("风险惩罚偏高")
        if numeric_or_none(row.get("数据可信度")) is not None and row["数据可信度"] < 0.75:
            risks.append("数据可信度打折")
        if numeric_or_none(d.get("应收压力")) is not None and d["应收压力"] >= 50:
            risks.append("应收压力偏高")
        if numeric_or_none(d.get("存货压力")) is not None and d["存货压力"] >= 50:
            risks.append("存货压力偏高")
        if numeric_or_none(d.get("现金流错配")) is not None and d["现金流错配"] >= 50:
            risks.append("现金流与利润错配")

        stance = "值得重点复核" if row["买入指数"] >= 70 else "可以观察" if row["买入指数"] >= 55 else "吸引力一般"
        strength_text = "、".join(strengths) if strengths else "未形成明显优势"
        risk_text = "；".join(risks) if risks else "主要风险项不突出"
        lines.append(f"- {row['公司']}：买入指数 {row['买入指数']:.1f}，{stance}。支撑项：{strength_text}。约束项：{risk_text}。")
    return lines


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
    parser.add_argument("--codes", help="Comma list like '000001:平安银行,600519:贵州茅台'. Overrides duplicate codes from --codes-file.")
    parser.add_argument("--codes-file", help="CSV/TSV/text stock universe. Use columns such as code/name or ts_code/name, or one code[:name] per line.")
    parser.add_argument("--repo", default=".", help="Repository root containing factor_research/data_lake")
    parser.add_argument("--include-date", action="store_true", help="Keep 日期 in the markdown table")
    parser.add_argument("--analysis", action="store_true", help="Emit peer medians, deviations, and composite relative valuation labels")
    parser.add_argument("--buy-index", action="store_true", help="Emit a rule-based attractiveness index, PNG quadrant chart, and explanations")
    parser.add_argument("--output-png", default="/private/tmp/a_share_buy_index.png", help="PNG output path for --buy-index")
    parser.add_argument("--json", action="store_true", help="Emit JSON records and warnings instead of markdown")
    args = parser.parse_args()

    codes = merge_code_inputs(args.codes, args.codes_file)
    repo = Path(args.repo).resolve()
    df_full, warnings = build_snapshot(repo, codes)
    df = df_full.copy()
    if not args.include_date and "日期" in df.columns:
        df = df.drop(columns=["日期"])

    median_df, deviation_df, summary_df = build_analysis(df_full)
    index_df = pd.DataFrame()
    detail_df = pd.DataFrame()
    if args.buy_index:
        index_df, detail_df = build_buy_index(repo, df_full, summary_df)

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
        if args.buy_index:
            payload.update(
                {
                    "buy_index": index_df.to_dict("records"),
                    "buy_index_details": detail_df.to_dict("records"),
                    "explanations": explain_buy_index(index_df, detail_df),
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
    if args.buy_index:
        png_path = Path(args.output_png).resolve()
        render_buy_index_png(index_df, png_path)
        print("\nBuy index:")
        print(format_markdown(index_df[["公司", "代码", *INDEX_COMPONENTS]]))
        print(f"\nPNG: {png_path}")
        print("\nExplanation:")
        for line in explain_buy_index(index_df, detail_df):
            print(line)
    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")
    print("\nNotes:")
    print("- PE(2026E) is intentionally blank unless a real consensus forecast source is supplied.")
    print("- EV/EBITDA and PEG are local historical estimates, not vendor consensus metrics.")


if __name__ == "__main__":
    main()
