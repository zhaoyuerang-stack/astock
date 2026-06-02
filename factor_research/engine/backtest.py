"""
因子回测引擎：IC分析 + 分层收益
"""
import numpy as np
import pandas as pd
from scipy.stats import spearmanr


def calc_ic(factor: pd.DataFrame, forward_ret: pd.DataFrame, method: str = "rank") -> pd.Series:
    """
    计算每个截面日期的IC
    factor/forward_ret: date×code 的DataFrame
    method: 'rank'=RankIC(ICIR更稳定), 'pearson'=PearsonIC
    """
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


def ic_summary(ic: pd.Series) -> dict:
    return {
        "IC_mean": ic.mean(),
        "IC_std": ic.std(),
        "ICIR": ic.mean() / ic.std() if ic.std() > 0 else np.nan,
        "IC>0_ratio": (ic > 0).mean(),
        "|IC|>0.02_ratio": (ic.abs() > 0.02).mean(),
        "count": len(ic),
    }


def stratify_return(
    factor: pd.DataFrame,
    forward_ret: pd.DataFrame,
    n_quantile: int = 5,
) -> pd.DataFrame:
    """
    分层回测：每个截面按因子值分成n_quantile组，计算各组平均收益
    返回 date×group 的收益率DataFrame
    """
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


def cumulative_return(group_ret: pd.DataFrame) -> pd.DataFrame:
    """将分层日度收益转为累计净值"""
    return (1 + group_ret).cumprod()


def long_short_return(group_ret: pd.DataFrame) -> pd.Series:
    """多空组合收益 = Q5 - Q1"""
    cols = sorted(group_ret.columns)
    return group_ret[cols[-1]] - group_ret[cols[0]]


def factor_summary(
    factor: pd.DataFrame,
    forward_ret: pd.DataFrame,
    factor_name: str = "factor",
    n_quantile: int = 5,
) -> dict:
    ic = calc_ic(factor, forward_ret)
    strat = stratify_return(factor, forward_ret, n_quantile)
    summary = ic_summary(ic)
    summary["factor"] = factor_name
    if strat.empty:
        summary["LS_annual"] = np.nan
        summary["LS_sharpe"] = np.nan
        summary["LS_maxdd"] = np.nan
    else:
        ls = long_short_return(strat)
        summary["LS_annual"] = ls.mean() * 252
        summary["LS_sharpe"] = ls.mean() / ls.std() * np.sqrt(252) if ls.std() > 0 else np.nan
        summary["LS_maxdd"] = ((1 + ls).cumprod() / (1 + ls).cumprod().cummax() - 1).min()
    return summary
