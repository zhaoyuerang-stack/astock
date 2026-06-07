"""Phase 4: Strategy registration with reproducibility metadata.

Takes Phase 1-3 results, auto-generates registry entry, records:
  - data snapshot version
  - engine version
  - git commit
  - python/dependency versions

Also handles lesson feedback loop: FAIL/WARN results from earlier phases
automatically generate structured lesson drafts in pending_lessons/.

Usage:
  >>> from workflow.phase4_register import Phase4Register
  >>> reg = Phase4Register(family='my-strategy')
  >>> reg.register(phase1_results, phase2_results, phase3_results)
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
LESSONS_DIR = ROOT / "workflow" / "pending_lessons"
LESSONS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Reproducibility metadata
# ---------------------------------------------------------------------------

def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(ROOT), text=True,
        ).strip()
    except Exception:
        return "unknown"


def _data_snapshot() -> str:
    """Check key parquet files for last-modified info."""
    files = [
        ROOT / "data_lake" / "price" / "daily_all.parquet",
        ROOT / "data_lake" / "price" / "daily_raw_all.parquet",
        ROOT / "data_lake" / "fundamental_batch.parquet",
    ]
    snapshots = {}
    for fp in files:
        if fp.exists():
            mtime = pd.Timestamp(fp.stat().st_mtime, unit="s")
            snapshots[fp.name] = str(mtime.date())
    return json.dumps(snapshots)


def _python_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _dependency_versions() -> dict:
    deps = {}
    for lib in ["pandas", "numpy", "scipy"]:
        try:
            mod = __import__(lib)
            deps[lib] = getattr(mod, "__version__", "unknown")
        except Exception:
            deps[lib] = "not found"
    return deps


def reproducibility_meta() -> dict:
    return {
        "date": str(date.today()),
        "git_commit": _git_commit(),
        "python": _python_version(),
        "dependencies": _dependency_versions(),
        "data_snapshot": _data_snapshot(),
        "engine": "core.engine.BacktestEngine",
    }


# ---------------------------------------------------------------------------
# Lesson generation
# ---------------------------------------------------------------------------

def _fingerprint(trigger: str, pattern: str) -> str:
    return hashlib.sha256(f"{trigger}:{pattern}".encode()).hexdigest()[:8]


def _suggest_fix(check_id: str) -> str:
    return {
        "timing_peek": (
            "Add .shift(1) to timing signal: timing = (condition).shift(1). "
            "Verify timing[T] only uses data through T-1."
        ),
        "amount_formula": (
            "Use raw_close (not adjusted close) for amount: "
            "amount = volume * 100 * raw_close. "
            "Adjusted close embeds future corporate actions in historical prices."
        ),
        "fund_alignment": (
            "Use load_fundamental_panel() which aligns by avail_date->ffill. "
            "Do not load raw fundamental values without date alignment."
        ),
        "warmup": (
            "Load price data from >=2 years before backtest start. "
            f"For typical window=60, load from at least 2016 for a 2018 start."
        ),
        "delisted": (
            "Ensure data pipeline includes delisted stocks. "
            "Check data_lake/price/daily_all.parquet against meta/delisted_codes.parquet."
        ),
        "cost_sensitivity": (
            "Strategy too sensitive to trading costs. "
            "Reduce turnover (longer rebalance interval, fewer stocks) "
            "or find stronger alpha to absorb cost drag."
        ),
        "oos_is_decay": (
            "Significant performance decay from IS to OOS — possible overfitting. "
            "Simplify factor, reduce parameters, or add walk-forward validation."
        ),
        "correlation": (
            "Strategy highly correlated with existing strategy. "
            "Find orthogonal alpha source or accept role as diversification component."
        ),
        "wf_aggregate": (
            "Walk-Forward OOS aggregate failed. Strategy does not generalize. "
            "Simplify factor construction, reduce lookback windows, "
            "or verify no data leakage in factor/timing builders."
        ),
    }.get(check_id, "Manual review needed.")


def save_lessons_from_phases(phase1: list, phase2: dict, phase3: dict, family: str):
    """Extract FAIL/WARN results from all phases and save as lesson drafts."""
    lessons_saved = 0

    # Phase 1
    for r in (phase1 or []):
        if hasattr(r, 'verdict') and r.verdict in ("FAIL", "WARN"):
            _upsert_lesson(r.check_id, r.name, r.detail, family)
            lessons_saved += 1

    # Phase 2
    for check_key in ["cost_sensitivity", "oos_is_decay", "correlation"]:
        c = (phase2 or {}).get(check_key, {})
        if c.get("verdict") in ("FAIL", "WARN"):
            _upsert_lesson(check_key, check_key, c.get("detail", str(c)), family)
            lessons_saved += 1

    # Phase 2 segments
    for label, seg in (phase2 or {}).get("segments", {}).items():
        if seg.get("annual", 1) <= 0:
            _upsert_lesson("segment_negative", f"segment {label}",
                           f"Segment {label} annual={seg['annual']:+.1%}", family)
            lessons_saved += 1

    # Phase 3
    agg = (phase3 or {}).get("aggregate", {})
    if agg.get("verdict") == "FAIL":
        _upsert_lesson("wf_aggregate", "WF aggregate FAIL",
                       f"WF OOS annual={agg.get('annual',0):+.1%}, "
                       f"positive={agg.get('positive_windows',0)}/{agg.get('total_windows',0)}",
                       family)
        lessons_saved += 1

    for w in (phase3 or {}).get("windows", []):
        if w.get("oos_annual", 1) <= 0:
            _upsert_lesson("wf_negative_window",
                           f"WF negative window {w.get('test_start_year')}",
                           f"OOS annual={w['oos_annual']:+.1%} in {w['test_start_year']}",
                           family)
            lessons_saved += 1

    return lessons_saved


def _upsert_lesson(check_id: str, name: str, detail: str, family: str):
    """Create or merge a lesson draft."""
    fp = _fingerprint(check_id, name)
    lf = LESSONS_DIR / f"{check_id}_{fp}.json"

    if lf.exists():
        ex = json.loads(lf.read_text())
        ex["hit_count"] = ex.get("hit_count", 1) + 1
        ex["last_seen"] = str(date.today())
        if family not in ex.get("strategies", []):
            ex.setdefault("strategies", []).append(family)
        lf.write_text(json.dumps(ex, ensure_ascii=False, indent=2))
    else:
        lf.write_text(json.dumps({
            "fingerprint": fp,
            "trigger": f"Phase_{check_id}",
            "pattern": name,
            "detail": detail,
            "fix": _suggest_fix(check_id),
            "hit_count": 1,
            "first_seen": str(date.today()),
            "last_seen": str(date.today()),
            "strategies": [family],
        }, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

@dataclass
class RegistrationReport:
    family: str
    version: str
    registered: bool
    repro_meta: dict
    lessons_saved: int
    detail: str = ""

    def summary(self) -> str:
        icon = "✅" if self.registered else "❌"
        lines = [
            f"Phase 4 Register: {self.family}/{self.version}",
            f"  Registered: {icon} {self.detail}",
            f"  Lessons saved: {self.lessons_saved}",
            f"  Git: {self.repro_meta.get('git_commit','?')}",
            f"  Python: {self.repro_meta.get('python','?')}",
            f"  Data snapshot: {self.repro_meta.get('data_snapshot','?')}",
        ]
        return "\n".join(lines)


class Phase4Register:
    """Strategy registration with reproducibility tracking."""

    def __init__(self, family: str, version: str = "v1.0"):
        self.family = family
        self.version = version

    def register(
        self,
        phase1_results: list,
        phase2_data: dict,
        phase3_data: dict,
        hypothesis: str = "",
        regime: str = "",
        decay_signal: str = "",
        force: bool = False,
    ) -> RegistrationReport:
        """Register strategy. Saves lessons regardless; registers only if all clear or forced."""

        # Always save lessons
        n_lessons = save_lessons_from_phases(
            phase1_results, phase2_data, phase3_data, self.family
        )
        print(f"  Lessons saved: {n_lessons}", flush=True)

        # Reproducibility metadata
        repro = reproducibility_meta()

        # Check if registration is allowed
        blocked = self._check_blocked(phase1_results, phase2_data, phase3_data)
        if blocked and not force:
            print(f"  Registration BLOCKED: {blocked}", flush=True)
            print(f"  Use force=True to override.", flush=True)
            return RegistrationReport(
                family=self.family, version=self.version,
                registered=False, repro_meta=repro, lessons_saved=n_lessons,
                detail=f"Blocked: {blocked}",
            )

        # Build metrics from Phase 2+3
        metrics = self._build_metrics(phase2_data, phase3_data)
        config = self._build_config(phase2_data)

        # Write to registry
        try:
            from strategy_registry import register_family, register

            register_family(
                self.family,
                self.family,
                hypothesis=hypothesis,
                regime=regime,
                decay_signal=decay_signal,
            )
            register(
                self.family, self.version,
                desc=f"{self.family} v{self.version} — auto-registered via workflow",
                config=config,
                data_scope={
                    "source": "data_lake",
                    "period": "2010-2026",
                    "survivorship_bias": False,
                    "wf_validated": phase3_data.get("aggregate", {}).get("verdict") == "PASS",
                    "phase1_audited": not any(
                        hasattr(r, 'is_fail') and r.is_fail
                        for r in (phase1_results or [])
                    ),
                    "reproducibility": repro,
                },
                metrics=metrics,
                status="在册" if not blocked else "候选",
                notes=(
                    f"Workflow Phase 1-3 validated. "
                    f"WF: {phase3_data.get('aggregate',{}).get('annual',0):+.1%} ann / "
                    f"{phase3_data.get('aggregate',{}).get('maxdd',0):+.1%} dd."
                ),
            )
            print(f"  Registered: {self.family}/{self.version}", flush=True)
            return RegistrationReport(
                family=self.family, version=self.version,
                registered=True, repro_meta=repro, lessons_saved=n_lessons,
                detail="Registered successfully",
            )
        except Exception as e:
            print(f"  Registration error: {e}", flush=True)
            return RegistrationReport(
                family=self.family, version=self.version,
                registered=False, repro_meta=repro, lessons_saved=n_lessons,
                detail=str(e),
            )

    def _check_blocked(self, p1, p2, p3) -> Optional[str]:
        """Return reason if registration should be blocked, or None."""
        # Phase 1: any FAIL?
        for r in (p1 or []):
            if hasattr(r, 'is_fail') and r.is_fail:
                return f"Phase 1 FAIL: {r.check_id}"

        # Phase 2: any segment negative?
        for label, seg in (p2 or {}).get("segments", {}).items():
            if seg.get("annual", 0) <= 0:
                return f"Phase 2 segment {label} annual ≤ 0"

        # Phase 2: cost sensitivity FAIL?
        if (p2 or {}).get("cost_sensitivity", {}).get("verdict") == "FAIL":
            return "Phase 2 cost sensitivity FAIL"

        # Phase 2: correlation FAIL?
        if (p2 or {}).get("correlation", {}).get("verdict") == "FAIL":
            return "Phase 2 correlation FAIL"

        # Phase 3: WF FAIL?
        if (p3 or {}).get("aggregate", {}).get("verdict") == "FAIL":
            return "Phase 3 WF aggregate FAIL"

        return None

    def _build_metrics(self, p2, p3) -> dict:
        """Build metrics dict from Phase 2+3 data."""
        m = {}
        segs = p2.get("segments", {})
        for label, key in [("IS  2018-2022", "2018"), ("OOS 2023-2026", "2023"),
                            ("压力 2010-2017", "2010")]:
            s = segs.get(label, {})
            if s:
                m[f"annual_{key}"] = s.get("annual", 0)
                m[f"maxdd_{key}"] = s.get("maxdd", 0)
                m[f"sharpe_{key}"] = s.get("sharpe", 0)

        # Top-level (show IS 2018-2022)
        is_seg = segs.get("IS  2018-2022", {})
        m["annual"] = is_seg.get("annual", 0)
        m["maxdd"] = is_seg.get("maxdd", 0)
        m["sharpe"] = is_seg.get("sharpe", 0)
        m["calmar"] = is_seg.get("calmar", 0)

        # Hit check
        m["hit"] = m["annual"] >= 0.15 and abs(m["maxdd"]) <= 0.20

        # WF metrics
        wf = p3.get("aggregate", {})
        if wf:
            m["wf_annual"] = wf.get("annual", 0)
            m["wf_maxdd"] = wf.get("maxdd", 0)
            m["wf_sharpe"] = wf.get("sharpe", 0)

        return {k: round(float(v), 4) if isinstance(v, (int, float)) else v
                for k, v in m.items()}

    def _build_config(self, p2) -> dict:
        """Build config dict."""
        cfg = dict(p2.get("config", {}))
        cfg["cost"] = {
            "buy": 0.00225,
            "sell": 0.00275,
            "financing_rate": 0.065,
        }
        return cfg
