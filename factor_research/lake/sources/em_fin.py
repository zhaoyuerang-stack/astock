"""东财财务源——宽表转长表 + 防未来函数（报告期→披露可用日）"""
import akshare as ak
import pandas as pd
from lake.base import Fetcher, RateLimiter

# 关键财务指标：中文名 → 英文字段
KEY_INDICATORS = {
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

# 财报披露滞后（防未来函数）：报告期 → 可用日 = 报告期 + N天
DISCLOSURE_LAG = {(3, 31): 45, (6, 30): 60, (9, 30): 45, (12, 31): 120}


class EastmoneyFinanceFetcher(Fetcher):
    """东财财务摘要(stock_financial_abstract)，季频，防未来函数对齐"""

    def __init__(self, out_dir: str = "data_lake/fundamental", **kw):
        super().__init__(
            name="em_finance", out_dir=out_dir,
            limiter=RateLimiter(min_interval=1.1, jitter=(0.1, 0.3)),  # 东财封禁严(5分钟≥300),降到<1请求/秒
            max_workers=kw.pop("max_workers", 2), timeout=20, **kw,
        )

    @staticmethod
    def avail_date(report_date: pd.Timestamp) -> pd.Timestamp:
        """报告期 → 披露可用日（防未来函数）"""
        lag = DISCLOSURE_LAG.get((report_date.month, report_date.day), 60)
        return report_date + pd.Timedelta(days=lag)

    def fetch_one(self, code: str):
        df = ak.stock_financial_abstract(symbol=code)
        if df is None or df.empty or "指标" not in df.columns:
            return None
        # 报告期列（8位数字）
        periods = [c for c in df.columns if c.isdigit() and len(c) == 8]
        if not periods:
            return None
        # 去重指标名后转索引
        df = df.drop_duplicates("指标", keep="first").set_index("指标")

        rows = []
        for p in periods:
            row = {"report_date": p}
            for cn, en in KEY_INDICATORS.items():
                if cn in df.index:
                    row[en] = pd.to_numeric(df.loc[cn, p], errors="coerce")
            rows.append(row)

        out = pd.DataFrame(rows)
        out["report_date"] = pd.to_datetime(out["report_date"], format="%Y%m%d")
        out["avail_date"] = out["report_date"].apply(self.avail_date)   # 关键：可用日
        out = out.sort_values("report_date").reset_index(drop=True)
        return out
