"""
用 akshare 新浪源下载全市场A股后复权日线（含创业板/科创板/小盘）
突破沪市主板样本偏差。新浪源走代理可达。
"""
import warnings; warnings.filterwarnings("ignore")
import os, time, sys
import pandas as pd
import numpy as np
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import akshare as ak

OUT = Path("data_full")
OUT.mkdir(exist_ok=True)
START = "20180101"

def to_sina(code):
    if code.startswith("6"): return "sh" + code   # 含688科创板
    if code.startswith(("0", "3")): return "sz" + code
    return None   # 4/8北交所跳过

def get_codes():
    cache = OUT / "_codes.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    df = ak.stock_info_a_code_name()
    df.to_parquet(cache, index=False)
    return df

def fetch_one(code, name):
    out = OUT / f"kline_{code}.parquet"
    if out.exists():
        return "cached"
    sym = to_sina(code)
    if sym is None:
        return "skip"
    for attempt in range(3):
        try:
            df = ak.stock_zh_a_daily(symbol=sym, start_date=START, adjust="hfq")
            if df is None or df.empty:
                return "empty"
            df["date"] = pd.to_datetime(df["date"])
            if "amount" not in df.columns:
                df["amount"] = df["volume"] * df["close"]
            keep = [c for c in ["date","open","close","high","low","volume","amount","turnover","outstanding_share"] if c in df.columns]
            df[keep].to_parquet(out, index=False)
            return "ok"
        except Exception as e:
            if attempt == 2:
                return f"err"
            time.sleep(0.5)
    return "err"

def main():
    codes_df = get_codes()
    codes = [(str(r["code"]), str(r["name"])) for _, r in codes_df.iterrows()]
    # 跳过北交所、ST、退市
    codes = [(c,n) for c,n in codes if to_sina(c) and "ST" not in n and "退" not in n]
    print(f"全市场目标: {len(codes)} 只", flush=True)
    print(f"已缓存: {len(list(OUT.glob('kline_*.parquet')))} 只", flush=True)

    cnt = {"ok":0,"cached":0,"empty":0,"err":0,"skip":0}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_one, c, n): c for c, n in codes}
        for i, fut in enumerate(as_completed(futs)):
            cnt[fut.result()] = cnt.get(fut.result(),0) + 1
            if (i+1) % 300 == 0:
                el = time.time()-t0
                eta = el/(i+1)*(len(codes)-i-1)
                print(f"  [{i+1}/{len(codes)}] ok={cnt['ok']} cached={cnt['cached']} "
                      f"empty={cnt['empty']} err={cnt['err']} 用时={el:.0f}s ETA={eta:.0f}s", flush=True)
    print(f"完成! {cnt} 总用时={time.time()-t0:.0f}s", flush=True)
    print(f"data_full总文件: {len(list(OUT.glob('kline_*.parquet')))}", flush=True)

if __name__ == "__main__":
    ROOT = Path(__file__).resolve().parents[2]
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    main()
