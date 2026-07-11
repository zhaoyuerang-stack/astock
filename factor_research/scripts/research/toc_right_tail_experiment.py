"""TOC 右尾 A 实验:rank-buffer 成员滞回 + 凸性加权(走权威引擎,apples-to-apples)。

四臂只在 weights 构造上不同,其余(因子/择时/价格/成本/引擎)完全一致:
  BASE   : 等权 top_n + 20D 调仓                 —— 复现在册基线(保真度闸门)
  A1a    : rank-buffer 成员滞回(仍在 top-2N 不卖) + 等权
  A2     : 凸性加权(因子强度 rank-linear 倾斜) + 无 buffer
  A1a+A2 : 滞回 + 凸性

纪律:
  - 不动权威引擎 core.engine(它不支持权重漂移,A1b 真·let-winners-run 需引擎扩展,本轮不做)。
  - 凸性方案固定为 rank-linear(无温度参数),避免多重测试自由度膨胀。
  - 同一把尺子:engine.metrics.metrics(组合层) + winner_concentration(选股层)。
"""
import io
import os
import sys
import json
from contextlib import redirect_stdout
from pathlib import Path

PROJECT_ROOT = Path("/Users/kiki/astcok/factor_research")
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from strategies.ai_compute_toc import (
    StrategyConfig, load_price_panels, build_factor, build_timing,
)
from lake.load_lake import load_raw_close, load_fina_indicator_panel
from engine.metrics import metrics, winner_concentration

START = "2010-06-01"
WINDOWS = {
    "registered_2018_2026": pd.Timestamp("2018-01-01"),
    "oos_2023_2026": pd.Timestamp("2023-01-01"),
    "stress_2010_2026": pd.Timestamp("2010-06-01"),
}


def build_weights(factor, close, amount, roe_panel, top_n, rebalance_days, roe_thresh,
                  weight_scheme="equal", buffer_mult=None):
    """通用 weights 构造:复刻基线掩码,仅参数化选股(buffer)与加权(scheme)。"""
    fdates = factor.dropna(how="all").index.intersection(close.index)
    fdates = fdates[fdates >= "2010-06-01"]
    if len(fdates) < 20:
        return {}
    liq_rank = amount.rolling(20).mean().rank(axis=1, ascending=False)
    universe_mask = (liq_rank <= 500) & close.notna()
    roe_mask = roe_panel > roe_thresh

    weights = {}
    holdings = []  # 上期持仓(buffer 滞回用)
    for rd in list(fdates[::rebalance_days]):
        pos = close.index.get_loc(rd)
        if pos + 1 >= len(close.index):
            continue
        effective = close.index[pos + 1]
        mask_rd = universe_mask.loc[rd] & roe_mask.loc[rd]
        f = factor.loc[rd].where(mask_rd).dropna()
        active = close.loc[rd].dropna().index
        f = f.reindex(active).dropna()
        if len(f) < top_n:
            continue
        ranked = f.sort_values(ascending=False)

        if buffer_mult:  # rank-buffer 成员滞回
            keep_pool = set(ranked.index[: int(top_n * buffer_mult)])
            kept = [c for c in holdings if c in keep_pool][:top_n]
            need = top_n - len(kept)
            add = [c for c in ranked.index if c not in kept][:need]
            selected = kept + add
        else:
            selected = list(ranked.index[:top_n])
        holdings = selected

        if weight_scheme == "equal":
            w = pd.Series(1.0 / top_n, index=selected, dtype="float64")
        elif weight_scheme == "convex":  # 因子强度 rank-linear 倾斜:最强=top_n 份、最弱=1 份
            order = f.reindex(selected).sort_values(ascending=False)
            tilt = pd.Series(range(top_n, 0, -1), index=order.index, dtype="float64")
            w = (tilt / tilt.sum()).reindex(selected).astype("float64")
        else:
            raise ValueError(weight_scheme)
        weights[effective] = w
    return weights


def run_arm(prices, roe_panel, factor, timing, scheduled, cfg):
    engine_config = BacktestConfig(
        start=cfg.start,
        cost=CostModel(buy_cost=cfg.cost.buy_cost, sell_cost=cfg.cost.sell_cost,
                       financing_rate=cfg.cost.financing_rate),
        leverage=cfg.leverage,
    )
    engine = BacktestEngine(prices=prices, config=engine_config)
    sig = Signal(weights=scheduled, timing=timing, family="ai-compute-toc", version="exp")
    return engine.run(sig)


def score(returns, scheduled, close, bench):
    out = {}
    for label, start in WINDOWS.items():
        rr = returns.loc[start:].dropna()
        out[label] = {
            "portfolio": metrics(rr, bench=bench.reindex(rr.index)),
            "stockpick": winner_concentration(scheduled, close, win_start=start),
        }
    return out


def main():
    cfg = StrategyConfig(start=START)
    buf = io.StringIO()
    with redirect_stdout(buf):
        close, volume, amount = load_price_panels("2010-01-01")
        prices = PricePanel(close=close, volume=volume, amount=amount)
        raw = load_raw_close(start="2010-01-01")
        if not raw.empty:
            raw_aligned = raw.reindex(index=close.index, columns=close.columns)
            prices = PricePanel(close=close, volume=volume, amount=amount, raw_close=raw_aligned)
        codes = list(close.columns)
        roe_panel = load_fina_indicator_panel(close.index, codes=codes, fields=["roe"])["roe"].shift(1)
        factor = build_factor(close, close.index, accel_diff=cfg.accel_diff)
        timing, _, _ = build_timing(close, amount, ma_window=16)

    bench = close.pct_change(fill_method=None).mean(axis=1).fillna(0.0)

    arms = {
        "BASE":     dict(weight_scheme="equal",  buffer_mult=None),
        "A1a_buf":  dict(weight_scheme="equal",  buffer_mult=2.0),
        "A2_convex":dict(weight_scheme="convex", buffer_mult=None),
        "A1A2":     dict(weight_scheme="convex", buffer_mult=2.0),
    }

    report = {}
    for name, kw in arms.items():
        sched = build_weights(factor, close, amount, roe_panel, cfg.top_n,
                              cfg.rebalance_days, cfg.roe_threshold, **kw)
        buf2 = io.StringIO()
        with redirect_stdout(buf2):
            res = run_arm(prices, roe_panel, factor, timing, sched, cfg)
        report[name] = {
            "n_rebalances": len(sched),
            "avg_annual_turnover": float(res.turnover.mean() * 252),
            "windows": score(res.returns, sched, close, bench),
        }

    with open("scratch/toc_right_tail_experiment.json", "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)

    # 控制台对照表(聚焦 oos + registered 两窗的右尾核心标量)
    print("WROTE scratch/toc_right_tail_experiment.json\n")
    hdr = f"{'arm':10} {'win':14} {'annual':>8} {'maxdd':>8} {'calmar':>7} {'cap_spr':>8} {'top1':>6} {'cvarR':>7} {'turn':>6}"
    print(hdr)
    print("-" * len(hdr))
    for name in arms:
        for win in ("registered_2018_2026", "oos_2023_2026"):
            p = report[name]["windows"][win]["portfolio"]
            s = report[name]["windows"][win]["stockpick"]
            print(f"{name:10} {win:14} {p['annual']:+8.2%} {p['maxdd']:+8.2%} "
                  f"{p['calmar']:7.2f} {p.get('capture_spread', float('nan')):+8.3f} "
                  f"{s['winners_top1_share']:6.3f} {p['cvar_right']:7.4f} "
                  f"{report[name]['avg_annual_turnover']:6.1f}")


if __name__ == "__main__":
    main()
