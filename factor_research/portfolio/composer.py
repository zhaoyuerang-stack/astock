"""Portfolio composition algorithms.

Three methods for combining strategy return streams into a portfolio:
  - EqualWeight:    1/N baseline
  - RiskParity:     inverse-volatility weighted
  - RegimeAdaptive: switch weights based on PureTrend regime

All operate on daily return DataFrames (date × strategy).
"""
import numpy as np
import pandas as pd


def equal_weight(returns: pd.DataFrame) -> pd.Series:
    """1/N equal weight across all strategies.

    Returns a daily portfolio return Series.
    """
    n = returns.shape[1]
    weights = np.full(n, 1.0 / n)
    return (returns * weights).sum(axis=1)


def risk_parity(returns: pd.DataFrame, lookback: int = 252) -> pd.Series:
    """Inverse-volatility weighted: lower vol → higher weight.

    Weights recomputed each day based on trailing lookback-day vol.
    """
    rolling_vol = returns.rolling(lookback, min_periods=63).std()
    inv_vol = 1.0 / rolling_vol.replace(0, np.nan)
    weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
    weights = weights.shift(1)  # use T-1 weights for T
    return (returns * weights).sum(axis=1)


def capped_weight(returns: pd.DataFrame, defensive: set, cap: float = 0.30) -> pd.Series:
    """防御腿合计权重 ≤ cap(组内等权),其余进攻腿分配 1-cap(组内等权)。

    防御腿(国债/黄金)低波低收益,无界等权会被等权或 risk_parity 过度配重而稀释
    收益(equal 4 腿=50% 防御 → 年化跌破满意线;risk_parity 灌满债券 → 年化崩 8.2%)。
    capped 保留进攻腿主导(收益)+ 防御腿封顶(回撤/尾部保险),是这两类混合的正确权重。
    """
    cols = list(returns.columns)
    d = [c for c in cols if c in defensive]
    g = [c for c in cols if c not in defensive]
    w = pd.Series(0.0, index=cols)
    if d and g:
        w[d] = cap / len(d)
        w[g] = (1.0 - cap) / len(g)
    else:  # 全防御或全进攻 → 退回等权
        w[:] = 1.0 / len(cols)
    return (returns * w).sum(axis=1), w


def regime_adaptive(
    returns: pd.DataFrame,
    vol: pd.DataFrame,
    regime_signal: pd.Series,
) -> pd.Series:
    """Regime-based weighting.

    When regime_signal = 1 (bull/in-market):
      → equal weight across all (stay diversified)
    When regime_signal = 0 (bear/cash):
      → overweight low-vol strategies (size-earnings gets 2x)

    Simple heuristic: don't overfit with rolling Sharpe optimization.
    """
    regime = regime_signal.reindex(returns.index).fillna(0)
    n = returns.shape[1]

    # Bull: equal weight
    bull_w = pd.DataFrame(1.0 / n, index=returns.index, columns=returns.columns)

    # Bear: 2x weight on lowest-vol strategy, equal on rest
    vol_mean = vol.rolling(252).mean().iloc[-1]
    lowest_vol = vol_mean.idxmin()
    bear_w = pd.DataFrame(1.0 / n, index=returns.index, columns=returns.columns)
    bear_w[lowest_vol] = min(0.5, 2.0 / n)  # cap at 50%

    # Blend
    weights = bull_w.mul(regime, axis=0) + bear_w.mul(1 - regime, axis=0)
    weights = weights.div(weights.sum(axis=1), axis=0).fillna(1.0 / n)
    weights = weights.shift(1).fillna(1.0 / n)

    return (returns * weights).sum(axis=1)


def compose(
    returns: dict[str, pd.Series],
    method: str = "equal_weight",
    regime_signal: pd.Series = None,
    defensive: set = None,
    cap: float = 0.30,
) -> tuple[pd.Series, pd.DataFrame]:
    """Main entry: compose strategy returns into a portfolio.

    Args:
        returns: {strategy_name: daily_return_series}
        method: 'equal_weight' | 'risk_parity' | 'regime_adaptive' | 'capped'
        regime_signal: required for regime_adaptive
        defensive: 防御腿名集合(method='capped' 用),合计权重封顶 cap
        cap: 防御腿合计权重上限(默认 0.30)

    Returns:
        (portfolio_daily_returns, weights_history)
    """
    df = pd.DataFrame(returns).dropna()
    if df.shape[1] < 2:
        return df.iloc[:, 0], pd.DataFrame({"weight": [1.0]})

    static_w = None
    if method == "risk_parity":
        port_ret = risk_parity(df)
    elif method == "regime_adaptive":
        if regime_signal is None:
            raise ValueError("regime_signal required for regime_adaptive")
        vol = df.rolling(252).std()
        port_ret = regime_adaptive(df, vol, regime_signal)
    elif method == "capped":
        port_ret, static_w = capped_weight(df, defensive or set(), cap)
    else:
        port_ret = equal_weight(df)

    # Reconstruct weights for reporting(capped 用真实静态权重)
    if static_w is not None:
        weights = pd.DataFrame([static_w.values], columns=df.columns, index=["weight"])
    else:
        weights = pd.DataFrame(1.0 / df.shape[1], index=df.index, columns=df.columns)
    return port_ret.dropna(), weights


def metrics(returns: pd.Series) -> dict:
    """Compute standard portfolio metrics."""
    r = returns.dropna()
    if len(r) < 50:
        return {"annual": 0, "maxdd": 0, "sharpe": 0, "calmar": 0}
    ann = float(r.mean() * 252)
    vol = float(r.std() * np.sqrt(252))
    sharpe = ann / vol if vol > 0 else 0.0
    cum = (1 + r).cumprod()
    maxdd = float((cum / cum.cummax() - 1).min())
    calmar = ann / abs(maxdd) if maxdd < 0 else 0.0
    return {"annual": ann, "vol": vol, "maxdd": maxdd,
            "sharpe": sharpe, "calmar": calmar, "n_days": len(r)}
