"""
因子研究主程序

用法：
  python scripts/research/main.py --run single --factor mom20  # 单因子IC分析
  python scripts/research/main.py --run all                    # 全因子扫描
  python scripts/research/main.py --run composite              # 多因子合成 + 组合回测
  python scripts/research/main.py --fetch                      # 强制重新拉取全市场数据
"""
import argparse
import os, sys
import warnings
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore")

from engine.fetch import get_stock_codes, get_stock_industry, batch_fetch_kline
from engine.neutralize import process_factor
from engine.backtest import factor_summary, calc_ic, stratify_return, cumulative_return, long_short_return
from engine.composer import equal_weight, ic_weight, factor_corr_matrix
from engine.universe import build_universe_panel, apply_universe_mask
from engine.portfolio import top_n_portfolio, calc_portfolio_return, performance_metrics
from factors.momentum import mom_n, vol_ratio, volatility, illiquidity, price_to_ma

START = "2018-01-01"
FORWARD_DAYS = 20
CACHE_CLOSE  = "data/close.parquet"
CACHE_VOL    = "data/volume.parquet"
CACHE_AMT    = "data/amount.parquet"


# ──────────────────────────────────────────
# 数据加载
# ──────────────────────────────────────────

def load_panels() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    import os
    if all(os.path.exists(p) for p in [CACHE_CLOSE, CACHE_VOL, CACHE_AMT]):
        print("读取本地K线缓存...")
        close  = pd.read_parquet(CACHE_CLOSE)
        volume = pd.read_parquet(CACHE_VOL)
        amount = pd.read_parquet(CACHE_AMT)
        print(f"  {close.shape[1]} 只股票 | {close.index.min().date()} ~ {close.index.max().date()}")
        return close, volume, amount

    codes = get_stock_codes()
    print(f"拉取 {len(codes)} 只股票（首次约20分钟）...")
    long_df = batch_fetch_kline(codes, START)

    close  = long_df.pivot(index="date", columns="code", values="close")
    volume = long_df.pivot(index="date", columns="code", values="volume")
    amount = long_df.pivot(index="date", columns="code", values="amount")

    close.to_parquet(CACHE_CLOSE)
    volume.to_parquet(CACHE_VOL)
    amount.to_parquet(CACHE_AMT)
    return close, volume, amount


def calc_forward_return(close: pd.DataFrame, n: int = FORWARD_DAYS) -> pd.DataFrame:
    return close.shift(-n) / close - 1


# ──────────────────────────────────────────
# 因子注册表（原始，未中性化）
# ──────────────────────────────────────────

FACTOR_REGISTRY = {
    "mom5":       lambda c, v, a: mom_n(c, 5),
    "mom20":      lambda c, v, a: mom_n(c, 20, skip=5),
    "mom60":      lambda c, v, a: mom_n(c, 60, skip=5),
    "reversal":   lambda c, v, a: -mom_n(c, 5),          # 短期反转
    "vol_ratio":  lambda c, v, a: vol_ratio(v),
    "low_vol":    lambda c, v, a: -volatility(c, 20),
    "illiq":      lambda c, v, a: -illiquidity(c, v),
    "price_ma20": lambda c, v, a: price_to_ma(c, 20),
}


def build_factor(
    name: str,
    close: pd.DataFrame,
    volume: pd.DataFrame,
    amount: pd.DataFrame,
    industry_map: pd.DataFrame,
    universes: dict,
    cap: pd.DataFrame = None,
) -> pd.DataFrame:
    raw = FACTOR_REGISTRY[name](close, volume, amount)
    raw = apply_universe_mask(raw, universes)           # 过滤不可交易股票
    processed = process_factor(raw, industry_map, cap)  # 去极值+中性化+标准化
    return processed


# ──────────────────────────────────────────
# 运行模式
# ──────────────────────────────────────────

def run_single(factor_name: str, close, volume, amount, industry_map, universes):
    print(f"\n===== 单因子分析: {factor_name} =====")
    factor = build_factor(factor_name, close, volume, amount, industry_map, universes)
    fwd = calc_forward_return(close)
    result = factor_summary(factor, fwd, factor_name)

    print(f"  IC均值   : {result['IC_mean']:+.4f}")
    print(f"  ICIR     : {result['ICIR']:+.2f}")
    print(f"  IC>0比率 : {result['IC>0_ratio']:.1%}")
    print(f"  多空年化 : {result['LS_annual']:+.2%}")
    print(f"  多空夏普 : {result['LS_sharpe']:+.2f}")
    print(f"  多空最大回撤: {result['LS_maxdd']:.2%}")

    # 分层净值图
    strat = stratify_return(factor, fwd)
    if not strat.empty:
        cum = cumulative_return(strat)
        ls  = long_short_return(strat)
        fig, axes = plt.subplots(2, 1, figsize=(12, 8))
        cum.plot(ax=axes[0], title=f"{factor_name} 分层累计收益")
        (1 + ls).cumprod().plot(ax=axes[1], title="多空组合净值", color="navy")
        axes[1].axhline(1, color="gray", linestyle="--")
        plt.tight_layout()
        fig.savefig(f"data/{factor_name}_backtest.png", dpi=120)
        print(f"  图表已保存: data/{factor_name}_backtest.png")
    return result


def run_all(close, volume, amount, industry_map, universes):
    print("\n===== 全因子扫描 =====")
    fwd = calc_forward_return(close)
    results = []
    for name in FACTOR_REGISTRY:
        try:
            factor = build_factor(name, close, volume, amount, industry_map, universes)
            r = factor_summary(factor, fwd, name)
            results.append(r)
            print(f"  {name:<12} IC={r['IC_mean']:+.4f}  ICIR={r['ICIR']:+.2f}  "
                  f"多空年化={r['LS_annual']:+.2%}  夏普={r['LS_sharpe']:+.2f}")
        except Exception as e:
            print(f"  {name:<12} 失败: {e}")

    summary = pd.DataFrame(results).set_index("factor")
    summary = summary[["IC_mean", "ICIR", "IC>0_ratio", "LS_annual", "LS_sharpe", "LS_maxdd"]]
    summary.columns = ["IC均值", "ICIR", "IC>0率", "多空年化", "多空夏普", "多空最大回撤"]
    summary = summary.sort_values("ICIR", ascending=False)

    print("\n========== 因子排名（按ICIR） ==========")
    print(summary.round(4).to_string())
    summary.to_csv("data/factor_summary.csv")
    print("\n结果已保存至 data/factor_summary.csv")
    return summary


def run_composite(close, volume, amount, industry_map, universes):
    print("\n===== 多因子合成 =====")
    fwd = calc_forward_return(close)

    # 1. 计算各因子
    factors = {}
    for name in FACTOR_REGISTRY:
        try:
            factors[name] = build_factor(name, close, volume, amount, industry_map, universes)
        except Exception as e:
            print(f"  [{name}] 跳过: {e}")

    # 2. 因子相关性矩阵（诊断冗余）
    print("\n因子截面相关矩阵（Spearman，近60期均值）:")
    corr = factor_corr_matrix(factors)
    print(corr.to_string())
    corr.to_csv("data/factor_corr.csv")

    # 3. IC加权合成
    print("\n合成因子（IC加权）...")
    composite = ic_weight(factors, fwd, ic_window=12)

    # 4. 合成因子回测
    result = factor_summary(composite, fwd, "composite_ic_weight")
    print(f"  IC均值={result['IC_mean']:+.4f}  ICIR={result['ICIR']:+.2f}  "
          f"多空年化={result['LS_annual']:+.2%}  夏普={result['LS_sharpe']:+.2f}")

    # 5. 组合构建与净值
    print("\n构建Top100等权组合...")
    weight = top_n_portfolio(composite, n=100)
    port_ret = calc_portfolio_return(weight, close)
    metrics = performance_metrics(port_ret)
    print("\n========== 组合绩效 ==========")
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    # 6. 净值图
    cum = (1 + port_ret.dropna()).cumprod()
    fig, ax = plt.subplots(figsize=(12, 5))
    cum.plot(ax=ax, label="多因子合成组合", color="navy")
    ax.axhline(1, color="gray", linestyle="--")
    ax.set_title("多因子合成组合净值（Top100等权）")
    ax.legend()
    plt.tight_layout()
    fig.savefig("data/composite_portfolio.png", dpi=120)
    print("净值图已保存: data/composite_portfolio.png")


# ──────────────────────────────────────────
# 入口
# ──────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", choices=["single", "all", "composite"], default="all")
    parser.add_argument("--factor", default="mom20")
    parser.add_argument("--fetch", action="store_true", help="强制重新拉取数据")
    args = parser.parse_args()

    if args.fetch:
        import os
        for p in [CACHE_CLOSE, CACHE_VOL, CACHE_AMT]:
            if os.path.exists(p):
                os.remove(p)

    close, volume, amount = load_panels()

    industry_map = get_stock_industry()

    # 股票池：过滤停牌（无ST数据则只过滤停牌+次新）
    print("构建股票池...")
    universes = build_universe_panel(close, volume, freq="W")
    print(f"  样本调仓日: {len(universes)} 个")

    if args.run == "single":
        run_single(args.factor, close, volume, amount, industry_map, universes)
    elif args.run == "all":
        run_all(close, volume, amount, industry_map, universes)
    elif args.run == "composite":
        run_composite(close, volume, amount, industry_map, universes)


if __name__ == "__main__":
    main()
