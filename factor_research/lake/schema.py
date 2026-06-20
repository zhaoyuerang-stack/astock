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

# ---------------------------------------------------------------------------
# Daily basic (tushare 每日指标:市值/股本/换手/估值)
# ---------------------------------------------------------------------------
DAILY_BASIC_FIELDS = [
    "total_share",      # 总股本(万股)
    "float_share",      # 流通股本(万股)
    "total_mv",         # 总市值(万元)
    "circ_mv",          # 流通市值(万元)
    "turnover_rate",    # 换手率(%)
    "turnover_rate_f",  # 换手率(自由流通股)
    "pe",               # 市盈率(总市值/净利润)
    "pe_ttm",           # 市盈率(TTM)
    "pb",               # 市净率
    "ps",               # 市销率
    "ps_ttm",           # 市销率(TTM)
    "dv_ratio",         # 股息率(%)
    "dv_ttm",           # 股息率(TTM)
]

# ---------------------------------------------------------------------------
# Fina indicator (tushare 财务指标:杠杆/质量/成长 → Barra 基本面风格)
# ---------------------------------------------------------------------------
FINA_INDICATOR_FIELDS = [
    "roe",                # 净资产收益率
    "roe_waa",            # 加权 ROE
    "roa",                # 总资产收益率
    "debt_to_assets",     # 资产负债率 → Leverage
    "assets_to_eqt",      # 权益乘数
    "netprofit_margin",   # 净利率
    "grossprofit_margin", # 毛利率
    "current_ratio",      # 流动比率
    "quick_ratio",        # 速动比率
    "or_yoy",             # 营收同比 → Growth
    "netprofit_yoy",      # 净利同比 → Growth
    "assets_turn",        # 总资产周转率 → Quality
    "ar_turn",            # 应收账款周转率
    "ocfps",              # 每股经营现金流
    "fcff",               # 企业自由现金流
    "eps", "bps", "cfps",
]

# ---------------------------------------------------------------------------
# Tushare 扩展维度字段(by_date 当日对齐 / anndate 公告日 ffill)
# ---------------------------------------------------------------------------
MONEYFLOW_FIELDS = [  # 资金流(by_date):大中小单买卖额 + 净流入(万元)
    "buy_sm_amount", "sell_sm_amount", "buy_md_amount", "sell_md_amount",
    "buy_lg_amount", "sell_lg_amount", "buy_elg_amount", "sell_elg_amount", "net_mf_amount",
]
STK_LIMIT_FIELDS = ["up_limit", "down_limit"]            # 涨跌停价(by_date)
SUSPEND_FIELDS = ["suspend_type"]                        # 停复牌(by_date)
FORECAST_FIELDS = [                                      # 业绩预告(anndate)
    "type", "p_change_min", "p_change_max", "net_profit_min", "net_profit_max",
]
EXPRESS_FIELDS = [                                       # 业绩快报(anndate)
    "revenue", "n_income", "diluted_eps", "diluted_roe", "yoy_net_profit",
]
HOLDERNUMBER_FIELDS = ["holder_num"]                     # 股东户数(anndate)
INDEX_DAILY_FIELDS = ["close", "open", "high", "low", "pct_chg", "vol", "amount"]  # 基准指数(by_date)
CYQ_FIELDS = ["cost_5pct", "cost_50pct", "cost_95pct", "weight_avg", "winner_rate"]  # 筹码(by_date)
HOLDERTRADE_FIELDS = ["in_de", "change_vol", "change_ratio", "after_ratio", "avg_price"]  # 增减持(anndate)
ADJ_FACTOR_FIELDS = ["adj_factor"]                                                    # 复权因子(by_date)
INCOME_FIELDS = ["revenue", "operate_profit", "total_profit", "n_income",            # 利润表(anndate)
                 "n_income_attr_p", "ebit", "ebitda"]
BALANCESHEET_FIELDS = ["total_assets", "total_liab", "total_hldr_eqy_exc_min_int",    # 资产负债表(anndate)
                       "total_cur_assets", "total_cur_liab", "money_cap", "lt_borr", "st_borr",
                       "accounts_receiv", "notes_receiv", "inventories", "acct_payable", "notes_payable"]  # 议价权/CCC
CASHFLOW_FIELDS = ["n_cashflow_act", "n_cashflow_inv_act", "n_cash_flows_fnc_act",    # 现金流量表(anndate)
                   "c_pay_acq_const_fiolta", "free_cashflow"]
DIVIDEND_FIELDS = ["stk_div", "cash_div", "cash_div_tax"]                             # 分红(anndate)

# dataset → (store 相对路径, 口径 by_date|anndate, 默认字段)
TUSHARE_DATASETS = {
    "daily_basic":   ("daily_basic/daily_basic_all.parquet", "by_date", DAILY_BASIC_FIELDS),
    "moneyflow":     ("moneyflow/moneyflow_all.parquet", "by_date", MONEYFLOW_FIELDS),
    "stk_limit":     ("market/stk_limit_all.parquet", "by_date", STK_LIMIT_FIELDS),
    "suspend":       ("market/suspend_all.parquet", "by_date", SUSPEND_FIELDS),
    "fina_indicator": ("financials/fina_indicator_all.parquet", "anndate", FINA_INDICATOR_FIELDS),
    "forecast":      ("event/forecast_all.parquet", "anndate", FORECAST_FIELDS),
    "express":       ("event/express_all.parquet", "anndate", EXPRESS_FIELDS),
    "holdernumber":  ("holder/holdernumber_all.parquet", "anndate", HOLDERNUMBER_FIELDS),
    "index_daily":   ("index/index_daily_all.parquet", "by_date", INDEX_DAILY_FIELDS),
    "cyq_perf":      ("cyq/cyq_perf_all.parquet", "by_date", CYQ_FIELDS),
    "holdertrade":   ("holder/holdertrade_all.parquet", "anndate", HOLDERTRADE_FIELDS),
    "adj_factor":    ("adj_factor/adj_factor_all.parquet", "by_date", ADJ_FACTOR_FIELDS),
    "income":        ("financials/income_all.parquet", "anndate", INCOME_FIELDS),
    "balancesheet":  ("financials/balancesheet_all.parquet", "anndate", BALANCESHEET_FIELDS),
    "cashflow":      ("financials/cashflow_all.parquet", "anndate", CASHFLOW_FIELDS),
    "dividend":      ("corp_action/dividend_all.parquet", "anndate", DIVIDEND_FIELDS),
}

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
