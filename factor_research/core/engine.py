"""Unified backtest engine — single entry-point for all backtest & factor analysis.

Design goals
------------
1. One ``BacktestEngine`` class handles portfolio-weight backtests, IC analysis,
   and stratified return tests.
2. ``Signal`` is the canonical input (weights, factor, or factor_builder).
3. ``BacktestResult`` is the canonical output (returns, costs, metrics).
4. ``PricePanel`` replaces the ad-hoc (close, volume, amount, raw_close) tuples.
5. Existing APIs in ``core/backtest.py`` and ``engine/backtest.py`` are preserved
   as thin compatibility wrappers (see Phase-2 migration).

Usage
-----
>>> from core.engine import BacktestEngine, Signal, BacktestConfig, PricePanel
>>> engine = BacktestEngine(prices=price_panel, config=BacktestConfig())
>>> result = engine.run(Signal(weights=scheduled_weights, timing=timing_signal))
>>> print(result.metrics)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from engine.metrics import compute_hit, institutional_metrics, TARGET_ANNUAL, TARGET_MAXDD


# ---------------------------------------------------------------------------
# Config & Data Containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CostModel:
    """Execution cost assumptions (matches ``core/backtest.CostModel``)."""
    buy_cost: float = 0.00225
    sell_cost: float = 0.00275
    financing_rate: float = 0.065


@dataclass(frozen=True)
class BacktestConfig:
    """Global backtest parameters.

    ``start`` is the **statistics window** start: simulation runs over the full
    price panel (preserving factor warmup and holding continuity), then the
    returns/turnover/cost series are truncated to ``>= start`` before metrics.
    Historically this field was dead (full-panel stats regardless of start),
    which silently diluted OOS metrics with idle pre-start days.
    """
    start: str = "2018-01-01"
    cost: CostModel = field(default_factory=CostModel)
    leverage: float = 1.25
    # Evaluation thresholds — single-strategy entry bar (年化>15% / 回撤<20%)
    # Original 35%/15% was anchored to data_full survivorship bias, retired.
    target_annual: float = 0.15
    target_maxdd: float = 0.20


@dataclass(frozen=True)
class PricePanel:
    """Unified price / volume panel.

    Replaces the ad-hoc ``(close, volume, amount, raw_close)`` tuples that
    used to be passed around between modules.
    """
    close: pd.DataFrame          # adjusted close (for return calculation)
    volume: pd.DataFrame         # in 手 (×100 for shares)
    amount: pd.DataFrame         # turnover in CNY  (volume*100*raw_close)
    raw_close: Optional[pd.DataFrame] = None  # unadjusted close (for valuation / order sizing)
    # Optional extensions for live-trade simulation
    raw_open: Optional[pd.DataFrame] = None


# ---------------------------------------------------------------------------
# Signal — canonical strategy input
# ---------------------------------------------------------------------------

@dataclass
class Signal:
    """Standardised strategy signal.

    Three mutually-preferred modes (checked in order):
    1. **weights** – pre-computed target weights (date × code DataFrame).
    2. **factor**  – raw factor values; engine converts to top-n weights internally.
    3. **factor_builder** – callable ``(prices, config) -> factor DataFrame``.
    """
    # Mode A: direct weights
    weights: Optional[pd.DataFrame] = None

    # Mode B: factor → top-n weights
    factor: Optional[pd.DataFrame] = None
    top_n: int = 25
    direction: int = 1                      # 1 = long top, -1 = long bottom
    rebalance_freq: str = "20D"             # pandas offset alias

    # Mode C: lazy factor builder (used by factory)
    factor_builder: Optional[Callable[[PricePanel, Optional[dict]], pd.DataFrame]] = None
    factor_config: Optional[dict] = None

    # Timing exposure (daily multiplier). Default cap 1.0 (binary).
    # 2026-06-07: Boost band 需要 > 1.0；调 Signal.exposure_cap 解除。
    timing: Optional[pd.Series] = None
    exposure_cap: float = 1.0   # boost timing 需要传 1.5 等

    # Metadata
    family: str = ""
    version: str = ""

    def _resolve_weights(self, prices: PricePanel) -> pd.DataFrame:
        """Convert factor / factor_builder to target weights."""
        if self.weights is not None:
            return self.weights
        factor = self.factor
        if factor is None and self.factor_builder is not None:
            factor = self.factor_builder(prices, self.factor_config)
        if factor is None:
            raise ValueError("Signal must provide weights, factor, or factor_builder")
        return _factor_to_weights(
            factor,
            top_n=self.top_n,
            direction=self.direction,
            rebalance_freq=self.rebalance_freq,
            close=prices.close,
        )


# ---------------------------------------------------------------------------
# BacktestResult — canonical output
# ---------------------------------------------------------------------------

@dataclass
class BacktestResult:
    """Unified backtest result.

    Replaces the scattered dicts returned by ``core/backtest.py``,
    ``engine/portfolio.py``, and ``factory/objectives.py``.
    """
    # Core series
    returns: pd.Series
    turnover: pd.Series
    cost: pd.Series

    # Derived
    detail: pd.DataFrame = field(init=False)
    weights_history: Optional[pd.DataFrame] = None

    # IC / stratify (populated by optional analysis calls)
    ic_series: Optional[pd.Series] = None
    ic_summary: Optional[dict] = None
    stratify_ret: Optional[pd.DataFrame] = None

    # Metadata
    family: str = ""
    version: str = ""
    config: Optional[BacktestConfig] = None

    def __post_init__(self):
        self.detail = pd.DataFrame(
            {"ret": self.returns, "turnover": self.turnover, "cost": self.cost},
            index=self.returns.index,
        )

    # ---- metrics (lazy properties, identical formula to core/backtest.metrics) ----

    @property
    def n(self) -> int:
        return len(self.returns)

    @property
    def annual(self) -> float:
        return float(self.returns.mean() * 252)

    @property
    def vol(self) -> float:
        return float(self.returns.std() * np.sqrt(252))

    @property
    def sharpe(self) -> float:
        return self.annual / self.vol if self.vol > 0 else 0.0

    @property
    def maxdd(self) -> float:
        cum = (1 + self.returns).cumprod()
        return float((cum / cum.cummax() - 1).min())

    @property
    def calmar(self) -> float:
        return self.annual / abs(self.maxdd) if self.maxdd < 0 else 0.0

    @property
    def anomalies(self) -> list:
        """结果哨兵:统计上近乎不可能的结果形态,优先怀疑数据而非行情。

        阈值取"分散组合物理上限之外":|组合日收益|>35%(20cm 全跌停 × 1.5 杠杆
        = 30% 才到边界;2026-06 假崩盘日为 -60% 量级)或回撤 >90%。
        只报警不改数——哨兵触发时先查数据(末几日截面分布),再信结论。
        """
        flags = []
        if len(self.returns):
            worst = self.returns.abs().max()
            if worst > 0.35:
                d = self.returns.abs().idxmax()
                flags.append(f"组合单日|r|={worst:.1%} @ {pd.Timestamp(d).date()} 超物理边界,疑数据问题")
        if self.maxdd < -0.90:
            flags.append(f"回撤 {self.maxdd:.1%} 近乎清零,疑数据问题")
        return flags

    @property
    def hit(self) -> bool:
        # 唯一权威判定走 engine.metrics.compute_hit（严格不等号），阈值可被 config 覆盖。
        # NOTE: @property cannot accept extra arguments — thresholds come from self.config.
        t_annual = self.config.target_annual if self.config else TARGET_ANNUAL
        t_maxdd = self.config.target_maxdd if self.config else TARGET_MAXDD
        return compute_hit(self.annual, self.maxdd, t_annual, t_maxdd)

    @property
    def metrics(self) -> dict:
        """Dict compatible with ``core/backtest.metrics()`` output."""
        if self.n < 100:
            return {
                "annual": -1.0,
                "vol": 0.0,
                "sharpe": -1.0,
                "maxdd": -1.0,
                "calmar": 0.0,
                "hit": False,
                "n": self.n,
            }
        return {
            "annual": self.annual,
            "vol": self.vol,
            "sharpe": self.sharpe,
            "maxdd": self.maxdd,
            "calmar": self.calmar,
            "hit": self.hit,
            "n": self.n,
            **institutional_metrics(self.returns),
        }

    @property
    def yearly_returns(self) -> pd.Series:
        return self.returns.groupby(self.returns.index.year).apply(
            lambda x: (1 + x).prod() - 1
        )

    # ---- convenience ----

    def summary(self) -> dict:
        """Human-friendly summary dict (for logging / JSON)."""
        m = self.metrics
        return {
            "annual": f"{m['annual']:+.2%}",
            "maxdd": f"{m['maxdd']:.2%}",
            "sharpe": f"{m['sharpe']:.2f}",
            "calmar": f"{m['calmar']:.2f}",
            "n": self.n,
        }


# ---------------------------------------------------------------------------
# BacktestEngine
# ---------------------------------------------------------------------------

class BacktestEngine:
    """Single entry-point for portfolio backtests and factor analysis."""

    def __init__(self, prices: PricePanel, config: BacktestConfig = None):
        self.prices = prices
        self.config = config or BacktestConfig()

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    def run(self, signal: Signal) -> BacktestResult:
        """Run a portfolio-weight backtest from a ``Signal``."""
        weights = signal._resolve_weights(self.prices)
        return self._run_weight_backtest(weights, signal.timing, signal)

    # ------------------------------------------------------------------
    # Factor analysis (ported from engine/backtest.py)
    # ------------------------------------------------------------------

    def run_ic_analysis(
        self,
        factor: pd.DataFrame,
        forward_days: int = 1,
        method: str = "rank",
    ) -> dict:
        """Compute IC time-series and summary (identical to ``engine/backtest``)."""
        close = self.prices.close
        forward_ret = close.pct_change(forward_days).shift(-forward_days)
        ic = _calc_ic(factor, forward_ret, method=method)
        return {
            "ic_series": ic,
            "ic_summary": _ic_summary(ic),
        }

    def run_stratify(
        self,
        factor: pd.DataFrame,
        forward_days: int = 1,
        n_quantile: int = 5,
    ) -> pd.DataFrame:
        """Stratified return test (identical to ``engine/backtest``)."""
        close = self.prices.close
        forward_ret = close.pct_change(forward_days).shift(-forward_days)
        return _stratify_return(factor, forward_ret, n_quantile=n_quantile)

    # ------------------------------------------------------------------
    # Internal: portfolio-weight backtest (ported from core/backtest.py)
    # ------------------------------------------------------------------

    def _run_weight_backtest(
        self,
        scheduled_weights: dict | pd.DataFrame,
        timing_signal: Optional[pd.Series] = None,
        signal_meta: Optional[Signal] = None,
    ) -> BacktestResult:
        """Daily vector backtest with turnover, timing, leverage and financing.

        Logic is a direct port of ``core/backtest.backtest_weights()`` so that
        numerical results are bit-for-bit identical.
        """
        close = self.prices.close
        config = self.config

        # Normalise dict-of-Series to DataFrame if necessary
        if isinstance(scheduled_weights, dict):
            scheduled_weights = _dict_weights_to_df(scheduled_weights, close.index)

        daily_ret = (
            close.pct_change(fill_method=None)
            .replace([np.inf, -np.inf], np.nan)
            .fillna(0.0)
        )
        dates = list(close.index)
        cols = list(close.columns)
        col_idx = {c: i for i, c in enumerate(cols)}

        current_selected = pd.Series(dtype=float)
        current_weight = np.zeros(len(cols))
        out = np.full(len(dates), np.nan)
        turnover = np.zeros(len(dates))
        cost_paid = np.zeros(len(dates))

        for i, dt in enumerate(dates):
            if i == 0:
                continue
            if dt in scheduled_weights.index:
                current_selected = scheduled_weights.loc[dt].dropna()

            # Timing exposure multiplier [0, exposure_cap]
            exposure = 1.0
            if timing_signal is not None:
                exposure = float(timing_signal.reindex([dt]).fillna(0.0).iloc[0])
                exp_cap = signal_meta.exposure_cap if signal_meta is not None else 1.0
                exposure = min(max(exposure, 0.0), exp_cap)

            target_weight = np.zeros(len(cols))
            if exposure > 0 and len(current_selected):
                for code, weight in current_selected.items():
                    j = col_idx.get(code)
                    if j is not None:
                        target_weight[j] = weight * exposure

            delta = target_weight - current_weight
            buy_turnover = float(delta[delta > 0].sum())
            sell_turnover = float((-delta[delta < 0]).sum())
            trade_cost = (
                buy_turnover * config.cost.buy_cost
                + sell_turnover * config.cost.sell_cost
            ) * config.leverage

            day_ret = np.array(daily_ret.iloc[i].values, dtype="float64", copy=True)
            day_ret[~np.isfinite(day_ret)] = 0.0
            day_ret = np.clip(day_ret, -1.0, 10.0)
            held = target_weight != 0
            gross_ret = float((day_ret[held] * target_weight[held]).sum()) * config.leverage

            financing = 0.0
            if target_weight.sum() > 0 and config.leverage > 1:
                financing = (config.leverage - 1.0) * config.cost.financing_rate / 252.0

            out[i] = gross_ret - trade_cost - financing
            turnover[i] = buy_turnover + sell_turnover
            cost_paid[i] = trade_cost + financing
            current_weight = target_weight

        ret = pd.Series(out, index=dates).dropna()
        to = pd.Series(turnover[1:], index=ret.index)
        co = pd.Series(cost_paid[1:], index=ret.index)

        # start = 统计窗口起点:全面板连续模拟(保留预热/持仓连续性)后切片统计,
        # 否则把 start 前的空仓/预热期算进年化会稀释指标(LESSONS 2026-06-12)
        if config.start:
            stats_from = pd.Timestamp(config.start)
            ret = ret.loc[stats_from:]
            to = to.loc[stats_from:]
            co = co.loc[stats_from:]

        result = BacktestResult(
            returns=ret,
            turnover=to,
            cost=co,
            family=getattr(signal_meta, "family", ""),
            version=getattr(signal_meta, "version", ""),
            config=config,
        )
        for msg in result.anomalies:
            print(f"🚨 [结果哨兵] {msg} —— 采信前先检查数据湖末几日截面分布", flush=True)
        return result


# ---------------------------------------------------------------------------
# Internal helpers (ported from existing modules)
# ---------------------------------------------------------------------------

def _factor_to_weights(
    factor: pd.DataFrame,
    top_n: int = 25,
    direction: int = 1,
    rebalance_freq: str = "20D",
    close: pd.DataFrame = None,
) -> pd.DataFrame:
    """Convert factor panel to scheduled target weights.

    Logic matches ``core.backtest.build_rebalance_weights`` for consistency:
    - rebalance every *rebalance_days* (parsed from ``rebalance_freq``)
    - effective date = next trading day (pos + 1)
    - top_n equal weights

    Parameters
    ----------
    close : pd.DataFrame, optional
        Price panel used to find the next-trading-day effective date.
        If omitted, effective date = the rebalance date itself.
    """
    if direction == -1:
        factor = -factor

    # Parse rebalance frequency (e.g. "20D" -> 20)
    try:
        rebalance_days = int(rebalance_freq.replace("D", ""))
    except ValueError:
        rebalance_days = 20  # fallback

    fdates = factor.dropna(how="all").index
    if close is not None:
        fdates = fdates.intersection(close.index)
    if len(fdates) < 100:
        return pd.DataFrame(index=pd.DatetimeIndex([], dtype="datetime64[ns]"))

    rows = []
    for rd in list(fdates[::rebalance_days]):
        if close is not None:
            pos = close.index.get_loc(rd)
            if pos + 1 >= len(close.index):
                continue
            effective = close.index[pos + 1]
            active = close.loc[rd].dropna().index
        else:
            effective = rd
            active = factor.columns

        f = factor.loc[rd].dropna()
        f = f.reindex(active).dropna()
        if len(f) < top_n:
            if len(f) == 0:
                w = pd.Series(0.0, index=[active[0]], name=effective)
                rows.append(w)
            continue
        if f.std() <= 1e-8:
            w = pd.Series(0.0, index=[active[0]], name=effective)
            rows.append(w)
            continue
        top = f.nlargest(top_n).index
        w = pd.Series(1.0 / top_n, index=top, name=effective)
        rows.append(w)

    if not rows:
        return pd.DataFrame(index=pd.DatetimeIndex([], dtype="datetime64[ns]"))

    weight_df = pd.DataFrame(rows).fillna(0)
    weight_df.index = pd.DatetimeIndex(weight_df.index)
    return weight_df


def _dict_weights_to_df(
    weights_dict: dict,
    all_dates: pd.DatetimeIndex,
) -> pd.DataFrame:
    """Convert ``{date: Series}`` (legacy core/backtest format) to DataFrame."""
    if not weights_dict:
        return pd.DataFrame(index=all_dates)
    rows = []
    for dt, s in sorted(weights_dict.items()):
        s = s.copy()
        s.name = dt
        rows.append(s)
    df = pd.DataFrame(rows).fillna(0)
    df.index = pd.DatetimeIndex(df.index)
    return df


# ---- IC analysis helpers (ported from engine/backtest.py) ----

def _calc_ic(
    factor: pd.DataFrame,
    forward_ret: pd.DataFrame,
    method: str = "rank",
) -> pd.Series:
    dates = factor.index.intersection(forward_ret.index)
    ics = {}
    for dt in dates:
        f = factor.loc[dt].dropna()
        r = forward_ret.loc[dt].dropna()
        common = f.index.intersection(r.index)
        if len(common) < 30:
            continue
        fv, rv = f[common].values, r[common].values
        if method == "rank":
            ic, _ = spearmanr(fv, rv)
        else:
            ic = np.corrcoef(fv, rv)[0, 1]
        ics[dt] = ic
    return pd.Series(ics).sort_index()


def _ic_summary(ic: pd.Series) -> dict:
    return {
        "IC_mean": ic.mean(),
        "IC_std": ic.std(),
        "ICIR": ic.mean() / ic.std() if ic.std() > 0 else np.nan,
        "IC>0_ratio": (ic > 0).mean(),
        "|IC|>0.02_ratio": (ic.abs() > 0.02).mean(),
        "count": len(ic),
    }


# ---- Stratify helpers (ported from engine/backtest.py) ----

def _stratify_return(
    factor: pd.DataFrame,
    forward_ret: pd.DataFrame,
    n_quantile: int = 5,
) -> pd.DataFrame:
    dates = factor.index.intersection(forward_ret.index)
    records = []
    for dt in dates:
        f = factor.loc[dt].dropna()
        r = forward_ret.loc[dt].dropna()
        common = f.index.intersection(r.index)
        if len(common) < n_quantile * 5:
            continue
        labels = pd.qcut(f[common], n_quantile, labels=False, duplicates="drop")
        group_ret = r[common].groupby(labels).mean()
        row = {"date": dt}
        for g, v in group_ret.items():
            row[f"Q{int(g)+1}"] = v
        records.append(row)
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records).set_index("date").sort_index()
    return df
