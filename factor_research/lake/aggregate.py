"""日线聚合 → 周线/月线"""
import pandas as pd
from pathlib import Path

AGG = {"open": "first", "high": "max", "low": "min",
       "close": "last", "volume": "sum", "amount": "sum"}


def aggregate_one(df: pd.DataFrame, freq: str) -> pd.DataFrame:
    d = df.set_index("date")
    cols = [c for c in AGG if c in d.columns]
    agg = d[cols].resample(freq).agg({c: AGG[c] for c in cols})
    return agg.dropna(subset=["close"]).reset_index()


def build_periodic(daily_dir: str = "data_lake/price/daily"):
    daily = Path(daily_dir)
    for period, freq in [("weekly", "W-FRI"), ("monthly", "ME")]:
        outdir = Path(f"data_lake/price/{period}")
        outdir.mkdir(parents=True, exist_ok=True)
        n = 0
        for fp in daily.glob("*.parquet"):
            df = pd.read_parquet(fp)
            if len(df) < 2:
                continue
            aggregate_one(df, freq).to_parquet(outdir / fp.name, index=False)
            n += 1
        print(f"[{period}] {n}只", flush=True)


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent.parent)
    build_periodic()
    # 验证茅台
    for period in ["weekly", "monthly"]:
        df = pd.read_parquet(f"data_lake/price/{period}/600519.parquet")
        print(f"\n茅台{period}: {len(df)}行 {df['date'].min().date()}~{df['date'].max().date()}")
        print(df.tail(2)[["date", "open", "high", "low", "close"]].to_string(index=False))
