"""FactorSpace — systematic factor combination search.

Define a search space (factors × transforms × parameters × neutralizations)
and evaluate all combinations, returning ranked results.

Usage::

    space = FactorSpace()
    space.add_axis("factor", [illiq, momentum, reversal])
    space.add_axis("window", [20, 60, 120], apply_to_param="window")
    space.add_axis("neutralize", [None, "industry", "market_cap"])

    results = space.evaluate(data, engine_builder)
    results.top(10)  # best 10 combinations
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Callable, Optional
import time

import numpy as np
import pandas as pd

from factors.alpha.base import Factor, FactorData


# ---------------------------------------------------------------------------
# Search axis definition
# ---------------------------------------------------------------------------

@dataclass
class Axis:
    """One dimension of the search space."""
    name: str                          # e.g. "window", "factor", "neutralize"
    values: list                       # e.g. [20, 60, 120]
    apply_to_param: Optional[str] = None  # parameter name to set on factor


# ---------------------------------------------------------------------------
# Search result
# ---------------------------------------------------------------------------

@dataclass
class SpaceResult:
    """Result of evaluating one factor combination."""
    label: str                         # Human-readable description
    params: dict                       # {axis_name: value}
    factor: Factor                     # The factor expression used
    annual: float
    maxdd: float
    sharpe: float
    calmar: float
    ic_mean: Optional[float] = None
    icir: Optional[float] = None
    n_days: int = 0

    def summary(self) -> str:
        return (
            f"{self.label:<50} "
            f"ann={self.annual:>+7.1%}  dd={self.maxdd:>+7.1%}  "
            f"sh={self.sharpe:>+5.2f}  calmar={self.calmar:>+5.2f}"
        )


# ---------------------------------------------------------------------------
# FactorSpace
# ---------------------------------------------------------------------------

class FactorSpace:
    """Define and evaluate a search space of factor combinations.

    Parameters
    ----------
    engine_builder : callable
        ``(close, volume, amount) -> BacktestEngine``.
    signal_builder : callable
        ``(factor_values, timing) -> BaseSignal``.
    timing_builder : callable
        ``(close, amount) -> pd.Series``  — returns exposure series.
    """

    def __init__(
        self,
        engine_builder: Callable = None,
        signal_builder: Callable = None,
        timing_builder: Callable = None,
    ):
        self._axes: dict[str, Axis] = {}
        self._engine_builder = engine_builder
        self._signal_builder = signal_builder
        self._timing_builder = timing_builder

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def add_axis(self, name: str, values: list, apply_to_param: str = None):
        """Add a search dimension.

        Parameters
        ----------
        name : str
            Axis name (e.g. "window", "factor").
        values : list
            Values to iterate over.
        apply_to_param : str, optional
            If set, values are passed as keyword arguments when constructing
            factors (e.g. ``window=60``).
        """
        self._axes[name] = Axis(name=name, values=values, apply_to_param=apply_to_param)

    def set_engine_builder(self, fn):
        self._engine_builder = fn

    def set_signal_builder(self, fn):
        self._signal_builder = fn

    def set_timing_builder(self, fn):
        self._timing_builder = fn

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def evaluate(
        self,
        data: FactorData,
        close: pd.DataFrame,
        volume: pd.DataFrame,
        amount: pd.DataFrame,
        eval_start: str = "2018-01-01",
        max_combinations: int = 50,
    ) -> list[SpaceResult]:
        """Evaluate all combinations in the search space.

        Returns results sorted by Sharpe (descending).
        """
        if self._engine_builder is None or self._signal_builder is None:
            raise ValueError(
                "engine_builder and signal_builder must be set before evaluate()"
            )

        # Build timing once (shared across all combinations)
        timing = None
        if self._timing_builder is not None:
            timing = self._timing_builder(close, amount)

        # Generate all combinations
        axis_names = list(self._axes.keys())
        axis_values = [self._axes[n].values for n in axis_names]
        total = 1
        for v in axis_values:
            total *= len(v)

        if total > max_combinations:
            print(f"  Warning: {total} combinations > {max_combinations} limit, "
                  f"sampling {max_combinations}", flush=True)
            # Simple random sampling
            import random
            all_combos = list(product(*axis_values))
            random.shuffle(all_combos)
            combos = all_combos[:max_combinations]
        else:
            combos = list(product(*axis_values))

        print(f"  Evaluating {len(combos)} combinations...", flush=True)
        t0 = time.time()
        results = []

        for i, combo in enumerate(combos):
            params = dict(zip(axis_names, combo))
            factor = self._build_factor(params, data)
            if factor is None:
                continue

            # Compute factor values
            try:
                values = factor.compute(data)
            except Exception as e:
                print(f"    Skip {params}: {e}", flush=True)
                continue

            # Build signal + engine
            signal = self._signal_builder(values, timing, params)
            engine = self._engine_builder(close, volume, amount)
            result = engine.run(signal)

            # Metrics (eval period only)
            ret = result.returns.loc[eval_start:]
            ann = float(ret.mean() * 252)
            dd = float(((1 + ret).cumprod() / (1 + ret).cumprod().cummax() - 1).min())
            vol = float(ret.std() * np.sqrt(252))
            sh = ann / vol if vol > 0 else 0.0
            cal = ann / abs(dd) if dd < 0 else 0.0

            # Build readable label
            if "factor" in params:
                base = params["factor"]
                cls_name = base.__name__ if isinstance(base, type) else base.__class__.__name__
                param_str = ", ".join(
                    f"{k}={v}" for k, v in params.items() if k != "factor"
                )
                if param_str:
                    label = f"{cls_name}({param_str})"
                else:
                    label = cls_name
            else:
                label = ", ".join(f"{k}={v}" for k, v in params.items())

            results.append(SpaceResult(
                label=label,
                params=dict(params),
                factor=factor,
                annual=ann, maxdd=dd, sharpe=sh, calmar=cal,
                n_days=len(ret),
            ))

            if (i + 1) % 10 == 0:
                elapsed = time.time() - t0
                print(f"    {i+1}/{len(combos)} ({elapsed:.0f}s)", flush=True)

        results.sort(key=lambda r: r.sharpe, reverse=True)
        elapsed = time.time() - t0
        print(f"  Done: {len(results)} results in {elapsed:.0f}s", flush=True)
        return results

    # ------------------------------------------------------------------
    # Walk-Forward Evaluation
    # ------------------------------------------------------------------

    def walk_forward_evaluate(
        self,
        data: FactorData,
        close: pd.DataFrame,
        volume: pd.DataFrame,
        amount: pd.DataFrame,
        train_years: int = 3,
        test_years: int = 1,
        factor_windows: list[int] = None,
        extra_purge: int = 20,
        min_train_days: int = 500,
        max_combinations: int = 50,
        compute_dsr: bool = True,
        compute_pbo: bool = True,
    ) -> dict:
        """Purged Walk-Forward evaluation across multiple train/test windows.

        For each window:
        1. Optimize parameters on the training period.
        2. Apply the best parameterization to the test period (true OOS).
        3. Collect OOS returns.

        Then compute aggregate WF metrics, DSR, and PBO.

        Parameters
        ----------
        train_years, test_years : int
            Window sizes in calendar years.
        factor_windows : list[int], optional
            Lookback windows of factors in the search space.  Used to compute
            the purge gap.  Auto-detected from search axes if not provided.
        extra_purge : int
            Additional purge days (default 20 for rebalance cadence).
        compute_dsr : bool
            Compute Deflated Sharpe Ratio.
        compute_pbo : bool
            Compute Probability of Backtest Overfitting via CSCV.

        Returns
        -------
        dict with keys: wf_metrics, dsr_report, pbo_report, windows, best_params
        """
        from core.analysis.walk_forward import (
            walk_forward_windows, purge_days, wf_metrics,
            deflated_sharpe, pbo_cscv,
        )

        # Determine purge gap
        if factor_windows is None:
            factor_windows = []
            for axis in self._axes.values():
                if axis.apply_to_param == "window":
                    factor_windows.extend(
                        [v for v in axis.values if isinstance(v, (int, float))]
                    )
        purge = purge_days(factor_windows, extra=extra_purge)

        # Generate WF windows
        windows = walk_forward_windows(
            close.index, train_years=train_years, test_years=test_years,
            purge_days=purge, min_train_days=min_train_days,
        )
        if len(windows) < 2:
            raise ValueError(
                f"Only {len(windows)} WF windows generated. "
                f"Need at least 2. Try reducing train_years or purge_days."
            )

        print(f"\n  Purged WF: {len(windows)} windows, "
              f"train={train_years}y, test={test_years}y, purge={purge}d", flush=True)
        t0 = time.time()

        # Timing (shared across windows)
        timing_full = None
        if self._timing_builder is not None:
            timing_full = self._timing_builder(close, amount)

        oos_returns_all = []
        oos_returns_by_strategy = {}  # For PBO
        best_params_per_window = []
        all_combos_returns = {}       # name → concatenated OOS returns (for PBO)

        for wi, w in enumerate(windows):
            t_train_start = w["train_start"]
            t_train_end = w["train_end"]
            t_test_start = w["test_start"]
            t_test_end = w["test_end"]

            # Slice data for this window
            close_train = close.loc[t_train_start:t_train_end]
            close_test = close.loc[t_test_start:t_test_end]

            if len(close_train) < 100 or len(close_test) < 20:
                continue

            # IS: optimize on training period
            train_mask = (close.index >= t_train_start) & (close.index <= t_train_end)
            test_mask = (close.index >= t_test_start) & (close.index <= t_test_end)

            vol_train = volume.loc[train_mask]
            amt_train = amount.loc[train_mask]
            timing_train = timing_full.loc[train_mask] if timing_full is not None else None

            # Slice FactorData for training
            train_dates = close_train.index
            data_train = FactorData(
                close=close_train,
                volume=vol_train,
                amount=amt_train,
                raw_close=data.raw_close.loc[train_dates]
                if data.raw_close is not None else None,
                industry=data.industry.loc[train_dates]
                if data.industry is not None else None,
                market_cap=data.market_cap.loc[train_dates]
                if data.market_cap is not None else None,
            )

            print(f"\n  Window {wi+1}/{len(windows)}: "
                  f"train={str(t_train_start.date())[:7]}~{str(t_train_end.date())[:7]}  "
                  f"test={str(t_test_start.date())[:7]}~{str(t_test_end.date())[:7]}",
                  flush=True)

            # Run IS evaluation
            is_timing_builder = (lambda c, a: timing_train) if timing_train is not None else None
            saved_timing = self._timing_builder
            saved_signal = self._signal_builder
            saved_engine = self._engine_builder

            # Override builders to use train-sliced data
            self._timing_builder = is_timing_builder

            is_results = self.evaluate(
                data_train, close_train, vol_train, amt_train,
                eval_start=str(t_train_start.date()),
                max_combinations=max_combinations,
            )
            if not is_results:
                continue

            best = is_results[0]
            best_params_per_window.append({
                "window": wi,
                "train": f"{t_train_start.date()}~{t_train_end.date()}",
                "test": f"{t_test_start.date()}~{t_test_end.date()}",
                "best_params": best.params,
                "best_is_sharpe": best.sharpe,
            })

            # OOS: test best parameterization on test period
            test_factor = self._build_factor(best.params, data)
            if test_factor is None:
                continue
            test_values = test_factor.compute(data).loc[t_test_start:t_test_end]

            # Also compute all combos on test for PBO
            if compute_pbo and len(is_results) > 1:
                for r in is_results:
                    name = r.label
                    tf = self._build_factor(r.params, data)
                    if tf is None:
                        continue
                    tv = tf.compute(data).loc[t_test_start:t_test_end]
                    if len(tv) < 20:
                        continue

                    timing_test = timing_full.loc[test_mask] if timing_full is not None else None
                    sig = saved_signal(tv, timing_test, r.params)
                    eng = saved_engine(
                        close.loc[test_mask],
                        volume.loc[test_mask],
                        amount.loc[test_mask],
                    )
                    oos_r = eng.run(sig).returns.dropna()
                    if len(oos_r) > 20:
                        if name not in all_combos_returns:
                            all_combos_returns[name] = []
                        all_combos_returns[name].append(oos_r)

            # Build signal + engine for test
            timing_test = timing_full.loc[test_mask] if timing_full is not None else None
            sig = saved_signal(test_values, timing_test, best.params)
            eng = saved_engine(
                close.loc[test_mask],
                volume.loc[test_mask],
                amount.loc[test_mask],
            )
            oos_result = eng.run(sig)
            oos_ret = oos_result.returns.dropna()
            if len(oos_ret) > 20:
                oos_returns_all.append(oos_ret)

            # Restore builders
            self._timing_builder = saved_timing

        # ── Aggregate results ──
        wf = wf_metrics(oos_returns_all)
        print(f"\n  WF aggregate: {wf.summary()}", flush=True)

        # DSR
        dsr_report = None
        if compute_dsr and len(oos_returns_all) > 0:
            all_oos = pd.concat(oos_returns_all).sort_index().dropna()
            if len(all_oos) > 200:
                skew = float(all_oos.skew())
                kurt = float(all_oos.kurtosis()) + 3.0  # pandas kurtosis is excess
                n_trials = len(combos := list(product(*[
                    self._axes[n].values for n in self._axes
                ])))
                dsr_report = deflated_sharpe(
                    observed_sr=wf.sharpe,
                    n_trials=min(n_trials, max_combinations),
                    n_periods=len(all_oos),
                    skew=skew if not np.isnan(skew) else 0.0,
                    kurt=kurt if not np.isnan(kurt) else 3.0,
                )
                print(f"  DSR: {dsr_report['dsr']:+.2f} "
                      f"(p={dsr_report['p_value']:.3f}, "
                      f"E[max SR]={dsr_report['e_max_sr']:.2f})", flush=True)

        # PBO
        pbo_report = None
        if compute_pbo and len(all_combos_returns) > 1:
            # Concatenate OOS returns per strategy
            concat_returns = {}
            for name, rets in all_combos_returns.items():
                if len(rets) > 0:
                    concat_returns[name] = pd.concat(rets).sort_index().dropna()
            if len(concat_returns) > 1:
                pbo_report = pbo_cscv(concat_returns, n_splits=min(50, len(windows)*10))
                print(f"  PBO: {pbo_report['pbo']:.2f} "
                      f"({pbo_report['risk_level']} risk, "
                      f"mean OOS rank={pbo_report['mean_oos_rank']:.1f})", flush=True)

        elapsed = time.time() - t0
        print(f"  WF total: {elapsed:.0f}s", flush=True)

        return {
            "wf_metrics": wf,
            "dsr_report": dsr_report,
            "pbo_report": pbo_report,
            "windows": best_params_per_window,
            "n_combinations": len(best_params_per_window),
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _build_factor(self, params: dict, data: FactorData) -> Optional[Factor]:
        """Build a Factor from search parameters."""
        factor = None

        # Special handling: if there's a "factor" axis, it provides the base
        if "factor" in params:
            base = params["factor"]

            # base can be a class or an instance
            if isinstance(base, type):
                factor_cls = base
            else:
                factor_cls = base.__class__

            # Collect constructor kwargs from parameter axes
            kwargs = {}
            for name, axis in self._axes.items():
                if axis.apply_to_param and name != "factor":
                    kwargs[axis.apply_to_param] = params[name]

            try:
                factor = factor_cls(**kwargs)
            except TypeError:
                # Class doesn't accept these params; try without
                try:
                    factor = factor_cls()
                except TypeError:
                    return None

        if factor is None:
            return None

        # Apply transforms
        factor = factor.mad_clip(5).zscore().shift(1)

        # Apply neutralization
        if params.get("neutralize") == "industry" and data.industry is not None:
            factor = factor.neutralize(data.industry)
        elif params.get("neutralize") == "market_cap" and data.market_cap is not None:
            factor = factor.neutralize(data.market_cap)

        return factor
