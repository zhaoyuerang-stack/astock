"""Centralised schema definitions for the data lake.

All field names, rename mappings, and type specs live here so that no other
module hard-codes raw source column names.
"""

# ---------------------------------------------------------------------------
# Price / volume
# ---------------------------------------------------------------------------
PRICE_FIELDS = ["date", "open", "high", "low", "close", "volume", "amount"]
RAW_PRICE_FIELDS = ["date", "raw_open", "raw_high", "raw_low", "raw_close"]

# ---------------------------------------------------------------------------
# Fundamental (from yjbb_em batch source)
# ---------------------------------------------------------------------------
FUNDAMENTAL_FIELDS = [
    "roe",
    "eps",
    "eps_ttm",
    "bps",
    "revenue",
    "net_profit",
    "gross_margin",
    "cfo_ps",
    "revenue_yoy",
    "net_profit_yoy",
    "industry",
]

# Eastmoney yjbb_em 批量接口: 原始列名 → 标准列名
YJBB_RENAME = {
    "股票代码": "code",
    "每股收益": "eps",
    "营业总收入-营业总收入": "revenue",
    "营业总收入-同比增长": "revenue_yoy",
    "净利润-净利润": "net_profit",
    "净利润-同比增长": "net_profit_yoy",
    "每股净资产": "bps",
    "净资产收益率": "roe",
    "每股经营现金流量": "cfo_ps",
    "销售毛利率": "gross_margin",
    "所处行业": "industry",
    "最新公告日期": "ann_date",
}

# 逐只财务源 (Eastmoney stock_financial_abstract) — 已废弃,保留映射供兼容
EM_FIN_RENAME = {
    "归母净利润": "net_profit_parent",
    "营业总收入": "revenue",
    "净利润": "net_profit",
    "扣非净利润": "net_profit_deduct",
    "经营现金流量净额": "cfo",
    "基本每股收益": "eps",
    "每股净资产": "bps",
    "净资产收益率(ROE)": "roe",
    "毛利率": "gross_margin",
    "资产负债率": "debt_ratio",
    "每股经营现金流": "cfo_ps",
}

# ---------------------------------------------------------------------------
# Capital (margin financing + northbound)
# ---------------------------------------------------------------------------
CAPITAL_FIELDS = [
    "margin_balance",
    "margin_buy",
    "short_balance",
    "short_vol",
    "northbound_hold_shares",
    "northbound_hold_value",
    "northbound_hold_pct",
    "northbound_value_chg_1d",
    "northbound_value_chg_5d",
    "northbound_value_chg_10d",
    "northbound_hold_shares_chg_1d",
    "northbound_buy_value_1d",
]

# 沪深交易所两融明细字段统一
MARGIN_RENAME = {
    "标的证券代码": "code",
    "证券代码": "code",
    "融资余额": "margin_balance",
    "融资买入额": "margin_buy",
    "融券余量": "short_vol",
    "融券余额": "short_balance",
    "融券卖出量": "short_sell",
}

# 北向持股每日个股统计字段统一
NORTHBOUND_RENAME = {
    "持股日期": "date",
    "股票代码": "code",
    "股票简称": "name",
    "当日收盘价": "close",
    "当日涨跌幅": "pct_chg",
    "持股数量": "northbound_hold_shares",
    "持股市值": "northbound_hold_value",
    "持股数量占发行股百分比": "northbound_hold_pct",
    "持股数量占A股百分比": "northbound_hold_pct",
    "持股市值变化-1日": "northbound_value_chg_1d",
    "持股市值变化-5日": "northbound_value_chg_5d",
    "持股市值变化-10日": "northbound_value_chg_10d",
    "今日增持股数": "northbound_hold_shares_chg_1d",
    "今日增持资金": "northbound_buy_value_1d",
    "今日持股市值变化": "northbound_value_chg_1d",
}

# 北向单股历史字段统一 (stock_hsgt_individual_em)
NORTHBOUND_INDIVIDUAL_RENAME = {
    "持股日期": "date",
    "股票代码": "code",
    "股票简称": "name",
    "当日收盘价": "close",
    "当日涨跌幅": "pct_chg",
    "持股数量": "northbound_hold_shares",
    "持股市值": "northbound_hold_value",
    "持股数量占发行股百分比": "northbound_hold_pct",
    "持股数量占A股百分比": "northbound_hold_pct",
    "今日增持股数": "northbound_hold_shares_chg_1d",
    "今日增持资金": "northbound_buy_value_1d",
    "今日持股市值变化": "northbound_value_chg_1d",
}

# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------
META_SCHEMA = {
    "trade_calendar": ["date"],
    "codes": ["code", "name"],
    "st_history": ["code", "date", "st_flag"],
    "list_date": ["code", "list_date"],
}

# ---------------------------------------------------------------------------
# Data lake directory layout
# ---------------------------------------------------------------------------
LAKE_DIRS = {
    "price_daily": "data_lake/price/daily",
    "price_daily_raw": "data_lake/price/daily_raw",
    "price_weekly": "data_lake/price/weekly",
    "price_monthly": "data_lake/price/monthly",
    "fundamental": "data_lake/fundamental",
    "fundamental_batch": "data_lake/fundamental_batch.parquet",
    "capital_margin": "data_lake/capital/margin",
    "capital_northbound": "data_lake/capital/northbound",
    "capital_northbound_stock": "data_lake/capital/northbound_stock",
    "capital_margin_all": "data_lake/capital/margin_all.parquet",
    "capital_northbound_all": "data_lake/capital/northbound_all.parquet",
    "meta": "data_lake/meta",
}
