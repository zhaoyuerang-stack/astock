"""
组合构建：基于因子信号生成持仓
"""
import pandas as pd
import numpy as np


def top_n_portfolio(
    factor: pd.DataFrame,
    n: int = 100,
    direction: int = 1,
    rebalance_freq: str = "W",
) -> pd.DataFrame:
    """
    每period选因子值最高(direction=1)或最低(-1)的n只股票，等权持仓
    返回 date×code 的持仓权重DataFrame（稀疏，仅持仓股非零）
    """
    if direction == -1:
        factor = -factor

    dates = factor.resample(rebalance_freq).last().index
    all_weights = []
    for dt in dates:
        f = factor.loc[:dt].iloc[-1].dropna()
        top = f.nlargest(n).index
        w = pd.Series(1.0 / n, index=top, name=dt)
        all_weights.append(w)

    weight_df = pd.DataFrame(all_weights).fillna(0)
    weight_df.index = pd.DatetimeIndex(weight_df.index)
    return weight_df


def calc_portfolio_return(
    weight: pd.DataFrame,
    close: pd.DataFrame,
) -> pd.Series:
    """
    用持仓权重和日收盘价计算组合日收益
    weight: rebalance日期×code，close: 所有交易日×code
    """
    daily_ret = close.pct_change()
    port_ret = []
    dates = daily_ret.index
    rebal_dates = weight.index.sort_values()

    current_w = None
    for dt in dates:
        # 换仓日更新权重
        past = rebal_dates[rebal_dates <= dt]
        if len(past) > 0:
            current_w = weight.loc[past[-1]]
        if current_w is None:
            port_ret.append((dt, np.nan))
            continue
        common = current_w.index.intersection(daily_ret.columns)
        r = (current_w[common] * daily_ret.loc[dt, common]).sum()
        port_ret.append((dt, r))

    return pd.Series(dict(port_ret))


def performance_metrics(port_ret: pd.Series, rf: float = 0.02) -> dict:
    ret = port_ret.dropna()
    annual_ret = ret.mean() * 252
    annual_vol = ret.std() * np.sqrt(252)
    sharpe = (annual_ret - rf) / annual_vol if annual_vol > 0 else np.nan
    cum = (1 + ret).cumprod()
    maxdd = (cum / cum.cummax() - 1).min()
    calmar = annual_ret / abs(maxdd) if maxdd != 0 else np.nan
    return {
        "年化收益": f"{annual_ret:.2%}",
        "年化波动": f"{annual_vol:.2%}",
        "夏普比率": f"{sharpe:.2f}",
        "最大回撤": f"{maxdd:.2%}",
        "卡玛比率": f"{calmar:.2f}",
    }
