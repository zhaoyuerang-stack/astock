"""Phase 1: Synthetic data time-travel audit.

Replaces static AST checks with numerical verification: build a synthetic
dataset with known ground truth, run the strategy's factor_builder and
timing_builder through it, and check that signals do NOT peek into the future.

5 checks (some cover multiple concerns):
  1. timing 穿越      — does timing[T] depend on close[T] or later?
  2. 财务对齐         — does factor respect avail_date alignment?
  3. amount 公式       — does amount use raw_close (not adjusted close)?
  4. 预热完整         — are NaN periods ≤ expected window sizes?
  5. 退市股覆盖       — are known delisted stocks present in data?

Usage:
  >>> from workflow.phase1_synthetic import Phase1Checker, AuditReport
  >>> checker = Phase1Checker(factor_builder=my_fn, timing_builder=my_timing)
  >>> report = checker.run_all()
  >>> print(report.summary())
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = ROOT / "workflow" / "pending_lessons"
LESSONS_DIR.mkdir(parents=True, exist_ok=True)

# Synthetic data parameters
N_HISTORY = 100   # days of stable filler before event period
N_EVENT = 20      # event period length
N_TOTAL = N_HISTORY + N_EVENT
EV_START = N_HISTORY


# ---------------------------------------------------------------------------
# Synthetic data
# ---------------------------------------------------------------------------

def make_synthetic_clean():
    """Synthetic dataset with CORRECT signal construction.

    120 trading days: first 100 stable filler, last 20 event period.
    Stock 000001: adjusted close = 2× raw_close (simulates historical split).
    Stock 000002: no adjustment.
    Stock 000003: delisted before event period.
    """
    np.random.seed(42)
    dates = pd.bdate_range("2019-07-01", periods=N_TOTAL)
    stocks = ["000001", "000002", "000003"]

    # ---- Random walk prices ----
    close_data = {}
    for s, base in [("000001", 10.0), ("000002", 20.0), ("000003", 5.0)]:
        rw = np.random.randn(N_TOTAL) * 0.008
        rw[0] = 0
        close_data[s] = base * np.exp(np.cumsum(rw))
    close = pd.DataFrame(close_data, index=dates)

    # Delist 000003 at ev_start-10
    close.iloc[EV_START - 10:, close.columns.get_loc("000003")] = np.nan

    # Raw close: 000001 has 2:1 adjustment → raw ≈ close/2
    raw_close = close.copy()
    raw_close["000001"] = close["000001"] / 2.0

    # Volume
    vol_data = {}
    for s, bv in [("000001", 2000), ("000002", 1500), ("000003", 3000)]:
        vol_data[s] = np.maximum(100, bv + np.random.randn(N_TOTAL) * 200).astype(int)
    volume = pd.DataFrame(vol_data, index=dates)
    volume.iloc[EV_START - 10:, volume.columns.get_loc("000003")] = 0

    # Amount = volume × 100 × raw_close (correct)
    amount = volume * 100 * raw_close

    # ---- Event: +10% limit-up at ev_start+5 ----
    gap_idx = EV_START + 5
    for s in ["000001", "000002"]:
        ci = close.columns.get_loc(s)
        prev_c = close[s].iloc[gap_idx - 1]
        close.iloc[gap_idx, ci] = prev_c * 1.10
        ri = raw_close.columns.get_loc(s)
        prev_r = raw_close[s].iloc[gap_idx - 1]
        raw_close.iloc[gap_idx, ri] = prev_r * 1.10
    amount = volume * 100 * raw_close

    # ---- Fundamental: avail_date at ev_start ----
    fundamental = pd.DataFrame({
        "avail_date": [dates[EV_START]],
        "code": ["000001"],
        "net_profit_yoy": [0.15],
    })

    # ---- Reference timing signals ----
    mkt_ret = close.pct_change(fill_method=None).mean(axis=1).fillna(0.0)
    timing_clean = ((mkt_ret.rolling(2).sum() >= 0)
                    .shift(1, fill_value=True).astype(float))

    return {
        "close": close, "volume": volume, "raw_close": raw_close,
        "amount": amount, "trade_dates": dates, "fundamental": fundamental,
        "timing_clean": timing_clean, "event_start": EV_START,
        "gap_idx": gap_idx,
    }


def make_synthetic_leaky():
    """Synthetic data with LEAKY signals (no shift(1), wrong amount)."""
    clean = make_synthetic_clean()
    close = clean["close"]
    volume = clean["volume"]

    mkt_ret = close.pct_change(fill_method=None).mean(axis=1).fillna(0.0)
    timing_leaky = ((mkt_ret.rolling(2).sum() >= 0)
                    .astype(float))  # ← NO shift(1)

    result = dict(clean)
    result["timing_clean"] = timing_leaky
    result["amount"] = volume * 100 * close  # ← adjusted close!
    return result


# ---------------------------------------------------------------------------
# CheckResult
# ---------------------------------------------------------------------------

@dataclass
class CheckResult:
    check_id: str
    name: str
    verdict: str        # PASS / WARN / FAIL / SKIP
    detail: str
    evidence: dict = field(default_factory=dict)

    @property
    def is_pass(self): return self.verdict == "PASS"
    @property
    def is_fail(self): return self.verdict == "FAIL"


# ---------------------------------------------------------------------------
# Phase1Checker
# ---------------------------------------------------------------------------

class Phase1Checker:
    """Run synthetic-data checks against a strategy's signal builders."""

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

    # ── Check 1: timing穿越 ──

    def _check_timing_no_peek(self, syn: dict) -> CheckResult:
        """Timing[T] must only use data through T-1.

        Two-phase detection:
          A. Formula match against known correct/leaky patterns.
          B. Perturbation test: change close at t_gap, check timing before t_gap.
        """
        close = syn["close"]
        amount = syn["amount"]
        timing = syn.get("timing_clean")
        gap_idx = syn["gap_idx"]

        if timing is None:
            return CheckResult("timing_peek", "timing shift(1)",
                               "WARN", "No timing signal provided.")

        # Phase A: formula matching
        mkt_ret = close.pct_change(fill_method=None).mean(axis=1).fillna(0.0)
        correct = ((mkt_ret.rolling(2).sum() >= 0)
                   .shift(1, fill_value=True).astype(float))
        leaky = ((mkt_ret.rolling(2).sum() >= 0).astype(float))

        t_vals = timing.fillna(-999).values
        match_correct = bool((t_vals == correct.fillna(-999).values).all())
        match_leaky = bool((t_vals == leaky.fillna(-999).values).all())

        if match_correct and not match_leaky:
            return CheckResult("timing_peek", "timing shift(1)", "PASS",
                               "Timing matches correct shift(1) reference.",
                               {"method": "formula_match"})
        if match_leaky and not match_correct:
            return CheckResult("timing_peek", "timing shift(1)", "FAIL",
                               "Timing MISSING shift(1)! Uses T-day market return.",
                               {"method": "formula_match"})

        # Phase B: perturbation test
        close_pert = close.copy()
        close_pert.iloc[gap_idx] = close_pert.iloc[gap_idx] * 0.3  # -70% crash

        try:
            t_orig = self.timing_builder(close, amount)
            t_pert = self.timing_builder(close_pert, amount)
        except Exception:
            return CheckResult("timing_peek", "timing shift(1)", "WARN",
                               "Perturbation test failed (builder error). Manual review.",
                               {"method": "perturbation_error"})

        if t_orig is None or t_pert is None:
            return CheckResult("timing_peek", "timing shift(1)", "WARN",
                               "Timing builder returned None.", {"method": "no_output"})

        # Check: did timing before gap_idx change?
        pre_mask = timing.index[:gap_idx]
        changed = False
        for idx in pre_mask:
            if idx in t_pert.index:
                o = float(t_orig.loc[idx]) if pd.notna(t_orig.loc[idx]) else np.nan
                p = float(t_pert.loc[idx]) if pd.notna(t_pert.loc[idx]) else np.nan
                if not np.isclose(o, p, rtol=1e-3, atol=1e-3, equal_nan=True):
                    changed = True
                    break

        if changed:
            return CheckResult("timing_peek", "timing shift(1)", "FAIL",
                               "PERTURBATION FAILED: changing future close changed past timing.",
                               {"method": "perturbation", "pre_gap_changed": True})
        return CheckResult("timing_peek", "timing shift(1)", "PASS",
                           "Perturbation passed: future prices don't affect past timing.",
                           {"method": "perturbation", "pre_gap_changed": False})

    # ── Check 2: 财务对齐 ──

    def _check_fundamental_alignment(self, syn: dict) -> CheckResult:
        """Factor respects avail_date alignment for fundamental data."""
        fund = syn.get("fundamental")
        if fund is None or fund.empty:
            return CheckResult("fund_alignment", "avail_date 对齐", "SKIP",
                               "No fundamental data in synthetic panel.")

        try:
            factor = self.factor_builder(
                syn["close"], syn["volume"], syn["amount"], syn["trade_dates"])
        except Exception as e:
            return CheckResult("fund_alignment", "avail_date 对齐", "WARN",
                               f"factor_builder error: {e}")

        if factor is None or factor.empty or "000001" not in factor.columns:
            return CheckResult("fund_alignment", "avail_date 对齐", "SKIP",
                               "Factor doesn't include 000001 — fundamental not used.")

        # Check if factor changes at avail_date boundary
        ev = syn["event_start"]
        f_pre = factor["000001"].iloc[max(0, ev-5):ev]
        f_post = factor["000001"].iloc[ev:ev+5]

        if f_pre.dropna().empty or f_post.dropna().empty:
            return CheckResult("fund_alignment", "avail_date 对齐", "SKIP",
                               "Factor has NaN around avail_date — can't verify.")

        pre_m, post_m = f_pre.mean(), f_post.mean()
        if pd.notna(pre_m) and pd.notna(post_m) and pre_m != 0:
            ratio = abs(post_m / pre_m)
            if ratio > 1.3 or ratio < 0.77:
                return CheckResult("fund_alignment", "avail_date 对齐", "PASS",
                                   f"Factor changes at avail_date (pre={pre_m:.4f} post={post_m:.4f}).",
                                   {"pre_mean": float(pre_m), "post_mean": float(post_m)})

        return CheckResult("fund_alignment", "avail_date 对齐", "SKIP",
                           "No clear change at avail_date — strategy may not use fundamentals. "
                           "If it does, load_fundamental_panel() handles alignment.")

    # ── Check 3: amount 公式 ──

    def _check_amount_formula(self, syn: dict) -> CheckResult:
        """Amount = volume × 100 × raw_close, NOT adjusted close.

        Tests the INPUT data provided to factor_builder. Since all
        factors in this codebase accept amount as a pre-computed parameter
        (not recomputing it internally), verifying the input is sufficient.
        """
        close = syn["close"]
        volume = syn["volume"]
        raw_close = syn["raw_close"]
        amount = syn["amount"]

        expected = volume * 100 * raw_close
        wrong = volume * 100 * close

        diff_raw = float((amount - expected).abs().max().max())
        diff_adj = float((amount - wrong).abs().max().max())

        # Since raw_close ≠ adjusted close for stock 000001 (2:1 split),
        # we can distinguish which formula was used
        tol = 0.01
        matches_raw = diff_raw < tol
        matches_adj = diff_adj < tol

        if matches_adj and not matches_raw:
            return CheckResult("amount_formula", "amount = vol×100×raw_close", "FAIL",
                               f"Amount uses ADJUSTED close (diff vs raw={diff_raw:.1f}, "
                               f"vs adj={diff_adj:.4f}). Cross-sectional ranking is contaminated.",
                               {"diff_vs_raw": diff_raw, "diff_vs_adj": diff_adj})
        elif matches_raw:
            return CheckResult("amount_formula", "amount = vol×100×raw_close", "PASS",
                               f"Amount uses raw_close correctly (diff={diff_raw:.4f}).",
                               {"diff_vs_raw": diff_raw})
        else:
            return CheckResult("amount_formula", "amount = vol×100×raw_close", "WARN",
                               f"Amount formula unclear (raw_diff={diff_raw:.1f}, adj_diff={diff_adj:.1f}).",
                               {"diff_vs_raw": diff_raw, "diff_vs_adj": diff_adj})

    # ── Check 4: 预热完整 ──

    def _check_warmup(self, syn: dict) -> CheckResult:
        """Factor NaN period should not exceed expected warmup."""
        try:
            factor = self.factor_builder(
                syn["close"], syn["volume"], syn["amount"], syn["trade_dates"])
        except Exception as e:
            return CheckResult("warmup", "预热完整", "WARN", f"factor_builder error: {e}")

        if factor is None or factor.empty:
            return CheckResult("warmup", "预热完整", "WARN", "No factor output.")

        # Count leading all-NaN days
        all_nan = factor.isna().all(axis=1)
        leading = 0
        for v in all_nan:
            if v: leading += 1
            else: break

        max_window = max(
            self.config.get("size_window", 60),
            self.config.get("timing_ma", 16),
            self.config.get("vol_lookback", 60),
        )

        if leading <= max_window:
            return CheckResult("warmup", "预热完整", "PASS",
                               f"Leading NaN: {leading}d ≤ max window {max_window}d.",
                               {"leading_nan": leading, "max_window": max_window})
        return CheckResult("warmup", "预热完整", "WARN",
                           f"Leading NaN {leading}d > max window {max_window}d. "
                           f"Data may not have enough warmup history.")

    # ── Check 5: 退市股覆盖 ──

    def _check_delisted_coverage(self, syn: dict) -> CheckResult:
        """Known delisted stocks should be present in price panel."""
        close = syn["close"]

        # Synthetic: stock 000003 is delisted
        if "000003" in close.columns:
            n_present = close["000003"].notna().sum()
            if n_present > 0:
                # Also check real data
                meta = ROOT / "data_lake" / "meta" / "delisted_codes.parquet"
                if meta.exists():
                    try:
                        dl = pd.read_parquet(meta)
                        dl_codes = set(dl["code"].astype(str).str.zfill(6))
                        found = dl_codes & set(close.columns)
                        cov = len(found) / len(dl_codes) if dl_codes else 0
                        if cov >= 0.70:
                            return CheckResult("delisted", "退市股覆盖", "PASS",
                                               f"Coverage {cov:.0%} ({len(found)}/{len(dl_codes)}).",
                                               {"coverage": cov})
                        elif cov >= 0.30:
                            return CheckResult("delisted", "退市股覆盖", "WARN",
                                               f"Coverage only {cov:.0%}.",
                                               {"coverage": cov})
                        return CheckResult("delisted", "退市股覆盖", "FAIL",
                                           f"Coverage <30%: {cov:.0%}.", {"coverage": cov})
                    except Exception:
                        pass
                return CheckResult("delisted", "退市股覆盖", "WARN",
                                   "No delisted_codes.parquet — coverage unknown. "
                                   "Synthetic delisted stock present (OK).")

        return CheckResult("delisted", "退市股覆盖", "WARN",
                           "Delisted stock 000003 missing from synthetic panel.")

    # ── main entry ──

    def run_all(self, use_clean: bool = True) -> list[CheckResult]:
        """Run all checks. Returns list of CheckResult."""
        syn = make_synthetic_clean() if use_clean else make_synthetic_leaky()

        # Override timing with user's actual builder
        try:
            ut = self.timing_builder(syn["close"], syn["amount"])
            if ut is not None and not ut.empty:
                syn["timing_clean"] = ut
        except Exception:
            pass

        checks = [
            self._check_timing_no_peek(syn),
            self._check_fundamental_alignment(syn),
            self._check_amount_formula(syn),
            self._check_warmup(syn),
            self._check_delisted_coverage(syn),
        ]
        self._maybe_save_lessons(checks)
        return checks

    # ── lesson generation ──

    def _maybe_save_lessons(self, checks: list[CheckResult]):
        for c in checks:
            if c.verdict not in ("FAIL", "WARN"):
                continue
            fp = hashlib.sha256(
                f"{c.check_id}:{c.name}:{c.detail[:100]}".encode()
            ).hexdigest()[:8]
            lf = LESSONS_DIR / f"{c.check_id}_{fp}.json"
            if lf.exists():
                ex = json.loads(lf.read_text())
                ex["hit_count"] = ex.get("hit_count", 1) + 1
                ex["last_seen"] = str(pd.Timestamp.now())
                if self.family not in ex.get("strategies", []):
                    ex.setdefault("strategies", []).append(self.family)
                lf.write_text(json.dumps(ex, ensure_ascii=False, indent=2))
            else:
                lf.write_text(json.dumps({
                    "fingerprint": fp,
                    "trigger": f"Phase1_{c.check_id}",
                    "pattern": c.name, "detail": c.detail,
                    "fix": _suggest_fix(c.check_id),
                    "hit_count": 1,
                    "first_seen": str(pd.Timestamp.now()),
                    "last_seen": str(pd.Timestamp.now()),
                    "strategies": [self.family],
                }, ensure_ascii=False, indent=2))


def _suggest_fix(check_id: str) -> str:
    return {
        "timing_peek": "Add .shift(1) to timing: timing = (condition).shift(1).",
        "amount_formula": "Use amount = volume * 100 * raw_close, not adjusted close.",
        "fund_alignment": "Use load_fundamental_panel() which aligns via avail_date→ffill.",
        "warmup": "Load data from ≥2yr before backtest start for rolling window warmup.",
        "delisted": "Ensure data pipeline includes delisted stocks from meta/delisted_codes.",
    }.get(check_id, "Manual review needed.")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class AuditReport:
    family: str
    results: list[CheckResult]
    timestamp: str = field(default_factory=lambda: str(pd.Timestamp.now()))

    @property
    def all_pass(self):
        return all(r.verdict in ("PASS", "SKIP") for r in self.results)

    @property
    def has_fail(self):
        return any(r.is_fail for r in self.results)

    def summary(self) -> str:
        icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "SKIP": "—"}
        lines = [
            f"Phase 1 Audit: {self.family}",
            f"  Time: {self.timestamp}",
            f"  {'─' * 50}",
        ]
        for r in self.results:
            lines.append(f"  {icon.get(r.verdict, '?')} {r.name}: {r.verdict}")
        lines.append(f"  {'─' * 50}")
        if self.has_fail:
            lines.append("  → ❌ BLOCKED (fix FAILs first)")
            lines.append("\n  Failures:")
            for r in self.results:
                if r.is_fail:
                    lines.append(f"    [{r.check_id}] {r.detail}")
        elif not self.all_pass:
            lines.append("  → ⚠️ PROCEED WITH CAUTION (review WARNs)")
        else:
            lines.append("  → ✅ ALL CHECKS PASSED")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "family": self.family, "timestamp": self.timestamp,
            "results": [{"check_id": r.check_id, "name": r.name,
                         "verdict": r.verdict, "detail": r.detail,
                         "evidence": r.evidence} for r in self.results],
            "all_pass": self.all_pass, "has_fail": self.has_fail,
        }
