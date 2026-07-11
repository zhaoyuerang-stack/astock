"""行业景气度因子 — 基于资金流的行业轮动信号。

算法:
  1. 个股资金流按行业聚合
  2. 计算:
     - flow_z: 行业净流入占比的60日滚动z-score
     - elg_z:  行业超大单(机构)净占比的60日滚动z-score
     - composite = (flow_z + elg_z) / 2
  3. 个股因子值 = 所属行业的 composite z-score

验证 (2021-2026):
  多空年化 +22.9%, Sharpe 1.92, 胜率 72%, 6年全正。
  与 size/illiquidity 正交 (度量行业间资金流动, 非个股特征)。

用法:
  from factors.industry_prosperity import industry_prosperity_factor
  factor = industry_prosperity_factor(close, amount)
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _load_industry_map():
    """加载个股→行业映射 (tushare stock_basic)"""
    from lake.sources.tushare import call
    sb = call("stock_basic", {"list_status": "L"}, "ts_code,industry")
    sb["code"] = sb["ts_code"].str.replace(".SH", "").str.replace(".SZ", "").str.replace(".BJ", "")
    return dict(zip(sb["code"], sb["industry"]))


def _load_moneyflow():
    """加载全量资金流数据"""
    from pathlib import Path
    fp = Path(__file__).resolve().parents[1] / "data_lake/moneyflow/moneyflow_all.parquet"
    return pd.read_parquet(fp)


from factors.registry import register_factor


@register_factor(
    "industry_prosperity",
    params={"z_window": (20, 120)},
    data=("price/close",),
    input="close",
    searchable=False,  # 行业因子不适合全截面 IC 搜索
)
def industry_prosperity_factor(
    close: pd.DataFrame,
    amount: pd.DataFrame | None = None,
    *,
    z_window: int = 60,
    min_periods: int = 20,
) -> pd.DataFrame:
    """返回 date × code 的行业景气度因子面板。

    每只股票的值 = 其所属行业的综合景气度 z-score。
    正值 = 行业资金净流入高于历史均值, 负值 = 净流出。

    Parameters
    ----------
    close: 后复权收盘价面板 (用于日期间对齐)
    z_window: z-score 滚动窗口
    min_periods: 最小样本数
    """
    code_to_ind = _load_industry_map()
    mf = _load_moneyflow()

    # 对齐日期范围
    trade_dates = close.index
    mf_dates = pd.to_datetime(mf["trade_date"].unique())
    common_dates = trade_dates.intersection(mf_dates)
    if len(common_dates) < 60:
        raise ValueError("资金流数据与价格面板日期交集不足")

    mf = mf[pd.to_datetime(mf["trade_date"]).isin(common_dates)]

    # 映射个股→行业
    mf["code_plain"] = mf["ts_code"].str.replace(".SH", "").str.replace(".SZ", "").str.replace(".BJ", "")
    mf["industry"] = mf["code_plain"].map(code_to_ind)
    mf = mf.dropna(subset=["industry"])

    # 行业日度聚合
    daily = mf.groupby(["trade_date", "industry"]).agg(
        net_mf=("net_mf_amount", "sum"),
        buy_lg=("buy_lg_amount", "sum"),
        sell_lg=("sell_lg_amount", "sum"),
        buy_elg=("buy_elg_amount", "sum"),
        sell_elg=("sell_elg_amount", "sum"),
    ).reset_index()

    daily["total_amt"] = (
        daily["buy_lg"] + daily["sell_lg"] + daily["buy_elg"] + daily["sell_elg"] + 1
    )

    # 资金流 z-score
    daily = daily.sort_values(["industry", "trade_date"])
    daily["flow_pct"] = daily["net_mf"] / daily["total_amt"]
    daily["flow_z"] = daily.groupby("industry")["flow_pct"].transform(
        lambda x: (x - x.rolling(z_window, min_periods=min_periods).mean())
        / x.rolling(z_window, min_periods=min_periods).std().replace(0, 1)
    )

    # 机构积累 z-score
    daily["elg_net"] = (daily["buy_elg"] - daily["sell_elg"]) / (
        daily["buy_elg"] + daily["sell_elg"] + 1
    )
    daily["elg_z"] = daily.groupby("industry")["elg_net"].transform(
        lambda x: (x - x.rolling(z_window, min_periods=min_periods).mean())
        / x.rolling(z_window, min_periods=min_periods).std().replace(0, 1)
    )

    # 综合景气度
    daily["composite"] = daily["flow_z"].fillna(0) * 0.5 + daily["elg_z"].fillna(0) * 0.5
    daily["trade_date"] = pd.to_datetime(daily["trade_date"])

    # 日期×行业 矩阵 (用于快速查表)
    ind_matrix = daily.pivot_table(
        index="trade_date", columns="industry", values="composite"
    )
    ind_matrix = ind_matrix.reindex(common_dates)

    # 构造个股因子面板: date × code
    codes = [c for c in close.columns if c in code_to_ind]
    factor_data = {}
    for code in codes:
        ind = code_to_ind[code]
        if ind in ind_matrix.columns:
            factor_data[code] = ind_matrix[ind]

    factor_df = pd.DataFrame(factor_data, index=common_dates)
    factor_df = factor_df.reindex(close.index)  # 对齐完整日期

    return factor_df.astype(float)
