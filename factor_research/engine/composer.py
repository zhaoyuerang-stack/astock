"""
多因子合成模块

支持三种合成方式：
  equal_weight  — 等权打分合成（快速baseline）
  ic_weight     — 滚动IC加权（过去N期IC均值为权重）
  pca           — PCA提取第一主成分（正交化，去共线性）
"""
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA


def equal_weight(factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    factors: {name: date×code DataFrame}，每个因子已中性化标准化
    返回等权合成因子
    """
    aligned = list(factors.values())
    combined = sum(aligned) / len(aligned)
    return combined


def ic_weight(
    factors: dict[str, pd.DataFrame],
    forward_ret: pd.DataFrame,
    ic_window: int = 12,
) -> pd.DataFrame:
    """
    滚动IC加权：用过去ic_window期的IC均值作为各因子权重。
    IC为负的因子自动取反方向。
    """
    from engine.backtest import calc_ic

    # 先算各因子的IC时间序列
    ic_series = {name: calc_ic(f, forward_ret) for name, f in factors.items()}

    dates = sorted(set.intersection(*[set(f.index) for f in factors.values()]))
    result = {}

    for dt in dates:
        weights = {}
        for name, ic in ic_series.items():
            past_ic = ic[ic.index < dt].tail(ic_window)
            if len(past_ic) < 3:
                weights[name] = 0.0
            else:
                weights[name] = past_ic.mean()   # 负IC自动减权/反向

        total_abs = sum(abs(w) for w in weights.values())
        if total_abs < 1e-6:
            continue

        # 归一化权重
        norm_w = {n: w / total_abs for n, w in weights.items()}

        row = sum(
            factors[n].loc[dt] * w
            for n, w in norm_w.items()
            if dt in factors[n].index
        )
        result[dt] = row

    return pd.DataFrame(result).T


def pca_composite(
    factors: dict[str, pd.DataFrame],
    n_components: int = 1,
) -> pd.DataFrame:
    """
    每个截面对各因子值做PCA，取第一主成分作为合成因子。
    适用于因子间高度相关时去冗余。
    """
    names = list(factors.keys())
    dates = sorted(set.intersection(*[set(f.index) for f in factors.values()]))
    result = {}

    for dt in dates:
        cols = {}
        for name in names:
            if dt in factors[name].index:
                cols[name] = factors[name].loc[dt]
        df = pd.DataFrame(cols).dropna()
        if len(df) < 50 or df.shape[1] < 2:
            continue
        pca = PCA(n_components=n_components)
        pc = pca.fit_transform(df.values)[:, 0]
        # 保证第一主成分与第一个因子同向
        if np.corrcoef(df.iloc[:, 0].values, pc)[0, 1] < 0:
            pc = -pc
        result[dt] = pd.Series(pc, index=df.index)

    return pd.DataFrame(result).T


def factor_corr_matrix(
    factors: dict[str, pd.DataFrame],
    sample_dates: int = 60,
) -> pd.DataFrame:
    """
    计算因子间的平均截面相关系数矩阵（用最近sample_dates个截面的均值）。
    用于诊断因子冗余度。
    """
    names = list(factors.keys())
    dates = sorted(set.intersection(*[set(f.index) for f in factors.values()]))[-sample_dates:]

    corr_accum = pd.DataFrame(0.0, index=names, columns=names)
    count = 0

    for dt in dates:
        cols = {}
        for name in names:
            if dt in factors[name].index:
                cols[name] = factors[name].loc[dt]
        df = pd.DataFrame(cols).dropna()
        if len(df) < 30:
            continue
        corr_accum += df.corr(method="spearman")
        count += 1

    return (corr_accum / max(count, 1)).round(3)
