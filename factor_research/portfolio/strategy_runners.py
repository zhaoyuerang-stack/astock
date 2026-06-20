"""LIVE 母策略 runners — 给每个 LIVE 母策略一个统一接口。

输入: start date
输出: daily returns pd.Series

所有 runner 共享:
  - data_lake 数据源
  - PureTrend(MA16) timing on small-cap index
  - top_n=25, rebal_days=20, leverage=1.25 (除非另注)
  - CostModel 标准成本

唯一变化点是 factor 公式。
"""
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

from core.engine import BacktestConfig, BacktestEngine, CostModel, PricePanel, Signal
from strategies.small_cap import build_rebalance_weights, load_price_panels
from factors.small_cap import small_cap_factor, small_cap_timing
from factors.utils import mad_clip, safe_zscore


@lru_cache(maxsize=4)
def _load_panels(start: str):
    """Cache panels per start to avoid reloading."""
    return load_price_panels(start)


# ────────────────────────── Factor builders ──────────────────────────

def _f_small_cap(close, volume, amount):
    return small_cap_factor(amount, window=60)


def _f_illiquidity(close, volume, amount, n=20):
    """Amihud illiquidity = mean(|ret|/amount). Positive = more illiquid → higher expected ret."""
    ret = close.pct_change(fill_method=None).abs()
    illiq = (ret / (amount.replace(0, np.nan) + 1)).rolling(n).mean()
    return safe_zscore(mad_clip(illiq))


def _f_size_low_vol(close, volume, amount, vol_window=20):
    """size60 + low_vol(-std20d): equal weight blend, z-scored."""
    size = small_cap_factor(amount, window=60)
    daily_ret = close.pct_change(fill_method=None)
    vol = daily_ret.rolling(vol_window).std()
    low_vol = safe_zscore(mad_clip(-vol))
    return safe_zscore(mad_clip(0.5 * size + 0.5 * low_vol))


# ────────────────────────── Generic runner ──────────────────────────

def _run_with_factor(
    factor_builder,
    *,
    start: str,
    top_n: int = 25,
    rebal_days: int = 20,
    leverage: float = 1.25,
    family: str = "",
    version: str = "",
) -> pd.Series:
    close, volume, amount = _load_panels(start)
    prices = PricePanel(close=close, volume=volume, amount=amount)

    factor = factor_builder(close, volume, amount)
    timing, _, _ = small_cap_timing(close, amount, ma_window=16)
    scheduled = build_rebalance_weights(factor, close, top_n=top_n, rebalance_days=rebal_days)

    cfg = BacktestConfig(
        start=start,
        cost=CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.065),
        leverage=leverage,
    )
    engine = BacktestEngine(prices=prices, config=cfg)
    signal = Signal(weights=scheduled, timing=timing, family=family, version=version)
    result = engine.run(signal)
    return result.returns.dropna()


# ────────────────────────── Cross-asset ETF runners ──────────────────────────

_ETF_DIR = (Path(__file__).resolve().parent.parent
            / "data_lake" / "cross_asset" / "etf")


@lru_cache(maxsize=8)
def _load_etf_close(code: str) -> pd.Series:
    fp = _ETF_DIR / f"{code}.parquet"
    df = pd.read_parquet(fp)
    df["date"] = pd.to_datetime(df["date"])
    return df.set_index("date").sort_index()["close"]


def _run_etf_trend(code: str, ma: int = 60, start: str = "2018-01-01") -> pd.Series:
    """ETF MA-N 趋势策略: close > MA → 持仓, 否则空仓. leverage 1.0x."""
    close = _load_etf_close(code).loc[start:]
    ma_line = close.rolling(ma).mean()
    in_mkt = (close > ma_line).shift(1, fill_value=False).astype(float)
    return (close.pct_change(fill_method=None).fillna(0) * in_mkt).dropna()


# ────────────────────────── Public LIVE runners ──────────────────────────

# 2026-06-07 引入 status 字段：
#   ACTIVE = 进入组合，贡献组合层 alpha
#   SHADOW = 不进入组合 (paper trade 观察期，等待恢复或正式退役)
#
# 决策依据 (2026-06-07 实测 2018-2026 全样本)：
#   illiquidity v1.0:   单 Sharpe 1.78，组合基线
#   small-cap v2.0:     marginal +0.104 (加入提升组合) → ACTIVE
#   size-low-vol v1.0:  marginal -0.120 (加入拖累组合) → SHADOW
#   size-earnings v1.0: marginal -0.277 (拖累最严重)   → SHADOW
#
# 组合实测改善：2 ACTIVE risk_parity Sharpe 1.89 vs 4 LIVE 等权 1.60 (+18%)
LIVE_STRATEGIES = {
    "small-cap-size.v2.0": {
        "desc": "size60 + PT-MA16 Band 1.0x (timing_mode=band 2026-06-07)",
        "status": "ACTIVE",
        "timing_mode": "band",      # 主决策: Band timing (dynamic 0~1.5x)
        "marginal_sharpe": +0.104,
        "fn": lambda start: _run_with_factor(
            _f_small_cap, start=start,
            family="small-cap-size", version="v2.0",
        ),
    },
    "illiquidity.v1.0": {
        "desc": "Amihud illiq20 + PT-MA16 Band 1.0x (生产基线, timing_mode=band 2026-06-07)",
        "status": "ACTIVE",
        "timing_mode": "band",      # 主决策: Band timing (dynamic 0~1.5x)
        "marginal_sharpe": None,    # baseline reference
        "fn": lambda start: _run_with_factor(
            _f_illiquidity, start=start,
            family="illiquidity", version="v1.0",
        ),
    },
    "size-low-vol.v1.0": {
        "desc": "size60 + low_vol20 + PT-MA16 + Lev1.25x (2026-06-07 转 SHADOW)",
        "status": "SHADOW",
        "marginal_sharpe": -0.120,
        "shadow_since": "2026-06-07",
        "shadow_reason": "组合层边际负贡献 -0.120 vs illiquidity baseline",
        "fn": lambda start: _run_with_factor(
            _f_size_low_vol, start=start,
            family="size-low-vol", version="v1.0",
        ),
    },
    "gov_bond_etf_511010.MA60": {
        "desc": "国债 ETF 511010 + MA60 趋势 + 1.0x (跨资产防御腿, 2026-06-14 转 ACTIVE)",
        "role": "defensive",
        # 2026-06-14 SHADOW→ACTIVE:跨资产腿搜索证无条件正边际(Δsh +0.64、逐年皆正、
        # 牛年不拖、corr -0.09),区别于 hedged-equity 的 regime 条件正边际。
        # 组合须用 equal_weight(compose 默认),禁 vanilla risk_parity(低波债券会被灌满权重→年化崩)。
        "status": "ACTIVE",
        "active_since": "2026-06-14",
        "marginal_sharpe": +0.64,
        "validation": {
            "wf_oos_positive_years": "6/6",
            "yearly_all_positive": True,
            "stress_period_defense": "5/5",
            "corr_to_a_stocks": -0.09,
            "compose_caveat": "equal_weight only; risk_parity 退化为债券基金(年化崩到 8.9%)",
        },
        "fn": lambda start: _run_etf_trend("511010", ma=60, start=start),
    },
    "gold_etf_518880.MA60": {
        "desc": "黄金 ETF 518880 + MA60 趋势 + 1.0x (第二防御腿, 2026-06-14 转 ACTIVE)",
        "role": "defensive",
        # 2026-06-14 SHADOW→ACTIVE:跨资产腿搜索 Δsh +0.37、corr -0.005、崩盘日 +7‱
        #(全场最强尾部对冲)、2018 +3.7%;与国债正交(国债平时稳/黄金治尾部)。
        "status": "ACTIVE",
        "active_since": "2026-06-14",
        "marginal_sharpe": +0.37,
        "validation": {
            "corr_to_book": -0.005,
            "ret_2018": 0.037,
            "down_capture_strongest": True,
            "standalone_sharpe": 1.02,
            "compose_caveat": "equal_weight only; risk_parity 灌满低波资产",
        },
        "fn": lambda start: _run_etf_trend("518880", ma=60, start=start),
    },
    "size-earnings.v1.0": {
        "desc": "size60 + NPY blend λ=0.5 + PT-MA16 × VolTarget(25%) + Lev1.10x (2026-06-07 转 SHADOW)",
        "status": "SHADOW",
        "marginal_sharpe": -0.277,
        "shadow_since": "2026-06-07",
        "shadow_reason": "组合层边际负贡献 -0.277 (最严重)",
        "fn": None,   # Special: 用现成 run_strategy
    },
}


def run_size_earnings(start: str = "2018-01-01") -> pd.Series:
    """Wrap strategies/size_earnings.run_strategy()."""
    from strategies.size_earnings import StrategyConfig, run_strategy
    cfg = StrategyConfig(start=start)
    return run_strategy(cfg)["returns"].dropna()


LIVE_STRATEGIES["size-earnings.v1.0"]["fn"] = run_size_earnings


def run_all_live(start: str = "2018-01-01") -> dict[str, pd.Series]:
    """跑全部 LIVE 母策略（含 SHADOW），返回 {name: returns}."""
    out = {}
    for name, spec in LIVE_STRATEGIES.items():
        out[name] = spec["fn"](start)
    return out


def run_active(start: str = "2018-01-01") -> dict[str, pd.Series]:
    """只跑 ACTIVE 状态的策略——组合层应用这个。"""
    out = {}
    for name, spec in LIVE_STRATEGIES.items():
        if spec.get("status", "ACTIVE") == "ACTIVE":
            out[name] = spec["fn"](start)
    return out


def active_strategies() -> list[str]:
    """返回 ACTIVE 策略名列表（不跑回测）."""
    return [n for n, s in LIVE_STRATEGIES.items() if s.get("status", "ACTIVE") == "ACTIVE"]


def shadow_strategies() -> list[str]:
    """返回 SHADOW 策略名列表."""
    return [n for n, s in LIVE_STRATEGIES.items() if s.get("status") == "SHADOW"]


def defensive_strategies() -> set[str]:
    """返回 role=defensive 的 ACTIVE 腿(跨资产防御腿),供 compose(method='capped') 封顶权重。"""
    return {n for n, s in LIVE_STRATEGIES.items()
            if s.get("role") == "defensive" and s.get("status", "ACTIVE") == "ACTIVE"}
