"""
增量更新（抓取方法的核心）——基于已有数据的 last_date，只抓新增，避免全量重下。

设计原则：
- 价量：每只读现有最新date，腾讯从 last_date+1 增量下载新交易日，merge去重
- 财务：读现有最新报告期，yjbb 批量补新季度（按报告期，避封禁）
- 两融：读现有最新date，补新交易日
- manifest：记录每数据集的 last_date + 更新时间，可追溯

用法：python3 scripts/data/update_lake.py            # 全部增量更新
      python3 scripts/data/update_lake.py --prices  # 仅价量
"""
import warnings; warnings.filterwarnings("ignore")
import os, json, argparse
from pathlib import Path
from datetime import date, datetime
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
import sys
sys.path.insert(0, str(ROOT))
import pandas as pd
import akshare as ak
from lake.sources.tencent import TencentDailyFetcher
from lake.sources.exchange import MarginFetcher, merge_margin

LAKE = Path("data_lake")
MANIFEST = LAKE / "_manifest.json"


def load_manifest():
    return json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {}

def save_manifest(m):
    m["_updated"] = datetime.now().isoformat(timespec="seconds")
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2))


# ── 价量增量 ──
def update_prices():
    daily = LAKE / "price/daily"
    today = pd.Timestamp(date.today())
    f = TencentDailyFetcher()

    # ── 发现缺失代码(退市股等)，尝试首次下载 ──
    codes_fp = LAKE / "meta/codes.parquet"
    added = 0
    if codes_fp.exists():
        all_codes = set(pd.read_parquet(codes_fp)["code"].tolist())
        existing = {fp.stem for fp in daily.glob("*.parquet")
                    if fp.stem.isdigit() and len(fp.stem) == 6}
        missing = all_codes - existing
        # 过滤北交所(920xxx, 腾讯API无数据)
        missing = {c for c in missing if not c.startswith("92")}
        if missing:
            print(f"[价量] 缺失代码 {len(missing)} 只(退市/停更)，尝试下载...", flush=True)
            f.start = "2010-01-01"
            for i, code in enumerate(sorted(missing)):
                try:
                    df = f.fetch_one(code)
                    if df is not None and len(df) > 20:
                        df.to_parquet(daily / f"{code}.parquet", index=False)
                        added += 1
                except Exception:
                    continue
                if (i + 1) % 50 == 0:
                    print(f"  缺失下载 {i+1}/{len(missing)} (新增{added})", flush=True)
            if added > 0:
                print(f"[价量] 新增退市/缺失股 {added} 只", flush=True)

    # ── 增量更新已有文件 ──
    files = sorted(daily.glob("*.parquet"))
    updated, skipped = 0, 0
    for i, fp in enumerate(files):
        df = pd.read_parquet(fp)
        last = df["date"].max()
        if last >= today - pd.Timedelta(days=1):
            skipped += 1
            continue
        f.start = (last + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        try:
            new = f.fetch_one(fp.stem)
        except Exception:
            continue
        if new is not None and len(new):
            merged = (pd.concat([df, new]).drop_duplicates("date")
                      .sort_values("date").reset_index(drop=True))
            merged.to_parquet(fp, index=False)
            updated += 1
        if (i + 1) % 500 == 0:
            print(f"  价量 {i+1}/{len(files)} (更新{updated} 跳过{skipped})", flush=True)
    print(f"[价量] 更新{updated}只, 跳过{skipped}只(已最新)", flush=True)

    # ── 增量更新后重新合并大表(含退市股) ──
    if updated > 0 or added > 0:
        print("重新合并 daily_all.parquet ...", flush=True)
        from lake.compact import compact_prices
        compact_prices(daily, LAKE / "price/daily_all.parquet")

    return {"price_daily": {"last_check": str(date.today()),
                            "updated": updated, "added_delisted": added}}


# ── 财务增量（按报告期补新季度）──
def update_fundamental():
    fp = LAKE / "fundamental_batch.parquet"
    if not fp.exists():
        return {}
    df = pd.read_parquet(fp)
    have = set(df["report_date"].dt.strftime("%Y%m%d"))
    # 生成所有应有报告期，找缺失的（新季度）
    periods = [f"{y}{md}" for y in range(2010, date.today().year + 1)
               for md in ["0331", "0630", "0930", "1231"]]
    cutoff = date.today().strftime("%Y%m%d")
    missing = [p for p in periods if p <= cutoff and p not in have]
    if not missing:
        print("[财务] 已最新，无新报告期", flush=True)
        return {"fundamental": {"last_check": str(date.today())}}

    from lake.schema import YJBB_RENAME
    RENAME = YJBB_RENAME
    KEEP = list(set(RENAME.values()) | {"report_date","avail_date"})
    new_frames = []
    for p in missing:
        try:
            d = ak.stock_yjbb_em(date=p)
            if d is None or d.empty:
                continue
            d = d.rename(columns=RENAME)
            d["report_date"] = pd.to_datetime(p)
            new_frames.append(d[[c for c in RENAME.values() if c in d.columns] + ["report_date"]])
            print(f"  财务新报告期 {p}: {len(d)}只", flush=True)
        except Exception:
            continue
    if new_frames:
        nf = pd.concat(new_frames, ignore_index=True)
        nf["code"] = nf["code"].astype(str).str.zfill(6)
        nf["ann_date"] = pd.to_datetime(nf.get("ann_date"), errors="coerce")
        nf["avail_date"] = nf["ann_date"].fillna(nf["report_date"] + pd.Timedelta(days=45))
        merged = pd.concat([df, nf], ignore_index=True).drop_duplicates(["code","report_date"], keep="last")
        merged.to_parquet(fp, index=False)
        print(f"[财务] 新增{len(missing)}个报告期", flush=True)
    return {"fundamental": {"last_check": str(date.today()), "new_periods": missing}}


def update_capital_margin():
    """补两融到最新交易日；北向依赖 eastmoney 稳定性，走 build_capital.py 单独维护。"""
    cal_fp = LAKE / "meta/trade_calendar.parquet"
    if not cal_fp.exists():
        return {}
    cal = pd.read_parquet(cal_fp)
    trade_dates = pd.to_datetime(cal["date"])
    margin_dir = LAKE / "capital/margin"
    margin_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(margin_dir.glob("*.parquet"))
    if existing:
        last = pd.to_datetime(existing[-1].stem)
        keys = trade_dates[trade_dates > last].dt.strftime("%Y%m%d").tolist()
    else:
        keys = trade_dates.dt.strftime("%Y%m%d").tolist()
    if not keys:
        print("[两融] 已最新，无新交易日", flush=True)
        return {"capital_margin": {"last_check": str(date.today()), "updated_days": 0}}
    fetcher = MarginFetcher(max_workers=3, timeout=30, retries=2)
    stats = fetcher.run(keys, skip_existing=True, progress_every=50)
    merge_margin()
    return {"capital_margin": {"last_check": str(date.today()), "updated_days": stats.get("ok", 0), "empty": stats.get("empty", 0), "error": stats.get("error", 0)}}


def update_weekly_monthly():
    """重新生成周/月线聚合。"""
    from lake.aggregate import build_periodic
    build_periodic("data_lake/price/daily")
    return {"periodic": {"last_check": str(date.today())}}


def run_validate():
    """运行数据质量校验。"""
    import subprocess
    result = subprocess.run([sys.executable, "validate_final.py"], cwd=ROOT, capture_output=True, text=True)
    ok = result.returncode == 0 and "干净" in result.stdout
    return {"validate": {"last_check": str(date.today()), "ok": ok}}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--prices", action="store_true", help="Update price data only.")
    ap.add_argument("--fundamental", action="store_true", help="Update fundamental data only.")
    ap.add_argument("--capital", action="store_true", help="Update margin financing data only.")
    ap.add_argument("--weekly-monthly", action="store_true", help="Rebuild weekly/monthly aggregates.")
    ap.add_argument("--validate", action="store_true", help="Run data quality validation.")
    ap.add_argument("--all", action="store_true", help="Run all updates.")
    args = ap.parse_args()
    do_all = args.all or not (args.prices or args.fundamental or args.capital or args.weekly_monthly or args.validate)

    m = load_manifest()
    if do_all or args.prices:
        m.update(update_prices())
    if do_all or args.fundamental:
        m.update(update_fundamental())
    if args.capital:
        m.update(update_capital_margin())
    if do_all or args.weekly_monthly:
        m.update(update_weekly_monthly())
    if do_all or args.validate:
        m.update(run_validate())
    save_manifest(m)
    print(f"\n增量更新完成，manifest: {MANIFEST}", flush=True)
