"""
动量类因子
"""
import pandas as pd
import numpy as np


def mom_n(close: pd.DataFrame, n: int, skip: int = 0) -> pd.DataFrame:
    """N日动量，可跳过最近skip日（规避短反转）"""
    if skip > 0:
        return close.shift(skip) / close.shift(n + skip) - 1
    return close / close.shift(n) - 1


def turnover_mean(amount: pd.DataFrame, capital: pd.DataFrame, n: int) -> pd.DataFrame:
    """N日平均换手率 = 成交额/流通市值"""
    turn = amount / capital
    return turn.rolling(n).mean()


def vol_ratio(volume: pd.DataFrame, short: int = 5, long: int = 20) -> pd.DataFrame:
    """量比 = 近short日均量 / 近long日均量"""
    return volume.rolling(short).mean() / volume.rolling(long).mean()


def price_to_ma(close: pd.DataFrame, n: int) -> pd.DataFrame:
    """价格偏离均线程度 = close/MA(n) - 1"""
    return close / close.rolling(n).mean() - 1


def volatility(close: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """N日收益率波动率"""
    ret = close.pct_change()
    return ret.rolling(n).std() * np.sqrt(252)


def illiquidity(close: pd.DataFrame, volume: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """Amihud非流动性因子 = mean(|ret|/volume)"""
    ret = close.pct_change().abs()
    daily = ret / (volume + 1)
    return daily.rolling(n).mean()
