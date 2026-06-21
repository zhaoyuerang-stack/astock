"""资金流因子 — 与价量(illiquidity/momentum/volatility)簇正交的独立数据族。

large_order_net_ratio: 大单+特大单净买入额 / 全部单子总成交额(自归一,无需额外加载
amount 面板)。moneyflow 是交易所 T 日盘后发布的当日量,与 close/amount 同口径,
不 shift(同 daily_basic 既有约定;真实下单时滞由 build_rebalance_weights 的 T+1
生效日统一兜底)。

数据来源:moneyflow/moneyflow_all.parquet(tushare moneyflow,已全量入库)。
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from factors.utils import mad_clip, safe_zscore

_BUY = ["buy_sm_amount", "buy_md_amount", "buy_lg_amount", "buy_elg_amount"]
_SELL = ["sell_sm_amount", "sell_md_amount", "sell_lg_amount", "sell_elg_amount"]


@lru_cache(maxsize=1)
def _load_moneyflow_cache():
    from lake.load_lake import load_tushare_panel
    trade_dates = pd.date_range("2010-01-01", "2030-01-01", freq="B")
    return load_tushare_panel("moneyflow", trade_dates, fields=_BUY + _SELL)


def _align_to_close(panel: pd.DataFrame, close: pd.DataFrame) -> pd.DataFrame:
    out = panel.reindex(close.index)
    common = close.columns.intersection(out.columns)
    return out[common].reindex(columns=close.columns)


def large_order_net_ratio(close, window: int = 5, **_):
    """(大单+特大单净买入) / 全部单子总成交额,滚动平滑;高值=主力资金净流入。"""
    panels = _load_moneyflow_cache()
    buy_total = sum(_align_to_close(panels[f], close) for f in _BUY)
    sell_total = sum(_align_to_close(panels[f], close) for f in _SELL)
    buy_large = _align_to_close(panels["buy_lg_amount"], close) + _align_to_close(panels["buy_elg_amount"], close)
    sell_large = _align_to_close(panels["sell_lg_amount"], close) + _align_to_close(panels["sell_elg_amount"], close)
    total = (buy_total + sell_total).rolling(window).mean()
    net_large = (buy_large - sell_large).rolling(window).mean()
    ratio = net_large / total.replace(0, np.nan)
    return safe_zscore(mad_clip(ratio.replace([np.inf, -np.inf], np.nan)))
