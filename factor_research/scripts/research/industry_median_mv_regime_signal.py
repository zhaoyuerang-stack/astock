"""
探索性研究：分行业中位数市值 -> 归一化(时间序列 rolling z-score) -> 偏离值 -> 是否能反映牛熊转换

结论必须由本脚本机械产出，不接受"看起来有效"。本脚本只做探索性诊断，不进入策略/入册流程，
不受 9-Gate 约束，但仍遵守数据纪律 (R-DATA-002 全市场、R-DATA-004 估值用不复权价口径—
此处市值本身就该用真实股本×真实价格，非复权价，daily_basic 的 total_mv 口径本就正确)。

方法（第一性原理拆解后确定）：
1. 市值中位数按月频、按申万一级行业分组计算，只用季后满 1 年的"老股"，剔除新股上市对
   中位数的结构性污染（这是最容易翻车的点之一）。
2. 每个行业的中位数市值序列，做"环比对数增速"，再对该行业自身历史做 rolling z-score
   （不做跨行业归一化，因为跨行业和跨时间是两种不同含义的指标，混着做会失去可解释性）。
3. 把各行业的 z-score 做等权平均，得到一个市场级"偏离度"月度序列。
4. 用 20% 顶底算法在上证指数上机械划出牛熊区间（不是人工挑选转折点，避免"挑日子讲故事"）。
5. 做三类可验证的检验：同期相关性、领先滞后相关性（偏离度 vs 未来 1/3/6 个月收益）、
   事件研究（牛熊转折前 6 个月 vs 其他时间的偏离度分布差异），并给出 Newey-West 调整后的
   t 统计量（月度序列有自相关，普通 t 检验会虚高显著性）。
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path

DATA_LAKE = Path("/sessions/inspiring-gifted-ramanujan/mnt/astcok/factor_research/data_lake")
OUT_DIR = Path("/sessions/inspiring-gifted-ramanujan/mnt/outputs")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SEASONING_DAYS = 365          # 剔除上市不满 1 年的新股
MIN_STOCKS_PER_INDUSTRY = 5   # 行业内股票数过少的月份丢弃，避免中位数噪音
ROLLING_WINDOW = 36           # 时间序列 rolling z-score 窗口（月）
ROLLING_MIN_PERIODS = 24
BULL_BEAR_THRESHOLD = 0.20    # 20% 顶底算法阈值（经典牛熊市定义）


def log(msg):
    print(f"[signal] {msg}", flush=True)


# ---------- 1. 加载数据 ----------

def load_daily_basic_month_end():
    """14M 行全量逐日 daily_basic 直接做 to_datetime/str.split 在本沙箱内存下会被 OOM kill。
    先在字符串层面(YYYYMMDD 文本)按年月取月末交易日、过滤到月末子集(约 70 万行)，
    再对这个小很多的子集做 datetime 转换和 code 提取，数量级从 1400 万行降到 70 万行。"""
    df = pd.read_parquet(DATA_LAKE / "daily_basic" / "daily_basic_all.parquet",
                          engine="fastparquet", columns=["ts_code", "trade_date", "total_mv"])
    year_month = df["trade_date"].str[:6]
    month_end_dates = set(df.groupby(year_month)["trade_date"].max().values)
    df = df[df["trade_date"].isin(month_end_dates)].copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df["code"] = df["ts_code"].str[:6]
    return df


def load_industry_map():
    df = pd.read_parquet(DATA_LAKE / "meta" / "industry.parquet", engine="fastparquet")
    m = df[["code", "industry_l1_name"]].dropna().drop_duplicates(subset="code")
    m["industry_l1_name"] = m["industry_l1_name"].str.replace("(申万)", "", regex=False)
    return m


def load_list_date():
    df = pd.read_parquet(DATA_LAKE / "meta" / "list_date.parquet", engine="fastparquet")
    return df[["code", "first_date", "truncated"]]


def load_index(ts_code="000001.SH"):
    df = pd.read_parquet(DATA_LAKE / "index" / "index_daily_all.parquet", engine="fastparquet")
    df = df[df["ts_code"] == ts_code].copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")
    df = df.sort_values("trade_date")
    return df[["trade_date", "close"]]


# ---------- 2. 构建月度分行业中位数市值面板（剔除新股）----------

def build_monthly_industry_median_mv():
    db_month_end = load_daily_basic_month_end()
    ind = load_industry_map()
    ld = load_list_date()

    db_month_end["month"] = db_month_end["trade_date"].dt.to_period("M")
    panel = db_month_end.merge(ind, on="code", how="left")
    panel = panel.merge(ld, on="code", how="left")

    coverage_before = panel["code"].nunique()
    panel = panel.dropna(subset=["industry_l1_name"])
    coverage_after_industry = panel["code"].nunique()

    # 新股剔除：满 1 年老股才计入
    panel["seasoning_days"] = (panel["trade_date"] - panel["first_date"]).dt.days
    panel_seasoned = panel[(panel["truncated"] == True) | (panel["seasoning_days"] >= SEASONING_DAYS)].copy()

    log(f"universe coverage: total_mv非空个股 {coverage_before} -> 有行业标签 {coverage_after_industry} "
        f"-> 剔除新股后用于计算 {panel_seasoned['code'].nunique()}")

    grp = (panel_seasoned.groupby(["month", "industry_l1_name"])
           .agg(median_mv=("total_mv", "median"), n_stocks=("code", "nunique"))
           .reset_index())
    grp = grp[grp["n_stocks"] >= MIN_STOCKS_PER_INDUSTRY]

    return grp, panel, panel_seasoned


# ---------- 3. 环比对数增速 + 时间序列 rolling z-score ----------

def build_deviation_index(grp):
    grp = grp.sort_values(["industry_l1_name", "month"]).copy()
    grp["month_ts"] = grp["month"].dt.to_timestamp("M")

    out = []
    for name, g in grp.groupby("industry_l1_name"):
        g = g.sort_values("month_ts").reset_index(drop=True)
        g["log_mv"] = np.log(g["median_mv"])
        g["g"] = g["log_mv"].diff()  # 环比对数增速
        roll_mean = g["g"].rolling(ROLLING_WINDOW, min_periods=ROLLING_MIN_PERIODS).mean()
        roll_std = g["g"].rolling(ROLLING_WINDOW, min_periods=ROLLING_MIN_PERIODS).std()
        g["z"] = (g["g"] - roll_mean) / roll_std
        out.append(g[["industry_l1_name", "month_ts", "median_mv", "g", "z", "n_stocks"]])

    panel_z = pd.concat(out, ignore_index=True)

    market = (panel_z.dropna(subset=["z"])
              .groupby("month_ts")
              .agg(deviation_index=("z", "mean"),
                   deviation_dispersion=("z", "std"),
                   n_industries=("z", "count"))
              .reset_index())
    return panel_z, market


# ---------- 4. 20% 顶底算法机械划牛熊区间（不是人工挑日子）----------

def label_bull_bear(index_df):
    """经典 Bry-Boschan / Pagan-Sossounov 简化版：从最近确认的峰/谷起算，
    价格偏离 >=20% 才确认新的峰或谷，避免用日内噪音制造伪转折点。"""
    px = index_df.set_index("trade_date")["close"]
    dates = px.index
    vals = px.values

    # 单分支实现：同一时刻只跟踪"候选峰"或"候选谷"之一，避免共享变量被两个分支
    # 同时改写导致的错误（第一版这里有 bug：state=None 时两个 if 都会进，
    # 候选峰/候选谷用同一个变量互相污染，结果一个转折点都测不出来，已用真实数据跑出
    # n_turning_points=0 复现确认，不是"看起来能跑就行"）。
    direction = "up"  # 初始假设先找候选峰；如果一开始就跌 20%，会在起点直接确认一个 peak
    extreme_val = vals[0]
    extreme_idx = 0
    turning_points = []

    for i in range(1, len(vals)):
        if direction == "up":
            if vals[i] >= extreme_val:
                extreme_val = vals[i]
                extreme_idx = i
            elif vals[i] <= extreme_val * (1 - BULL_BEAR_THRESHOLD):
                turning_points.append((dates[extreme_idx], "peak"))
                direction = "down"
                extreme_val = vals[i]
                extreme_idx = i
        else:  # direction == "down"
            if vals[i] <= extreme_val:
                extreme_val = vals[i]
                extreme_idx = i
            elif vals[i] >= extreme_val * (1 + BULL_BEAR_THRESHOLD):
                turning_points.append((dates[extreme_idx], "trough"))
                direction = "up"
                extreme_val = vals[i]
                extreme_idx = i

    # 用 turning_points 重建逐日 regime：trough 后到下一个 peak 之间是 bull，peak 后到下一个 trough 是 bear
    regime_series = pd.Series("unknown", index=dates)
    if turning_points:
        first_kind = turning_points[0][1]
        cur_state = "bear" if first_kind == "peak" else "bull"
        regime_series.loc[:turning_points[0][0]] = "bull" if cur_state == "bear" else "bear"
        for k in range(len(turning_points)):
            start = turning_points[k][0]
            end = turning_points[k + 1][0] if k + 1 < len(turning_points) else dates[-1]
            kind = turning_points[k][1]
            regime_series.loc[start:end] = "bear" if kind == "peak" else "bull"

    return regime_series, turning_points


# ---------- 5. Newey-West t 统计量（月度自相关调整，手写不依赖 statsmodels）----------

def newey_west_tstat(x, y, lags=6):
    """对 corr(x,y) 的显著性做 HAC 调整。用简单方法：对 y = a + b*x 做 OLS，
    再用 Newey-West 修正 b 的标准误，返回 (b, t_stat, n)。"""
    df = pd.DataFrame({"x": x, "y": y}).dropna()
    n = len(df)
    if n < 10 or df["x"].std() == 0:
        # x 在有效样本内没有变化（比如 pre_turn 窗口全部落在 rolling z 还没热身完的
        # 早期样本里，导致这个 dummy 恒为 0），回归会奇异，如实报告缺失而不是硬凑一个数字
        return np.nan, np.nan, n
    X = np.column_stack([np.ones(n), df["x"].values])
    Y = df["y"].values
    beta = np.linalg.lstsq(X, Y, rcond=None)[0]
    resid = Y - X @ beta
    XtX_inv = np.linalg.inv(X.T @ X)

    # HAC (Newey-West) 协方差
    S = np.zeros((2, 2))
    for t in range(n):
        S += resid[t] ** 2 * np.outer(X[t], X[t])
    for lag in range(1, lags + 1):
        w = 1 - lag / (lags + 1)
        for t in range(lag, n):
            term = resid[t] * resid[t - lag] * np.outer(X[t], X[t - lag])
            S += w * (term + term.T)
    cov = XtX_inv @ S @ XtX_inv
    se_b = np.sqrt(cov[1, 1])
    b = beta[1]
    t_stat = b / se_b if se_b > 0 else np.nan
    return b, t_stat, n


# ---------- 6. 主流程 ----------

def main():
    log("Step 1: 构建月度分行业中位数市值面板（剔除新股、剔除样本过少行业）")
    grp, panel_raw, panel_seasoned = build_monthly_industry_median_mv()

    log("Step 2: 计算环比对数增速 + rolling z-score，聚合为市场级偏离度指数")
    panel_z, market = build_deviation_index(grp)

    log("Step 3: 加载上证指数，用 20% 顶底算法机械划牛熊区间")
    idx = load_index("000001.SH")
    regime_daily, turning_points = label_bull_bear(idx)

    idx_m = idx.set_index("trade_date")["close"].resample("ME").last()
    idx_ret_fwd = pd.DataFrame({"close": idx_m})
    idx_ret_fwd["ret_fwd_1m"] = idx_ret_fwd["close"].shift(-1) / idx_ret_fwd["close"] - 1
    idx_ret_fwd["ret_fwd_3m"] = idx_ret_fwd["close"].shift(-3) / idx_ret_fwd["close"] - 1
    idx_ret_fwd["ret_fwd_6m"] = idx_ret_fwd["close"].shift(-6) / idx_ret_fwd["close"] - 1
    idx_ret_fwd["ret_contemp_1m"] = idx_ret_fwd["close"] / idx_ret_fwd["close"].shift(1) - 1
    idx_ret_fwd.index.name = "month_ts"

    merged = market.set_index("month_ts").join(idx_ret_fwd, how="inner").reset_index()

    # regime 按月末对齐
    regime_month = regime_daily.resample("ME").last()
    regime_month.index.name = "month_ts"
    merged = merged.merge(regime_month.rename("regime").reset_index(), on="month_ts", how="left")

    log("Step 4: 相关性检验（同期 + 领先滞后），Newey-West 调整")
    results = {}
    for label, col in [("同期(本月收益)", "ret_contemp_1m"),
                        ("领先1个月", "ret_fwd_1m"),
                        ("领先3个月", "ret_fwd_3m"),
                        ("领先6个月", "ret_fwd_6m")]:
        b, t, n = newey_west_tstat(merged["deviation_index"], merged[col], lags=6)
        raw_corr = merged[["deviation_index", col]].dropna().corr().iloc[0, 1]
        results[label] = {"beta": b, "nw_tstat": t, "n_obs": n, "raw_corr": raw_corr}
        log(f"  {label}: beta={b:.4f} NW-t={t:.2f} raw_corr={raw_corr:.3f} n={n}")

    log("Step 5: 事件研究——牛熊转折前 6 个月 vs 其他时间的偏离度分布")
    pre_turn_months = set()
    for (dt, kind) in turning_points:
        window = pd.date_range(end=dt, periods=6, freq="ME")
        pre_turn_months.update(window)
    merged["pre_turn"] = merged["month_ts"].isin(pre_turn_months)

    event_stats = {
        "pre_turn_mean": float(merged.loc[merged["pre_turn"], "deviation_index"].mean()),
        "pre_turn_std": float(merged.loc[merged["pre_turn"], "deviation_index"].std()),
        "pre_turn_n": int(merged["pre_turn"].sum()),
        "other_mean": float(merged.loc[~merged["pre_turn"], "deviation_index"].mean()),
        "other_std": float(merged.loc[~merged["pre_turn"], "deviation_index"].std()),
        "other_n": int((~merged["pre_turn"]).sum()),
    }
    b_evt, t_evt, n_evt = newey_west_tstat(merged["pre_turn"].astype(float), merged["deviation_index"], lags=6)
    event_stats["nw_tstat_pre_turn_dummy"] = t_evt
    log(f"  转折前6个月 mean(z)={event_stats['pre_turn_mean']:.3f} (n={event_stats['pre_turn_n']}) "
        f"vs 其他 mean(z)={event_stats['other_mean']:.3f} (n={event_stats['other_n']}) NW-t={t_evt:.2f}")

    # ---------- 输出 ----------
    market_out = merged[["month_ts", "deviation_index", "deviation_dispersion", "n_industries",
                          "ret_contemp_1m", "ret_fwd_1m", "ret_fwd_3m", "ret_fwd_6m", "regime", "pre_turn"]]
    market_out.to_csv(OUT_DIR / "industry_median_mv_deviation_monthly.csv", index=False)
    panel_z.to_csv(OUT_DIR / "industry_median_mv_by_industry_monthly.csv", index=False)

    turning_points_out = [{"date": str(d.date()), "kind": k} for d, k in turning_points]
    summary = {
        "universe": {
            "total_mv非空个股数": int(coverage := panel_raw["code"].nunique()),
            "剔除新股后个股数": int(panel_seasoned["code"].nunique()),
            "行业数(月均)": float(grp.groupby("month")["industry_l1_name"].nunique().mean()),
        },
        "params": {
            "SEASONING_DAYS": SEASONING_DAYS,
            "MIN_STOCKS_PER_INDUSTRY": MIN_STOCKS_PER_INDUSTRY,
            "ROLLING_WINDOW": ROLLING_WINDOW,
            "BULL_BEAR_THRESHOLD": BULL_BEAR_THRESHOLD,
            "benchmark": "000001.SH 上证指数",
        },
        "turning_points": turning_points_out,
        "correlation_tests": results,
        "event_study_pre_turn_6m": event_stats,
        "sample_period": {
            "start": str(merged["month_ts"].min().date()),
            "end": str(merged["month_ts"].max().date()),
            "n_months": int(len(merged)),
        },
    }
    with open(OUT_DIR / "industry_median_mv_regime_signal_summary.json", "w") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

    # ---------- 图 ----------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.font_manager as fm
    import matplotlib.pyplot as plt
    cjk_path = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    fm.fontManager.addfont(cjk_path)
    cjk_name = fm.FontProperties(fname=cjk_path).get_name()
    plt.rcParams["font.sans-serif"] = [cjk_name, "DejaVu Sans"]
    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["axes.unicode_minus"] = False

    fig, axes = plt.subplots(2, 1, figsize=(13, 8), sharex=True)
    ax0, ax1 = axes

    sample_start = merged["month_ts"].min()
    idx_plot = idx.set_index("trade_date")["close"]
    idx_plot = idx_plot[idx_plot.index >= sample_start]
    ax0.plot(idx_plot.index, idx_plot.values, color="black", lw=1)
    ax0.set_ylabel("上证指数")
    plotted_turns = [(dt, k) for dt, k in turning_points if dt >= sample_start]
    for dt, kind in plotted_turns:
        ax0.axvline(dt, color="red" if kind == "peak" else "green", ls="--", alpha=0.6, lw=1)
    ax0.set_title(f"上证指数（{sample_start.date()}起，与偏离度指数样本区间对齐）"
                  "与 20%顶底算法机械划出的牛熊转折点（红=顶部, 绿=底部）")

    ax1.plot(merged["month_ts"], merged["deviation_index"], color="steelblue", lw=1.3,
              label="分行业中位数市值 环比增速 rolling z-score 等权平均")
    ax1.axhline(0, color="gray", lw=0.8)
    for dt, kind in plotted_turns:
        ax1.axvline(dt, color="red" if kind == "peak" else "green", ls="--", alpha=0.6, lw=1)
    ax1.set_ylabel("偏离度指数 (z-score)")
    ax1.legend(loc="upper left", fontsize=9)

    plt.tight_layout()
    fig.savefig(OUT_DIR / "industry_median_mv_regime_signal.png", dpi=130)

    log("完成。输出文件：")
    log(f"  {OUT_DIR / 'industry_median_mv_deviation_monthly.csv'}")
    log(f"  {OUT_DIR / 'industry_median_mv_by_industry_monthly.csv'}")
    log(f"  {OUT_DIR / 'industry_median_mv_regime_signal_summary.json'}")
    log(f"  {OUT_DIR / 'industry_median_mv_regime_signal.png'}")


if __name__ == "__main__":
    main()
