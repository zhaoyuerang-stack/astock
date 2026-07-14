"""Validate whether industry median market-cap deviations identify A-share regimes.

This is an exploratory falsification study, not a production timing rule.  The
current industry mapping is a latest-active snapshot, so historical results are
explicitly marked non-PIT until a dated membership table is available.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
LAKE = ROOT / "data_lake"
DEFAULT_OUT = ROOT.parent / "reports" / "research" / "industry_cap_regime_validation"
BENCHMARK_CODES = ("000300.SH", "000905.SH", "000852.SH", "932000.CSI")


def _robust_z(panel: pd.DataFrame, window: int, min_periods: int) -> pd.DataFrame:
    center = panel.rolling(window, min_periods=min_periods).median()
    abs_dev = (panel - center).abs()
    mad = abs_dev.rolling(window, min_periods=min_periods).median()
    return (panel - center).div(1.4826 * mad.replace(0, np.nan))


def build_signal(
    daily_basic: pd.DataFrame,
    industry: pd.DataFrame,
    cap_field: str,
    window: int,
    min_periods: int,
) -> tuple[pd.DataFrame, dict]:
    mapping = industry[["code", "industry_l1_name"]].copy()
    mapping["code"] = mapping["code"].astype(str).str.zfill(6)
    mapping = mapping.drop_duplicates("code", keep="last")
    mapping = mapping[mapping["industry_l1_name"].ne("未知")]

    values = daily_basic[["ts_code", "trade_date", cap_field]].copy()
    values["code"] = values["ts_code"].str.split(".").str[0]
    values["date"] = pd.to_datetime(values["trade_date"].astype(str))
    values = values.merge(mapping, on="code", how="inner", validate="many_to_one")
    values = values[values[cap_field].gt(0)]
    values["log_cap"] = np.log(values[cap_field].astype(float))

    med = values.pivot_table(
        index="date", columns="industry_l1_name", values="log_cap", aggfunc="median"
    ).sort_index()
    counts = values.pivot_table(
        index="date", columns="industry_l1_name", values="code", aggfunc="nunique"
    ).reindex(med.index)
    med = med.where(counts.ge(5))
    z = _robust_z(med, window=window, min_periods=min_periods).clip(-8, 8)

    signal = pd.DataFrame(index=z.index)
    signal["level"] = z.median(axis=1, skipna=True)
    signal["breadth"] = z.gt(0).sum(axis=1).div(z.notna().sum(axis=1).replace(0, np.nan))
    signal["impulse_20d"] = signal["level"].diff(20)
    signal["industry_count"] = z.notna().sum(axis=1)
    signal["stock_count"] = counts.sum(axis=1, min_count=1)

    coverage = {
        "mapped_stock_count": int(mapping["code"].nunique()),
        "industry_count": int(mapping["industry_l1_name"].nunique()),
        "signal_start": str(signal.dropna(subset=["level"]).index.min().date()),
        "signal_end": str(signal.dropna(subset=["level"]).index.max().date()),
        "median_daily_stock_count": int(signal["stock_count"].median()),
    }
    return signal, coverage


def load_benchmark(path: Path) -> pd.Series:
    raw = pd.read_parquet(path, columns=["ts_code", "trade_date", "close"])
    raw = raw[raw["ts_code"].isin(BENCHMARK_CODES)].copy()
    raw["date"] = pd.to_datetime(raw["trade_date"].astype(str))
    close = raw.pivot_table(index="date", columns="ts_code", values="close", aggfunc="last")
    close = close.sort_index()
    # Average same-day returns, not normalized index levels.  The latter creates
    # artificial jumps whenever a younger index first enters the panel.
    daily_return = close.pct_change(fill_method=None).mean(axis=1, skipna=True)
    composite = (1.0 + daily_return.fillna(0.0)).cumprod()
    return composite.rename("benchmark")


def _event_starts(mask: pd.Series, cooldown: int = 20) -> pd.Series:
    starts = mask.fillna(False) & ~mask.shift(1, fill_value=False)
    accepted = pd.Series(False, index=mask.index)
    last_position = -cooldown - 1
    for position in np.flatnonzero(starts.to_numpy()):
        if position - last_position >= cooldown:
            accepted.iloc[position] = True
            last_position = position
    return accepted


def evaluate(signal: pd.DataFrame, benchmark: pd.Series) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    frame = signal.join(benchmark, how="inner").dropna(subset=["level", "breadth", "benchmark"])
    frame["ret_20d_trailing"] = frame["benchmark"].pct_change(20)
    frame["ret_60d_trailing"] = frame["benchmark"].pct_change(60)
    for horizon in (5, 20, 60):
        frame[f"fwd_{horizon}d"] = frame["benchmark"].shift(-horizon).div(frame["benchmark"]).sub(1)

    # The state observed after T close is only actionable from T+1.
    frame["bull_candidate"] = (
        frame["breadth"].gt(0.60) & frame["impulse_20d"].gt(0)
    ).shift(1, fill_value=False)
    frame["bear_candidate"] = (
        frame["breadth"].lt(0.40) & frame["impulse_20d"].lt(0)
    ).shift(1, fill_value=False)
    frame["baseline_bull"] = frame["ret_60d_trailing"].gt(0).shift(1, fill_value=False)
    frame["bull_transition"] = _event_starts(frame["bull_candidate"])
    frame["bear_transition"] = _event_starts(frame["bear_candidate"])

    valid = frame.dropna(subset=["fwd_20d", "fwd_60d"]).copy()
    valid["level_quintile"] = pd.qcut(valid["level"], 5, labels=False, duplicates="drop") + 1
    quintiles = valid.groupby("level_quintile").agg(
        n=("fwd_20d", "size"),
        mean_fwd_20d=("fwd_20d", "mean"),
        median_fwd_20d=("fwd_20d", "median"),
        positive_20d=("fwd_20d", lambda x: float(x.gt(0).mean())),
        mean_fwd_60d=("fwd_60d", "mean"),
        positive_60d=("fwd_60d", lambda x: float(x.gt(0).mean())),
    ).reset_index()

    def state_stats(mask: pd.Series) -> dict:
        subset = valid[mask.reindex(valid.index).fillna(False)]
        return {
            "n_days": int(len(subset)),
            "mean_fwd_20d": float(subset["fwd_20d"].mean()),
            "positive_20d": float(subset["fwd_20d"].gt(0).mean()),
            "mean_fwd_60d": float(subset["fwd_60d"].mean()),
            "positive_60d": float(subset["fwd_60d"].gt(0).mean()),
        }

    def period_stats(subset: pd.DataFrame) -> dict:
        if subset.empty:
            return {}
        return {
            "n_days": int(len(subset)),
            "level_fwd_20d_spearman": float(subset["level"].corr(subset["fwd_20d"], method="spearman")),
            "level_fwd_60d_spearman": float(subset["level"].corr(subset["fwd_60d"], method="spearman")),
            "breadth_fwd_20d_spearman": float(subset["breadth"].corr(subset["fwd_20d"], method="spearman")),
            "breadth_fwd_60d_spearman": float(subset["breadth"].corr(subset["fwd_60d"], method="spearman")),
        }

    correlations = {
        col: {
            f"fwd_{h}d_spearman": float(valid[col].corr(valid[f"fwd_{h}d"], method="spearman"))
            for h in (5, 20, 60)
        }
        for col in ("level", "breadth", "impulse_20d", "ret_60d_trailing")
    }
    stats = {
        "observations": int(len(valid)),
        "start": str(valid.index.min().date()),
        "end": str(valid.index.max().date()),
        "correlations": correlations,
        "states": {
            "all_days": state_stats(pd.Series(True, index=valid.index)),
            "bull_candidate": state_stats(valid["bull_candidate"]),
            "bear_candidate": state_stats(valid["bear_candidate"]),
            "baseline_bull": state_stats(valid["baseline_bull"]),
            "bull_transition": state_stats(valid["bull_transition"]),
            "bear_transition": state_stats(valid["bear_transition"]),
        },
        "periods": {
            "2012_2018": period_stats(valid.loc[:"2018-12-31"]),
            "2019_2026": period_stats(valid.loc["2019-01-01":]),
        },
        "top_minus_bottom_quintile_20d": float(
            quintiles.iloc[-1]["mean_fwd_20d"] - quintiles.iloc[0]["mean_fwd_20d"]
        ),
        "top_minus_bottom_quintile_60d": float(
            quintiles.iloc[-1]["mean_fwd_60d"] - quintiles.iloc[0]["mean_fwd_60d"]
        ),
    }
    return frame, stats, quintiles


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cap-field", choices=("circ_mv", "total_mv"), default="circ_mv")
    parser.add_argument("--window", type=int, default=756)
    parser.add_argument("--min-periods", type=int, default=252)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    daily = pd.read_parquet(
        LAKE / "daily_basic" / "daily_basic_all.parquet",
        columns=["ts_code", "trade_date", args.cap_field],
    )
    industry = pd.read_parquet(LAKE / "meta" / "industry.parquet")
    signal, coverage = build_signal(daily, industry, args.cap_field, args.window, args.min_periods)
    benchmark = load_benchmark(LAKE / "index" / "index_daily_all.parquet")
    frame, stats, quintiles = evaluate(signal, benchmark)

    frame.to_csv(args.output_dir / "daily_signal.csv", index_label="date")
    quintiles.to_csv(args.output_dir / "quintile_results.csv", index=False)
    result = {
        "status": "exploratory_non_pit",
        "cap_field": args.cap_field,
        "rolling_window_days": args.window,
        "minimum_periods": args.min_periods,
        "benchmark_codes": list(BENCHMARK_CODES),
        "coverage": coverage,
        "evaluation": stats,
        "known_bias": "industry mapping contains latest-active members only",
    }
    (args.output_dir / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
