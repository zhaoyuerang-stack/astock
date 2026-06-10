"""A-H premium factor — download HK data + build premium factor.

A-H premium = (A-share price / H-share price * FX) - 1
  > 0: A-share trades at premium vs H-share → bearish for A-share
  < 0: A-share trades at discount → bullish for A-share

Natural orthogonal to v2.1 (cross-market pricing, different driver).

Key A-H pairs (A-code → H-code):
  600028 → 00386 (中石化), 601398 → 01398 (工行), 601318 → 02318 (平安)
  601288 → 01288 (农行), 601939 → 00939 (建行), 601988 → 03988 (中行)
  ... and ~140 more

Usage:
  cd /Users/kiki/astcok/factor_research && python3 scripts/research/ah_premium_factor.py
"""
import os, sys, time, json, urllib.request
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import spearmanr

ROOT = Path("/Users/kiki/astcok/factor_research").resolve()
os.chdir(ROOT); sys.path.insert(0, str(ROOT))

from strategies.small_cap import load_price_panels
from factors.small_cap import small_cap_factor

OUT = ROOT / "reports" / "research"; OUT.mkdir(parents=True, exist_ok=True)
HK_DIR = ROOT / "data_lake" / "price" / "hk_daily"
HK_DIR.mkdir(parents=True, exist_ok=True)

# ── HK data fetching ──
def fetch_hk_history(code, start="2018-01-01"):
    """Fetch full HK stock history with pagination."""
    seen, rows, end_date = set(), [], "2026-12-31"
    for _ in range(15):
        url = (f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
               f"?param=hk{code},day,2010-01-01,{end_date},640,hfq")
        try:
            resp = urllib.request.urlopen(url, timeout=15)
            data = json.loads(resp.read())
            node = data.get("data", {}).get(f"hk{code}", {})
            arr = node.get("hfqday") or node.get("day") or []
            if not arr: break
            new = [r for r in arr if r[0] not in seen]
            if not new: break
            for r in new: seen.add(r[0])
            rows = new + rows
            earliest = arr[0][0]
            if earliest <= "2017-01-01": break
            end_date = earliest
        except Exception: break
        time.sleep(0.2)
    if not rows: return None
    df = pd.DataFrame([r[:6] for r in rows],
                      columns=["date","open","close","high","low","volume"])
    df["date"] = pd.to_datetime(df["date"])
    for c in ["open","close","high","low","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    df = df[df["date"] >= pd.Timestamp(start)]
    return df.set_index("date")[["close"]].rename(columns={"close": f"hk_{code}"})


# ── A-H pair mapping (verified pairs with active trading) ──
AH_PAIRS = {
    "600028": "00386", "601398": "01398", "601318": "02318",
    "601288": "01288", "601939": "00939", "601988": "03988",
    "601328": "03328", "601628": "02628", "600036": "03968",
    "600585": "00914", "600011": "00902", "600027": "01071",
    "601111": "00753", "600029": "01055", "600016": "01988",
    "601390": "00390", "601857": "00857", "601088": "01088",
    "601998": "00998", "600050": "00762",
}

print(f"Downloading {len(AH_PAIRS)} HK stocks...", flush=True)
hk_data = {}
for i, (a_code, h_code) in enumerate(AH_PAIRS.items()):
    cache_file = HK_DIR / f"{h_code}.parquet"
    if cache_file.exists():
        hk_data[h_code] = pd.read_parquet(cache_file)["close"]
    else:
        df = fetch_hk_history(h_code)
        if df is not None and len(df) > 100:
            df.to_parquet(cache_file)
            hk_data[h_code] = df.iloc[:, 0]  # close column
    if (i+1) % 5 == 0:
        print(f"  {i+1}/{len(AH_PAIRS)} done ({len(hk_data)} found)", flush=True)
print(f"  Downloaded {len(hk_data)} HK stocks", flush=True)

# ── Load A-share data ──
print("Loading A-share prices...", flush=True)
close, vol, amount = load_price_panels("2018-01-01")

# ── Build A-H premium panel ──
print("Building A-H premium panel...", flush=True)
premiums = {}
for a_code, h_code in AH_PAIRS.items():
    if h_code not in hk_data: continue
    if a_code not in close.columns: continue

    a_px = close[a_code].dropna()
    h_series = hk_data[h_code].dropna()

    common = a_px.index.intersection(h_series.index)
    if len(common) < 500: continue

    h_aligned = h_series.reindex(common).ffill()
    a_aligned = a_px.reindex(common)

    # CNY/HKD ≈ 0.91 (fluctuates between 0.85-0.93)
    # A-share in CNY, H-share in HKD → convert H-share to CNY-equivalent
    fx_rate = 0.91
    premium = a_aligned / (h_aligned * fx_rate) - 1
    premiums[a_code] = premium

print(f"  {len(premiums)} A-H pairs with sufficient data", flush=True)

if not premiums:
    print("  No A-H pairs found. Aborting."); sys.exit(0)

# Build panel
premium_panel = pd.DataFrame(premiums)

# ── Factor construction ──
# Cross-sectional: rank(negative premium) → higher = A-share cheaper vs H-share
factor = -premium_panel.rank(axis=1, pct=True)  # cross-sectional rank

# ── IC analysis ──
fwd20 = close.pct_change(20).shift(-20)
ics = []
for dt in factor.index[::30]:
    if dt not in fwd20.index: continue
    f = factor.loc[dt].dropna()
    r = fwd20.loc[dt].reindex(f.index).dropna()
    common = f.index.intersection(r.index)
    if len(common) < 10: continue
    ic, _ = spearmanr(f[common], r[common])
    if not np.isnan(ic): ics.append(ic)

print(f"\n{'='*50}")
print(f"  A-H Premium Factor IC")
print(f"{'='*50}")
print(f"  Pairs: {len(premiums)}")
print(f"  IC20d mean: {np.mean(ics):+.4f}  ICIR: {np.mean(ics)/np.std(ics):.2f}  pos: {(np.array(ics)>0).mean():.0%}")

# Correlation with v2.1
v21 = small_cap_factor(amount, 30)
corrs = []
for dt in factor.index[::60]:
    if dt not in v21.index: continue
    f = factor.loc[dt].dropna()
    v = v21.loc[dt].dropna()
    common = f.index.intersection(v.index)
    if len(common) < 10: continue
    c, _ = spearmanr(f[common], v[common])
    if not np.isnan(c): corrs.append(c)
print(f"  Corr with v2.1: {np.mean(corrs):+.3f}  ({'✅ ORTHOGONAL' if abs(np.mean(corrs))<0.3 else '⚠️ correlated'})")

# Daily mean premium for reference
mean_premium = premium_panel.mean(axis=1)
print(f"\n  Mean A-H premium: {mean_premium.mean():+.1%}")
print(f"  Range: {mean_premium.min():+.1%} ~ {mean_premium.max():+.1%}")
print(f"  Current: {mean_premium.iloc[-1]:+.1%}")
print(f"\n  Wrote HK data to: {HK_DIR}")
print(f"  Total pairs: {len(premiums)}")
