"""微观结构 / 行为金融类因子。

这些因子与小盘流动性溢价 (factors.small_cap) 是不同的 alpha 源：
  - short_reversal: 短期反转（行为金融过度反应）
  - price_position: N 日价格位置（抄底/追高反转）
  - vol_breakout: 量比突破（关注度跳变）
  - amplitude_mean: N 日振幅（不确定性溢价）

所有函数都返回 z-scored panel (date × code)，正值 = "长方向"。
"""
import numpy as np
import pandas as pd

from factors.utils import mad_clip, safe_zscore


def short_reversal(close: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    """N 日累计收益的反转因子（负 ret_N）。

    Mechanism: 短期过度反应 → 价格回归；A 股 1-3 周反转效应。
    Positive = 近期跌得多 → 期望反弹。
    """
    ret_n = close / close.shift(n) - 1
    return safe_zscore(mad_clip(-ret_n))


def price_position(close: pd.DataFrame, n: int = 60) -> pd.DataFrame:
    """N 日价格相对位置（0=最低，1=最高）的反转因子。

    Mechanism: 近 N 日低位股 = 已超卖 → 反弹概率高（与 short_reversal 类似但更稳健）。
    Positive = 当前在 N 日低位。
    """
    rolling_min = close.rolling(n).min()
    rolling_max = close.rolling(n).max()
    pos = (close - rolling_min) / (rolling_max - rolling_min + 1e-8)
    return safe_zscore(mad_clip(-pos))


def vol_breakout(volume: pd.DataFrame, short: int = 5, long: int = 20) -> pd.DataFrame:
    """量比突破 (vol_ratio shorted/long) z-scored.

    Mechanism: 突然放量 → 资金关注度 + 信息冲击 → 短期 alpha (A 股散户驱动)。
    Positive = 近期 short 日量能显著高于 long 日 baseline。
    """
    vol_ratio = volume.rolling(short).mean() / (volume.rolling(long).mean() + 1)
    return safe_zscore(mad_clip(vol_ratio))


def amplitude_mean(close: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """N 日日内振幅均值（高 - 低）/ close 的 proxy。

    用 close-to-close 波动率近似（缺 high/low panel 数据时的替代）。
    Mechanism: 高波动股 → 风险溢价 / 注意力溢价 (A 股低波因子的对立面)。
    Positive = 高波动。
    """
    ret = close.pct_change(fill_method=None)
    amp = ret.abs().rolling(n).mean()
    return safe_zscore(mad_clip(amp))


def ret_zscore_cross(close: pd.DataFrame, n: int = 20) -> pd.DataFrame:
    """N 日累计收益的截面 z-score（动量截面排序）。

    与 mom_n 区别：这里做截面标准化，重点是相对排名而非绝对幅度。
    Positive = N 日累计 return 截面排名高。
    """
    ret_n = close / close.shift(n) - 1
    return safe_zscore(mad_clip(ret_n))
