"""
数据加载层：多维度对齐面板（防未来函数）

把数据湖的价量+财务+估值统一成 date×code 面板，供因子计算。
关键：财务按 avail_date(披露可用日) 对齐，杜绝未来函数。
"""
import numpy as np
import pandas as pd
from pathlib import Path

LAKE = Path(__file__).parent.parent / "data_lake"


# ── 价量面板 ──
def load_prices(codes=None, start="2010-01-01", fields=("close", "volume", "amount")):
    """加载日线 → {field: date×code 宽表}"""
    daily = LAKE / "price/daily"
    files = ([daily / f"{c}.parquet" for c in codes] if codes
             else sorted(daily.glob("*.parquet")))
    frames = []
    for fp in files:
        if not fp.exists():
            continue
        df = pd.read_parquet(fp, columns=["date"] + list(fields))
        df["code"] = fp.stem
        frames.append(df)
    long = pd.concat(frames, ignore_index=True)
    long = long[long["date"] >= pd.Timestamp(start)]
    return {f: long.pivot(index="date", columns="code", values=f) for f in fields}


# ── 财务面板（批量长表，防未来函数对齐）──
FUND_FIELDS = ["roe", "eps", "eps_ttm", "bps", "revenue", "net_profit",
               "gross_margin", "cfo_ps", "revenue_yoy", "net_profit_yoy"]


def load_fundamental_panel(trade_dates, codes=None, fields=FUND_FIELDS):
    """
    从批量长表 fundamental_batch.parquet 加载，对齐到交易日面板 {field: date×code}。
    用 avail_date(公告日) 作为生效日 ffill，确保 T 日只用 T 日前已披露的财务（防未来函数）。
    """
    fp = LAKE / "fundamental_batch.parquet"
    if not fp.exists():
        return {f: pd.DataFrame() for f in fields}
    df = pd.read_parquet(fp).dropna(subset=["avail_date"])
    if codes:
        df = df[df["code"].isin(codes)]
    trade_idx = pd.DatetimeIndex(trade_dates)
    panels = {}
    for f in fields:
        if f not in df.columns:
            continue
        sub = (df[["avail_date", "code", f]].dropna()
               .sort_values("avail_date")
               .drop_duplicates(["code", "avail_date"], keep="last"))
        pivot = sub.pivot_table(index="avail_date", columns="code", values=f, aggfunc="last")
        # 公告日生效，ffill 到交易日（T日只用T日前已公告的财务）
        aligned = pivot.reindex(pivot.index.union(trade_idx)).ffill().reindex(trade_idx)
        panels[f] = aligned
    return panels


# ── 估值自算（财务+价量）──
def compute_valuation(close, eps, bps):
    """PE=close/EPS, PB=close/BPS（eps/bps 已是 date×code 防未来函数面板）"""
    pe = close / eps.replace(0, np.nan)
    pb = close / bps.replace(0, np.nan)
    return {"pe": pe, "pb": pb}


# ── 不复权价加载（估值专用，通达信原始价）──
def load_raw_close(codes=None, start="2010-01-01"):
    """加载不复权close → date×code（PE/PB自算必须用不复权价）"""
    raw_dir = LAKE / "price/daily_raw"
    files = ([raw_dir / f"{c}.parquet" for c in codes] if codes
             else sorted(raw_dir.glob("*.parquet")))
    frames = []
    for fp in files:
        if not fp.exists():
            continue
        df = pd.read_parquet(fp)
        df["code"] = fp.stem
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    long = pd.concat(frames, ignore_index=True)
    long = long[long["date"] >= pd.Timestamp(start)]
    return long.pivot(index="date", columns="code", values="raw_close")


# ── 资金面面板（两融/北向，按披露可用日滞后一日防未来函数）──
CAPITAL_FIELDS = [
    "margin_balance", "margin_buy", "short_balance", "short_vol",
    "northbound_hold_shares", "northbound_hold_value", "northbound_hold_pct",
    "northbound_value_chg_1d", "northbound_value_chg_5d", "northbound_value_chg_10d",
    "northbound_hold_shares_chg_1d", "northbound_buy_value_1d",
]


def _load_capital_long(name, codes=None, start="2010-01-01"):
    fp = LAKE / "capital" / f"{name}_all.parquet"
    if not fp.exists():
        return pd.DataFrame()
    df = pd.read_parquet(fp)
    if "date" not in df.columns or "code" not in df.columns:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    df["code"] = df["code"].astype(str).str.zfill(6)
    df = df[df["date"] >= pd.Timestamp(start)]
    if codes:
        df = df[df["code"].isin(codes)]
    return df


def load_capital_panel(trade_dates, codes=None, start="2010-01-01", fields=CAPITAL_FIELDS):
    """
    加载资金面长表并对齐成 date×code 面板。

    防未来函数：交易所/东财资金面数据通常在 T 日盘后发布，因此 T 日记录
    只允许从 T+1 起被策略看到。实现上 pivot 后统一 shift(1)。
    """
    trade_idx = pd.DatetimeIndex(trade_dates)
    frames = []
    for name in ["margin", "northbound"]:
        df = _load_capital_long(name, codes=codes, start=start)
        if not df.empty:
            frames.append(df)
    panels = {f: pd.DataFrame(index=trade_idx, columns=codes, dtype=float) for f in fields}
    if not frames:
        return panels
    long = pd.concat(frames, ignore_index=True, sort=False)
    for f in fields:
        if f not in long.columns:
            continue
        sub = long[["date", "code", f]].dropna()
        if sub.empty:
            continue
        pivot = sub.pivot_table(index="date", columns="code", values=f, aggfunc="last")
        aligned = pivot.reindex(pivot.index.union(trade_idx)).sort_index().shift(1).reindex(trade_idx)
        panels[f] = aligned.reindex(columns=codes)
    return panels


# ── 一站式加载 ──
def load_panel(codes=None, start="2010-01-01", with_fundamental=True):
    """返回统一的多维度面板 dict：close/volume/amount (+财务+估值)"""
    px = load_prices(codes, start)
    panel = dict(px)
    if with_fundamental:
        trade_dates = px["close"].index
        fund = load_fundamental_panel(trade_dates, codes)
        panel.update({f"fund_{k}": v for k, v in fund.items()})
        if "eps_ttm" in fund and "bps" in fund:
            raw_close = load_raw_close(codes, start)   # 不复权价算估值(防量纲错误)
            price_for_val = raw_close.reindex(index=px["close"].index) if not raw_close.empty else px["close"]
            val = compute_valuation(price_for_val, fund["eps_ttm"], fund["bps"])  # 用TTM EPS
            panel.update(val)
    return panel
