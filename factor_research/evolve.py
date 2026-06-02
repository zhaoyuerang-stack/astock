"""
自进化策略优化系统 v2

目标：最大回撤 < 15%，年化收益 > 35%

三层架构：
  选股层  多因子IC加权合成 → 截面打分排序
  择时层  全市场均线择时，熊市空仓（斩断系统性回撤）
  进化层  遗传算法搜索 (因子子集, 持股数, 调仓频率, 择时窗口)
"""
import warnings
warnings.filterwarnings("ignore")

import os, json, random
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.stats import spearmanr

DATA   = Path(os.environ.get("FACTOR_DATA", "data"))
RESULT = Path("results")
RESULT.mkdir(exist_ok=True)

TARGET_ANNUAL = 0.35
TARGET_MAXDD  = 0.15
FORWARD_DAYS  = 20
random.seed(42)
np.random.seed(42)


# ══════════════════════════════════════════════════════════════════
# 数据
# ══════════════════════════════════════════════════════════════════

def load_panels():
    files = sorted(DATA.glob("kline_*.parquet"))
    print(f"加载 {len(files)} 只股票缓存...")
    frames = []
    for f in files:
        df = pd.read_parquet(f)
        df["code"] = f.stem.replace("kline_", "")
        frames.append(df[["date", "code", "close", "volume", "amount"]])
    long = pd.concat(frames, ignore_index=True)
    close  = long.pivot(index="date", columns="code", values="close").sort_index()
    volume = long.pivot(index="date", columns="code", values="volume").sort_index()
    amount = long.pivot(index="date", columns="code", values="amount").sort_index()
    active = (volume > 0).rolling(5).sum().iloc[-1] >= 3
    codes = active[active].index
    print(f"有效股票: {len(codes)} 只 | {close.index[0].date()} ~ {close.index[-1].date()}")
    return close[codes], volume[codes], amount[codes]


# ══════════════════════════════════════════════════════════════════
# 因子
# ══════════════════════════════════════════════════════════════════

def safe_zscore(df):
    return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1) + 1e-8, axis=0)

def mad_clip(df, n=5):
    med = df.median(axis=1)
    mad = df.sub(med, axis=0).abs().median(axis=1)
    return df.clip(lower=med - n*mad, upper=med + n*mad, axis=0)

def compute_factor(name, params, close, volume, amount):
    c, v, a = close, volume, amount
    ret = c.pct_change()
    if name == "mom":
        n, skip = params["n"], params.get("skip", 0)
        f = c.shift(skip) / c.shift(n + skip) - 1
    elif name == "reversal":
        f = -(c / c.shift(params["n"]) - 1)
    elif name == "vol_ratio":
        f = v.rolling(params["short"]).mean() / (v.rolling(params["long"]).mean() + 1e-6)
    elif name == "low_vol":
        f = -ret.rolling(params["n"]).std()
    elif name == "illiq":
        f = -(ret.abs() / (v + 1)).rolling(params["n"]).mean()
    elif name == "turnover":
        turn = a / (a.rolling(60).mean() + 1e-6)
        f = -turn.rolling(params["n"]).mean()
    elif name == "price_ma":
        f = -(c / c.rolling(params["n"]).mean() - 1)
    elif name == "momentum_quality":
        f = (ret > 0).rolling(params["n"]).mean()
    elif name == "drawdown_recover":
        f = -(c.rolling(params["n"]).max() / c - 1)
    elif name == "size":
        # 小盘因子：成交额越小越偏小盘（A股最强alpha之一）
        f = -np.log(a.rolling(params["n"]).mean() + 1)
    else:
        return None
    return safe_zscore(mad_clip(f))


# 因子搜索空间（精简到已验证有效的）
SEARCH_SPACE = {
    "size":             [{"n": n} for n in [20, 40, 60]],
    "reversal":         [{"n": n} for n in [3, 5, 10, 20]],
    "turnover":         [{"n": n} for n in [5, 10, 20]],
    "price_ma":         [{"n": n} for n in [20, 60, 120]],
    "low_vol":          [{"n": n} for n in [10, 20, 40]],
    "illiq":            [{"n": n} for n in [10, 20, 40]],
    "vol_ratio":        [{"short": s, "long": l} for s, l in [(5, 20), (5, 60)]],
    "momentum_quality": [{"n": n} for n in [10, 20, 40]],
    "drawdown_recover": [{"n": n} for n in [20, 60]],
}


# ══════════════════════════════════════════════════════════════════
# IC评估
# ══════════════════════════════════════════════════════════════════

def calc_ic_series(factor, fwd_ret):
    dates = factor.dropna(how="all").index.intersection(fwd_ret.dropna(how="all").index)
    ics = {}
    for dt in dates[::3]:   # 每3天采样，加速
        f = factor.loc[dt].dropna()
        r = fwd_ret.loc[dt].dropna()
        common = f.index.intersection(r.index)
        if len(common) < 50:
            continue
        ic, _ = spearmanr(f[common], r[common])
        if not np.isnan(ic):
            ics[dt] = ic
    return pd.Series(ics)


# ══════════════════════════════════════════════════════════════════
# 回测（含市场择时）
# ══════════════════════════════════════════════════════════════════

def market_timing(close, ma_window):
    """全市场等权指数均线择时，返回 date→bool（是否持仓），已shift防前视"""
    mkt = close.mean(axis=1)
    signal = (mkt > mkt.rolling(ma_window).mean()).shift(1).fillna(False)
    return signal

def backtest(composite, close, top_n, rebal_gap, timing_signal=None, cost=0.0015,
             vol_target=None, lev_max=2.5):
    """
    composite: date×code 因子分数（越大越好）
    timing_signal: date→bool，空仓日收益为0
    cost: 单边交易成本（含印花税+佣金+冲击），调仓日扣除
    vol_target: 年化波动率目标，启用则动态调杠杆（低波加仓/高波减仓）
    lev_max: 杠杆上限
    """
    daily_ret = close.pct_change()
    fdates = composite.dropna(how="all").index.intersection(close.index)
    if len(fdates) < 100:
        return pd.Series(dtype=float)

    # 调仓日选股权重（每gap个交易日，等权top_n）
    rebal_dates = list(fdates[::rebal_gap])
    weight_panel = {}
    for rd in rebal_dates:
        f = composite.loc[rd].dropna()
        active = close.loc[rd].dropna().index
        f = f.reindex(active).dropna()
        if len(f) < top_n:
            continue
        weight_panel[rd] = pd.Series(1.0 / top_n, index=f.nlargest(top_n).index)
    if not weight_panel:
        return pd.Series(dtype=float)

    # 向量化：按持仓区间批量矩阵运算（T日组合收益 = 区间收益矩阵 @ 权重）
    dr_np   = np.nan_to_num(daily_ret.values)            # T×N
    col_idx = {c: i for i, c in enumerate(daily_ret.columns)}
    index_list = list(close.index)
    pos_of  = {dt: i for i, dt in enumerate(index_list)}
    T = len(index_list)
    port = np.full(T, np.nan)

    sorted_rebal = sorted(weight_panel.keys())
    for k, rd in enumerate(sorted_rebal):
        pos_k = pos_of[rd]
        start = pos_k + 1                               # 防前视：选股次日起持有
        end = pos_of[sorted_rebal[k+1]] if k+1 < len(sorted_rebal) else T-1
        if start > end:
            continue
        w = weight_panel[rd]
        pairs = [(col_idx[c], w[c]) for c in w.index if c in col_idx]
        if not pairs:
            continue
        cols = [p[0] for p in pairs]
        vals = np.array([p[1] for p in pairs])
        port[start:end+1] = dr_np[start:end+1, cols] @ vals
        port[start] -= cost                            # 换仓成本

    ret_series = pd.Series(port, index=index_list).dropna()

    # 择时空仓（空仓日收益置0）
    if timing_signal is not None:
        mask = timing_signal.reindex(ret_series.index).fillna(False).astype(bool)
        ret_series = ret_series.where(mask, 0.0)

    # 波动率目标动态杠杆
    if vol_target and len(ret_series) > 30:
        realized = ret_series.rolling(20).std() * np.sqrt(252)
        lev = (vol_target / (realized + 1e-8)).clip(0, lev_max).shift(1).fillna(1.0)
        ret_series = ret_series * lev
    return ret_series


def metrics(ret):
    if len(ret) < 100:
        return {"annual": -1, "vol": 0, "sharpe": -1, "maxdd": -1, "calmar": 0,
                "score": -999, "hit": False, "n": len(ret)}
    annual = ret.mean() * 252
    vol    = ret.std() * np.sqrt(252)
    sharpe = annual / vol if vol > 0 else 0
    cum    = (1 + ret).cumprod()
    maxdd  = (cum / cum.cummax() - 1).min()
    calmar = annual / abs(maxdd) if maxdd < 0 else 0
    hit    = (annual >= TARGET_ANNUAL) and (abs(maxdd) <= TARGET_MAXDD)
    # 评分：达标得高分；否则引导降回撤+提收益
    dd_pen = max(0, abs(maxdd) - TARGET_MAXDD) * 3.0
    ret_pen = max(0, TARGET_ANNUAL - annual) * 1.0
    score = annual - dd_pen - ret_pen + sharpe * 0.05 + (10 if hit else 0)
    return {"annual": annual, "vol": vol, "sharpe": sharpe, "maxdd": maxdd,
            "calmar": calmar, "score": score, "hit": hit, "n": len(ret)}


# ══════════════════════════════════════════════════════════════════
# 进化引擎（遗传算法）
# ══════════════════════════════════════════════════════════════════

def build_gene_pool(close, volume, amount, fwd_ret, top_k=12):
    print("\n[Gen 0] 扫描因子库...")
    pool = []
    for fname, plist in SEARCH_SPACE.items():
        for params in plist:
            f = compute_factor(fname, params, close, volume, amount)
            if f is None:
                continue
            ic = calc_ic_series(f, fwd_ret)
            if len(ic) < 20:
                continue
            icir = ic.mean() / (ic.std() + 1e-8)
            pool.append({"name": fname, "params": params, "factor": f,
                         "ic": ic.mean(), "icir": icir})
    pool.sort(key=lambda g: abs(g["icir"]), reverse=True)
    pool = pool[:top_k]
    print(f"  保留 {len(pool)} 个强因子:")
    for g in pool:
        print(f"    {g['name']:18s}{str(g['params']):18s} IC={g['ic']:+.4f} ICIR={g['icir']:+.3f}")
    return pool


def make_composite(genes, mask):
    """按mask选择因子，IC加权合成"""
    chosen = [g for g, m in zip(genes, mask) if m]
    if not chosen:
        return None
    total = sum(abs(g["icir"]) for g in chosen) + 1e-8
    comp = sum(g["factor"] * (g["icir"] / total) for g in chosen)
    return safe_zscore(comp)


# 执行参数候选
TOP_N_OPTS   = [15, 20, 30, 50]
GAP_OPTS     = [5, 10, 20]
TIMING_OPTS  = [None, 20, 30, 40]
VOLTGT_OPTS  = [None, 0.15, 0.20, 0.25]   # 波动率目标
LEVMAX_OPTS  = [2.0, 3.0]                  # 杠杆上限

def random_individual(n_genes):
    mask = [random.random() < 0.4 for _ in range(n_genes)]
    if not any(mask):
        mask[random.randrange(n_genes)] = True
    return {
        "mask": mask,
        "top_n": random.choice(TOP_N_OPTS),
        "gap": random.choice(GAP_OPTS),
        "timing": random.choice(TIMING_OPTS),
        "vol_target": random.choice(VOLTGT_OPTS),
        "lev_max": random.choice(LEVMAX_OPTS),
    }

def mutate(ind, n_genes):
    child = {k: (v.copy() if isinstance(v, list) else v) for k, v in ind.items()}
    r = random.random()
    if r < 0.34:   # 翻转一个因子
        i = random.randrange(n_genes)
        child["mask"][i] = not child["mask"][i]
        if not any(child["mask"]):
            child["mask"][i] = True
    elif r < 0.5:
        child["top_n"] = random.choice(TOP_N_OPTS)
    elif r < 0.62:
        child["gap"] = random.choice(GAP_OPTS)
    elif r < 0.76:
        child["timing"] = random.choice(TIMING_OPTS)
    elif r < 0.9:
        child["vol_target"] = random.choice(VOLTGT_OPTS)
    else:
        child["lev_max"] = random.choice(LEVMAX_OPTS)
    return child

def crossover(a, b, n_genes):
    mask = [a["mask"][i] if random.random() < 0.5 else b["mask"][i] for i in range(n_genes)]
    if not any(mask):
        mask[random.randrange(n_genes)] = True
    return {
        "mask": mask,
        "top_n": random.choice([a["top_n"], b["top_n"]]),
        "gap": random.choice([a["gap"], b["gap"]]),
        "timing": random.choice([a["timing"], b["timing"]]),
        "vol_target": random.choice([a["vol_target"], b["vol_target"]]),
        "lev_max": random.choice([a["lev_max"], b["lev_max"]]),
    }


def evaluate(ind, genes, close, timing_cache):
    comp = make_composite(genes, ind["mask"])
    if comp is None:
        return {"score": -999, "hit": False}
    ts = timing_cache.get(ind["timing"]) if ind["timing"] else None
    ret = backtest(comp, close, ind["top_n"], ind["gap"], ts,
                   vol_target=ind["vol_target"], lev_max=ind["lev_max"])
    m = metrics(ret)
    m["ret"] = ret
    m["ind"] = ind
    return m


def evolve(close, volume, amount, generations=25, pop_size=30):
    fwd_ret = close.shift(-FORWARD_DAYS) / close - 1
    print("="*64)
    print(f"自进化策略系统 v2 | 目标：年化≥{TARGET_ANNUAL:.0%} 回撤≤{TARGET_MAXDD:.0%}")
    print("="*64)

    genes = build_gene_pool(close, volume, amount, fwd_ret)
    n_genes = len(genes)

    # 预计算择时信号
    timing_cache = {w: market_timing(close, w) for w in TIMING_OPTS if w}

    # 初始化种群
    pop = [random_individual(n_genes) for _ in range(pop_size)]
    best = {"score": -999, "hit": False}
    history = []

    for gen in range(generations):
        scored = [evaluate(ind, genes, close, timing_cache) for ind in pop]
        scored.sort(key=lambda m: m["score"], reverse=True)
        gen_best = scored[0]

        if gen_best["score"] > best["score"]:
            best = gen_best

        chosen = [g for g, m in zip(genes, gen_best["ind"]["mask"]) if m]
        fnames = "+".join(g["name"] for g in chosen)
        ind = gen_best["ind"]
        print(f"\n[Gen {gen+1}] 年化={gen_best['annual']:+.2%} 回撤={gen_best['maxdd']:.2%} "
              f"夏普={gen_best['sharpe']:.2f} 卡玛={gen_best.get('calmar',0):.2f} | "
              f"持股={ind['top_n']} 调仓={ind['gap']}d 择时={ind['timing']} "
              f"波动目标={ind['vol_target']} 杠杆={ind['lev_max']}")
        print(f"        因子=[{fnames}]")
        print(f"        全局最优: 年化={best['annual']:+.2%} 回撤={best['maxdd']:.2%} "
              f"达标={'✅' if best['hit'] else '❌'}")

        history.append({"gen": gen+1, "annual": gen_best["annual"], "maxdd": gen_best["maxdd"],
                        "sharpe": gen_best["sharpe"], "best_annual": best["annual"],
                        "best_maxdd": best["maxdd"], "hit": best["hit"]})

        if best["hit"]:
            print(f"\n🎯 第 {gen+1} 代达标！")
            break

        # 选择 + 繁殖
        elites = scored[:max(2, pop_size // 5)]
        new_pop = [e["ind"] for e in elites]   # 精英保留
        while len(new_pop) < pop_size:
            if random.random() < 0.5:
                pa, pb = random.sample(elites, 2)
                child = crossover(pa["ind"], pb["ind"], n_genes)
            else:
                parent = random.choice(elites)
                child = mutate(parent["ind"], n_genes)
            new_pop.append(child)
        pop = new_pop

    report(best, genes, history)
    return best


def report(best, genes, history):
    print("\n" + "="*64)
    print("最终结果")
    print("="*64)
    print(f"年化收益 : {best['annual']:+.2%}")
    print(f"最大回撤 : {best['maxdd']:.2%}")
    print(f"夏普比率 : {best['sharpe']:.2f}")
    print(f"卡玛比率 : {best.get('calmar',0):.2f}")
    print(f"是否达标 : {'✅ 达标' if best['hit'] else '❌ 未达标'}")

    ind = best["ind"]
    chosen = [g for g, m in zip(genes, ind["mask"]) if m]
    print(f"\n策略配置:")
    print(f"  持股数  : {ind['top_n']}")
    print(f"  调仓间隔: {ind['gap']} 交易日")
    print(f"  择时窗口: {ind['timing']}")
    print(f"  波动目标: {ind['vol_target']}")
    print(f"  杠杆上限: {ind['lev_max']}")
    print(f"  因子组合:")
    for g in chosen:
        print(f"    {g['name']:18s}{str(g['params']):18s} ICIR={g['icir']:+.3f}")

    # 净值图
    ret = best["ret"]
    cum = (1 + ret).cumprod()
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    cum.plot(ax=axes[0], color="navy", lw=1.5)
    axes[0].set_title(f"最优策略  年化={best['annual']:.2%}  回撤={best['maxdd']:.2%}  夏普={best['sharpe']:.2f}")
    axes[0].axhline(1, color="gray", ls="--", lw=0.8)
    axes[0].set_ylabel("净值")
    dd = cum / cum.cummax() - 1
    dd.plot(ax=axes[1], color="crimson", lw=1)
    axes[1].fill_between(dd.index, dd, 0, alpha=0.3, color="crimson")
    axes[1].axhline(-TARGET_MAXDD, color="orange", ls="--", label=f"回撤上限{TARGET_MAXDD:.0%}")
    axes[1].set_ylabel("回撤"); axes[1].legend()
    plt.tight_layout()
    fig.savefig("results/best_strategy.png", dpi=130)
    print("\n净值图: results/best_strategy.png")

    pd.DataFrame(history).to_csv("results/evolution_history.csv", index=False)
    with open("results/best_config.json", "w") as f:
        json.dump({
            "metrics": {k: round(float(v), 4) for k, v in best.items()
                        if k in ("annual","maxdd","sharpe","calmar")},
            "hit": bool(best["hit"]),
            "top_n": ind["top_n"], "gap": ind["gap"], "timing": ind["timing"],
            "vol_target": ind["vol_target"], "lev_max": ind["lev_max"],
            "factors": [{"name": g["name"], "params": g["params"],
                         "icir": round(float(g["icir"]), 3)} for g in chosen],
        }, f, indent=2)
    print("配置: results/best_config.json")


if __name__ == "__main__":
    os.chdir(Path(__file__).parent)
    close, volume, amount = load_panels()
    evolve(close, volume, amount, generations=25, pop_size=30)
