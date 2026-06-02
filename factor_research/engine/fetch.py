"""
API数据拉取与本地缓存模块

数据说明（经验证）：
- K线价格为后复权价格，无需手动调整
- 原始数据存在重复行：同一日期两条记录，volume 相差100倍（股 vs 手）
  修复方式：保留 volume 最大的那条（单位：股）
"""
import json
import time
import requests
import pandas as pd
from pathlib import Path

BASE_URL = "http://192.168.1.250:8000"
CACHE_DIR = Path(__file__).parent.parent / "data"
CACHE_DIR.mkdir(exist_ok=True)


def _get(path: str, params: dict = None, timeout: int = 30) -> dict:
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _clean_kline(df: pd.DataFrame) -> pd.DataFrame:
    """清洗K线：去除重复日期（保留volume最大的行），排序，重置索引"""
    df["date"] = pd.to_datetime(df["date"])
    # 同一日期可能有 volume 单位不同的两条，保留最大值（单位：股）
    df = df.sort_values(["date", "volume"], ascending=[True, False])
    df = df.drop_duplicates(subset=["date"], keep="first")
    df = df.reset_index(drop=True)
    return df


def get_stock_list() -> list[dict]:
    """返回全部股票信息列表 [{code, name, market, industry}, ...]"""
    cache = CACHE_DIR / "stocks.json"
    if cache.exists():
        return json.loads(cache.read_text())
    data = _get("/stocks")
    cache.write_text(json.dumps(data))
    return data


def get_stock_codes() -> list[str]:
    return [s["code"] if isinstance(s, dict) else s for s in get_stock_list()]


def get_stock_industry() -> pd.DataFrame:
    """返回 code→industry 映射"""
    cache = CACHE_DIR / "industry.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    stocks = get_stock_list()
    df = pd.DataFrame(stocks)[["code", "industry"]].dropna()
    df.to_parquet(cache, index=False)
    return df


def get_kline_daily(code: str, start: str = "2018-01-01", end: str = None) -> pd.DataFrame:
    """
    获取单只股票日K线（后复权）。
    本地有缓存且覆盖请求范围时直接读缓存。
    """
    cache = CACHE_DIR / f"kline_{code}.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        latest = df["date"].max()
        # 缓存够用则直接返回截取
        if end is None or latest >= pd.Timestamp(end):
            mask = df["date"] >= pd.Timestamp(start) if start else slice(None)
            return df[mask].reset_index(drop=True)

    params = {"code": code, "start": start, "limit": 5000}
    if end:
        params["end"] = end
    data = _get("/kline/daily", params)
    if not data.get("data"):
        return pd.DataFrame()

    df = _clean_kline(pd.DataFrame(data["data"]))
    df.to_parquet(cache, index=False)
    return df


def get_valuation(code: str, start: str = "2018-01-01") -> pd.DataFrame:
    """PE/PB/市值/换手率历史"""
    cache = CACHE_DIR / f"val_{code}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    data = _get(f"/valuation/{code}", {"start": start, "limit": 3000})
    if not data.get("data"):
        return pd.DataFrame()
    df = pd.DataFrame(data["data"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    df.to_parquet(cache, index=False)
    return df


def get_fundamental(code: str, limit: int = 40) -> pd.DataFrame:
    """财务季报（含利润表/资产负债/现金流主要指标）"""
    cache = CACHE_DIR / f"fundamental_{code}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    data = _get(f"/fundamental/{code}", {"limit": limit})
    if not data.get("data"):
        return pd.DataFrame()
    df = pd.DataFrame(data["data"])
    date_col = next((c for c in ["ann_date", "report_date"] if c in df.columns), None)
    if date_col:
        df["date"] = pd.to_datetime(df[date_col])
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    df.to_parquet(cache, index=False)
    return df


def get_moneyflow(code: str, limit: int = 500) -> pd.DataFrame:
    """日级资金流"""
    cache = CACHE_DIR / f"flow_{code}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    data = _get(f"/flow/moneyflow/daily/{code}", {"limit": limit})
    if not data.get("data"):
        return pd.DataFrame()
    df = pd.DataFrame(data["data"])
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    df.to_parquet(cache, index=False)
    return df


def batch_fetch_kline(
    codes: list[str],
    start: str = "2018-01-01",
    sleep: float = 0.05,
) -> pd.DataFrame:
    """
    批量拉取日K线，返回长表 [date, code, close, volume, amount]
    有本地缓存的股票直接读取，大幅加速二次运行。
    """
    frames = []
    for i, code in enumerate(codes):
        try:
            df = get_kline_daily(code, start)
            if df.empty:
                continue
            df = df[["date", "close", "volume", "amount"]].copy()
            df["code"] = code
            frames.append(df)
        except Exception as e:
            print(f"[warn] {code}: {e}")
        if i % 200 == 0:
            print(f"  [{i}/{len(codes)}] 已完成 {i} 只")
        time.sleep(sleep)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def verify_kline_quality(code: str = "600519") -> None:
    """
    数据质量验证：检查重复行和价格连续性
    默认用贵州茅台（大额分红，最易暴露复权问题）
    """
    df = get_kline_daily(code, "2018-01-01")
    print(f"[{code}] 总行数: {len(df)}")
    print(f"  日期范围: {df['date'].min().date()} ~ {df['date'].max().date()}")
    print(f"  重复日期: {df['date'].duplicated().sum()}")

    # 检测异常大跌（>15%单日跌幅，可能是未复权缺口）
    ret = df["close"].pct_change()
    big_drops = df[ret < -0.15][["date", "close"]].copy()
    big_drops["ret"] = ret[ret < -0.15].values
    if big_drops.empty:
        print("  未发现 >15% 单日异常跌幅（复权正常）")
    else:
        print(f"  发现 {len(big_drops)} 处 >15% 单日跌幅（需核查是否除权）:")
        print(big_drops.to_string(index=False))
