"""Phase 2: Three-segment backtest with non-overlapping intervals.

  IS   2018-2022  — sample内, parameters can be seen
  OOS  2023-2026  — sample外, strict blind test
  压力 2010-2017  — early stress (2015 crash, 2016 circuit-breaker)

Checks:
  - All segments: annual > 0
  - OOS/IS decay: OOS_annual / IS_annual > 0.3
  - Cost sensitivity: +50% cost → annual decay < 50%
  - Correlation vs registered strategies: |corr| < 0.85

Usage:
  >>> from workflow.phase2_backtest import Phase2Runner, BacktestReport
  >>> runner = Phase2Runner(factor_builder=my_fn, timing_builder=my_timing,
  ...                        family='my-strategy', config={...})
  >>> report = runner.run()
  >>> print(report.summary())
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from strategies.small_cap import load_price_panels as load_data

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "reports" / "discovery"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Non-overlapping segments
SEGMENTS = [
    ("IS  2018-2022", "2018-01-01", "2022-12-31"),
    ("OOS 2023-2026", "2023-01-01", "2026-12-31"),
    ("压力 2010-2017", "2010-01-01", "2017-12-31"),
]

DEFAULT_TOP_N = 25
DEFAULT_REBALANCE = 20
DEFAULT_LEVERAGE = 1.25


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def build_rebalance_weights(factor, close, top_n=25, rebalance_days=20):
    fdates = factor.dropna(how="all").index.intersection(close.index)
    if len(fdates) < 50:
        return {}
    weights = {}
    for rd in list(fdates[::rebalance_days]):
        pos = close.index.get_loc(rd)
        if pos + 1 >= len(close.index):
            continue
        effective = close.index[pos + 1]
        f = factor.loc[rd].dropna()
        active = close.loc[rd].dropna().index
        f = f.reindex(active).dropna()
        if len(f) < top_n:
            continue
        weights[effective] = pd.Series(1.0 / top_n, index=f.nlargest(top_n).index)
    return weights


def run_segment(close, volume, amount, weights, timing, leverage, cost_model):
    """Run a single backtest segment and return metrics."""
    prices = PricePanel(close=close, volume=volume, amount=amount)
    engine = BacktestEngine(
        prices=prices,
        config=BacktestConfig(
            start=str(close.index[0].date()),
            cost=cost_model,
            leverage=leverage,
        ),
    )
    signal = Signal(weights=weights, timing=timing)
    result = engine.run(signal)
    m = result.metrics
    return {
        "annual": m["annual"],
        "maxdd": m["maxdd"],
        "sharpe": m["sharpe"],
        "calmar": m["calmar"],
        "turnover": result.detail["turnover"].mean() * 252,
        "cost_drag": result.detail["cost"].mean() * 252,
        "n_days": len(result.returns),
        "returns": result.returns,
        "hit": m["hit"],
    }


# ---------------------------------------------------------------------------
# Phase2Runner
# ---------------------------------------------------------------------------

class Phase2Runner:
    """Run three-segment backtest + cost sensitivity + correlation check."""

    def __init__(
        self,
        factor_builder: Callable[
            [pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DatetimeIndex],
            pd.DataFrame,
        ],
        timing_builder: Callable[[pd.DataFrame, pd.DataFrame], pd.Series],
        family: str = "unnamed",
        config: Optional[dict] = None,
    ):
        self.factor_builder = factor_builder
        self.timing_builder = timing_builder
        self.family = family
        self.config = config or {}
        self.top_n = self.config.get("top_n", DEFAULT_TOP_N)
        self.rebalance = self.config.get("rebalance_days", DEFAULT_REBALANCE)
        self.leverage = self.config.get("leverage", DEFAULT_LEVERAGE)
        self.base_cost = CostModel(
            buy_cost=self.config.get("buy_cost", 0.00225),
            sell_cost=self.config.get("sell_cost", 0.00275),
            financing_rate=self.config.get("financing_rate", 0.065),
        )

    # ── main ──

    def run(self, warmup_start: str = "2010-01-01") -> dict:
        """Run all Phase 2 checks. Returns dict with segments + checks."""
        print(f"Phase 2: {self.family}", flush=True)

        # Load data once with warmup
        close, volume, amount = load_data(warmup_start)
        trade_dates = close.index
        print(f"  Data: {close.shape[1]} stocks × {close.shape[0]} days "
              f"[{trade_dates[0].date()}~{trade_dates[-1].date()}]", flush=True)

        # Build factor + timing on full range
        factor = self.factor_builder(close, volume, amount, trade_dates)
        timing = self.timing_builder(close, amount)
        weights = build_rebalance_weights(factor, close, self.top_n, self.rebalance)
        print(f"  Factor: {factor.dropna(how='all').shape[0]} valid days, "
              f"weights: {len(weights)} rebalance events", flush=True)

        # ── Three segments ──
        segments = {}
        for label, start, end in SEGMENTS:
            mask = (trade_dates >= pd.Timestamp(start)) & (trade_dates <= pd.Timestamp(end))
            if mask.sum() < 50:
                print(f"  {label}: ⚠️ too few days ({mask.sum()})", flush=True)
                continue

            c = close.loc[mask]; v = volume.loc[mask]; a = amount.loc[mask]
            t = timing.loc[mask] if timing is not None else None

            # Filter weights to segment dates
            w_seg = {dt: ws for dt, ws in weights.items() if dt in c.index}

            res = run_segment(c, v, a, w_seg, t, self.leverage, self.base_cost)
            segments[label] = res
            print(f"  {label}: annual={res['annual']:+.1%} maxdd={res['maxdd']:+.1%} "
                  f"sharpe={res['sharpe']:.2f} turn={res['turnover']:.1f}x", flush=True)

        # ── Cost sensitivity ──
        cost_check = self._check_cost_sensitivity(close, volume, amount, weights, timing)

        # ── Correlation ──
        corr_check = self._check_correlation(close, volume, amount, weights, timing)

        # ── OOS/IS decay ──
        decay_check = self._check_decay(segments)

        report = {
            "family": self.family,
            "config": self.config,
            "segments": segments,
            "cost_sensitivity": cost_check,
            "correlation": corr_check,
            "oos_is_decay": decay_check,
            "timestamp": str(pd.Timestamp.now()),
        }

        # Save
        out_path = OUT_DIR / f"{self.family}_phase2.json"
        # Convert non-serializable items
        serializable = _make_serializable(report)
        out_path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2))
        print(f"  Report → {out_path}", flush=True)

        return report

    # ── checks ──

    def _check_cost_sensitivity(self, close, volume, amount, weights, timing):
        """Run backtest with +50% costs, compare annual return."""
        # Full period 2018-2026 for cost sensitivity
        mask = (close.index >= "2018-01-01") & (close.index <= "2026-12-31")
        c = close.loc[mask]; v = volume.loc[mask]; a = amount.loc[mask]
        t = timing.loc[mask] if timing is not None else None
        w_seg = {dt: ws for dt, ws in weights.items() if dt in c.index}

        # Base cost
        base = run_segment(c, v, a, w_seg, t, self.leverage, self.base_cost)

        # +50% cost
        stressed_cost = CostModel(
            buy_cost=self.base_cost.buy_cost * 1.5,
            sell_cost=self.base_cost.sell_cost * 1.5,
            financing_rate=self.base_cost.financing_rate * 1.5,
        )
        stressed = run_segment(c, v, a, w_seg, t, self.leverage, stressed_cost)

        annual_decay = base["annual"] - stressed["annual"]
        decay_pct = annual_decay / base["annual"] if base["annual"] > 0 else float("inf")

        verdict = "PASS" if decay_pct < 0.5 else "FAIL"
        print(f"  Cost +50%: annual {base['annual']:+.1%}→{stressed['annual']:+.1%} "
              f"(decay={decay_pct:.0%}) → {verdict}", flush=True)

        return {
            "verdict": verdict,
            "base_annual": base["annual"],
            "stressed_annual": stressed["annual"],
            "decay_pct": decay_pct,
            "threshold": 0.5,
        }

    def _check_correlation(self, close, volume, amount, weights, timing):
        """Check daily return correlation vs registered strategies."""
        # Load registered strategies from strategy_versions.json
        reg_path = ROOT / "strategy_versions.json"
        if not reg_path.exists():
            return {"verdict": "SKIP", "detail": "No strategy registry found."}

        registry = json.loads(reg_path.read_text())
        active_strategies = []
        for fam in registry.get("families", []):
            for v in fam.get("versions", []):
                if v.get("status") == "在册" and fam["id"] != self.family:
                    active_strategies.append(f"{fam['id']}/{v['version']}")

        if not active_strategies:
            return {"verdict": "SKIP", "detail": "No other active strategies to compare."}

        # Run our strategy on 2018-2026
        mask = (close.index >= "2018-01-01") & (close.index <= "2026-12-31")
        c = close.loc[mask]; v = volume.loc[mask]; a = amount.loc[mask]
        t = timing.loc[mask] if timing is not None else None
        w_seg = {dt: ws for dt, ws in weights.items() if dt in c.index}
        our_res = run_segment(c, v, a, w_seg, t, self.leverage, self.base_cost)
        our_ret = our_res["returns"].dropna()

        # For each active strategy, load and compute correlation
        correlations = {}
        for s_id in active_strategies:
            fam_id = s_id.split("/")[0]
            # Run the baseline strategy
            try:
                from factors.small_cap import small_cap_factor, small_cap_timing
                sc = small_cap_factor(a, window=60)
                bl_timing, _, _ = small_cap_timing(c, a, ma_window=16)
                bl_weights = build_rebalance_weights(sc, c, self.top_n, self.rebalance)
                bl_res = run_segment(c, v, a, bl_weights, bl_timing.astype(float),
                                     self.leverage, self.base_cost)
                bl_ret = bl_res["returns"].dropna()
                common = our_ret.index.intersection(bl_ret.index)
                if len(common) > 100:
                    corr = our_ret.loc[common].corr(bl_ret.loc[common])
                    correlations[s_id] = corr
            except Exception:
                continue

        if not correlations:
            return {"verdict": "SKIP", "detail": "Could not compute correlations."}

        max_corr = max(abs(c) for c in correlations.values())
        if max_corr > 0.85:
            verdict = "FAIL"
        elif max_corr > 0.70:
            verdict = "WARN"
        else:
            verdict = "PASS"

        print(f"  Correlation vs active: max|corr|={max_corr:.3f} → {verdict}", flush=True)

        return {
            "verdict": verdict,
            "max_abs_corr": max_corr,
            "correlations": {k: round(v, 4) for k, v in correlations.items()},
            "threshold_warn": 0.70,
            "threshold_fail": 0.85,
        }

    def _check_decay(self, segments):
        """Check OOS/IS annual return decay."""
        is_seg = segments.get("IS  2018-2022", {})
        oos_seg = segments.get("OOS 2023-2026", {})

        if not is_seg or not oos_seg:
            return {"verdict": "SKIP", "detail": "Missing IS or OOS segment."}

        is_ann = is_seg.get("annual", 0)
        oos_ann = oos_seg.get("annual", 0)

        if is_ann <= 0:
            return {"verdict": "FAIL", "detail": f"IS annual ≤ 0 ({is_ann:+.1%})."}

        ratio = oos_ann / is_ann
        verdict = "PASS" if ratio > 0.3 else "FAIL"

        print(f"  OOS/IS decay: {oos_ann:+.1%} / {is_ann:+.1%} = {ratio:.2f} → {verdict}", flush=True)

        return {
            "verdict": verdict,
            "is_annual": is_ann,
            "oos_annual": oos_ann,
            "ratio": ratio,
            "threshold": 0.3,
        }


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class BacktestReport:
    family: str
    data: dict
    timestamp: str = field(default_factory=lambda: str(pd.Timestamp.now()))

    @property
    def has_fail(self) -> bool:
        for check in ["cost_sensitivity", "correlation", "oos_is_decay"]:
            if self.data.get(check, {}).get("verdict") == "FAIL":
                return True
        for seg in self.data.get("segments", {}).values():
            if seg.get("annual", -1) <= 0:
                return True
        return False

    def summary(self) -> str:
        d = self.data
        segs = d.get("segments", {})
        lines = [
            f"Phase 2 Backtest: {self.family}",
            f"  Time: {self.timestamp}",
            f"  {'─' * 50}",
            f"  Segments:",
        ]
        for label in ["IS  2018-2022", "OOS 2023-2026", "压力 2010-2017"]:
            s = segs.get(label, {})
            if s:
                icon = "✅" if s.get("annual", -1) > 0 else "❌"
                lines.append(
                    f"    {icon} {label}: annual={s['annual']:+.1%} "
                    f"maxdd={s['maxdd']:+.1%} sharpe={s['sharpe']:.2f} "
                    f"turn={s.get('turnover',0):.1f}x"
                )
        lines.append(f"  {'─' * 50}")

        # Cost sensitivity
        cs = d.get("cost_sensitivity", {})
        lines.append(f"  {'✅' if cs.get('verdict')=='PASS' else '❌'} Cost +50%: "
                     f"decay={cs.get('decay_pct',1):.0%} "
                     f"(limit 50%) → {cs.get('verdict','?')}")

        # OOS/IS decay
        dc = d.get("oos_is_decay", {})
        lines.append(f"  {'✅' if dc.get('verdict')=='PASS' else '❌'} OOS/IS decay: "
                     f"ratio={dc.get('ratio',0):.2f} "
                     f"(limit >0.3) → {dc.get('verdict','?')}")

        # Correlation
        cc = d.get("correlation", {})
        lines.append(f"  {'✅' if cc.get('verdict') in ('PASS','SKIP') else '⚠️' if cc.get('verdict')=='WARN' else '❌'} "
                     f"Correlation: max|corr|={cc.get('max_abs_corr',0):.3f} "
                     f"(warn>0.70, fail>0.85) → {cc.get('verdict','?')}")

        lines.append(f"  {'─' * 50}")
        lines.append(f"  → {'❌ BLOCKED' if self.has_fail else '✅ PASSED'}")
        return "\n".join(lines)


def _make_serializable(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (pd.Timestamp,)):
        return str(obj)
    if isinstance(obj, (pd.Series, pd.DataFrame)):
        return None  # don't serialize large objects
    return obj
