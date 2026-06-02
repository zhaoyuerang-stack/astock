"""
元数据构建：股票列表 / 交易日历 / 上市日
（交易日历和上市日依赖价量数据，下载完成后执行）
"""
import akshare as ak
import pandas as pd
from pathlib import Path

META = Path("data_lake/meta")
META.mkdir(parents=True, exist_ok=True)
PRICE = Path("data_lake/price/daily")


def build_stock_list():
    """全市场股票列表（code, name）"""
    df = ak.stock_info_a_code_name()
    df["code"] = df["code"].astype(str)
    df.to_parquet(META / "codes.parquet", index=False)
    print(f"[meta] 股票列表: {len(df)} 只")
    return df


def build_calendar():
    """
    交易日历 = 几只从不停牌的大盘股日期并集（茅台/平安/招商/浦发）。
    作为完整性校验和缺失检测的基准。
    """
    anchors = ["600519", "000001", "600036", "600000", "601398"]
    dates = set()
    for c in anchors:
        fp = PRICE / f"{c}.parquet"
        if fp.exists():
            dates |= set(pd.read_parquet(fp, columns=["date"])["date"])
    cal = pd.DatetimeIndex(sorted(dates))
    pd.DataFrame({"date": cal}).to_parquet(META / "trade_calendar.parquet", index=False)
    print(f"[meta] 交易日历: {len(cal)} 个交易日 {cal.min().date()}~{cal.max().date()}")
    return cal


def build_list_dates():
    """
    上市日（近似）= 每只价量首日。
    注：回溯起点2010，2010前上市的首日被截断为2010-01-04（标记为'≤2010'）；
    2010后上市的为真实上市日（用于识别次新股）。真实上市日可后续用个股信息接口补。
    """
    rows = []
    for fp in PRICE.glob("*.parquet"):
        df = pd.read_parquet(fp, columns=["date"])
        if len(df):
            first = df["date"].min()
            rows.append({
                "code": fp.stem,
                "first_date": first,
                "truncated": first <= pd.Timestamp("2010-01-05"),  # 可能2010前已上市
            })
    out = pd.DataFrame(rows).sort_values("code").reset_index(drop=True)
    out.to_parquet(META / "list_date.parquet", index=False)
    print(f"[meta] 上市日: {len(out)} 只 (其中{out['truncated'].sum()}只可能2010前上市)")
    return out


def build_all():
    build_stock_list()
    build_calendar()
    build_list_dates()
    print("[meta] 元数据构建完成")


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent.parent)
    build_all()
