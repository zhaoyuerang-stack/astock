"""MVP 策略腿工厂 — 最小验证链路.

搜索空间: illiq LONG/SHORT × 2 择时 × 2 regime = 8 条腿
验证: 最佳编排方案是否优于当前基线.

用法:
  cd /Users/kiki/astcok/factor_research
  /opt/homebrew/bin/python3 scripts/research/mvp_leg_factory.py
"""
import os, sys, warnings
from pathlib import Path
warnings.filterwarnings("ignore")
os.chdir(Path(__file__).resolve().parent.parent.parent)
sys.path.insert(0, str(Path.cwd()))

import numpy as np
import pandas as pd
from core.backtest import load_price_panels
from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from factors.small_cap import small_cap_factor, small_cap_timing
from strategies.small_cap import build_rebalance_weights
from engine.regime import RegimeEngine
from factory.analysis.asymmetry_audit import asymmetry_report


def build_weight_dict(factor, close, top_n=25, rebalance_days=20, direction=1):
    """构建权重字典. direction: 1=long top-N, -1=long bottom-N."""
    if direction == 1:
        return build_rebalance_weights(factor, close, top_n=top_n, rebalance_days=rebalance_days)
    else:
        neg_factor = -factor
        return build_rebalance_weights(neg_factor, close, top_n=top_n, rebalance_days=rebalance_days)


def build_band_timing(close, amount, ma_window=16, exp_cap=1.5):
    """构建 Band timing 序列."""
    _, _, dist = small_cap_timing(close, amount, ma_window=ma_window)
    dist_s = dist.shift(1)
    return ((1 + dist_s * 8).clip(0, exp_cap) * (dist_s > 0)).fillna(0.0)


def evaluate_leg(weights, timing, exp_cap, regime_mask, close, amount, label):
    """评估一条腿: 在目标 regime 内的表现."""
    prices = PricePanel(close=close, volume=None, amount=amount)
    cfg = BacktestConfig(start="2018-01-01", cost=CostModel(), leverage=1.0)
    engine = BacktestEngine(prices=prices, config=cfg)

    # 全时段回测
    r = engine.run(Signal(weights=weights, timing=timing, exposure_cap=exp_cap,
                          family="mvp", version="")).returns.loc["2018-01-01":].dropna()
    if len(r) < 100:
        return None

    # 目标 regime 内的表现
    common = r.index.intersection(regime_mask.index)
    regime_mask_aligned = regime_mask.reindex(common).fillna(False)
    r_regime = r[regime_mask_aligned]

    if len(r_regime) < 50:
        return None

    reg_ann = float(r_regime.mean() * 252)
    reg_vol = float(r_regime.std() * np.sqrt(252))
    reg_sh = (reg_ann - 0.025) / reg_vol if reg_vol > 0 else 0
    reg_dd = float(((1 + r_regime).cumprod() / (1 + r_regime).cumprod().cummax() - 1).min())

    # 全时段指标 (对照)
    full_ann = float(r.mean() * 252)
    full_dd = float(((1 + r).cumprod() / (1 + r).cumprod().cummax() - 1).min())

    return {
        "label": label, "r_full": r, "r_regime": r_regime,
        "reg_ann": reg_ann, "reg_sh": reg_sh, "reg_dd": reg_dd,
        "full_ann": full_ann, "full_dd": full_dd,
        "n_days": len(r_regime),
    }


def compose_and_evaluate(bull_leg, bear_leg, close, amount):
    """编排两条腿 + 评估组合."""
    r_bull = bull_leg["r_full"]; r_bear = bear_leg["r_full"]
    common = r_bull.index.intersection(r_bear.index)

    # 用 regime engine 重新获取 mask
    re2 = RegimeEngine(close, amount)
    bull_mask = re2.trend_up.reindex(common).fillna(False)
    bear_mask = re2.trend_down.reindex(common).fillna(False)

    combined = []
    for dt in common:
        if bull_mask.loc[dt]:
            combined.append(r_bull.loc[dt])
        elif bear_mask.loc[dt]:
            combined.append(r_bear.loc[dt])
        else:
            combined.append(0.0)
    r_combo = pd.Series(combined, index=common)

    # 不对称性审计
    mkt = close.loc["2018-01-01":].pct_change().mean(axis=1).fillna(0)
    rep = asymmetry_report(r_combo, mkt, "combo")

    ann = float(r_combo.mean() * 252)
    dd = float(((1 + r_combo).cumprod() / (1 + r_combo).cumprod().cummax() - 1).min())
    nav = (1 + r_combo).cumprod().iloc[-1] * 100

    return {
        "bull_leg": bull_leg["label"], "bear_leg": bear_leg["label"],
        "ann": ann, "mdd": dd, "nav": nav,
        "sharpe": rep.sharpe, "sortino": rep.sortino,
        "gain_pain": rep.gain_pain, "asym_score": rep.asymmetry_score,
        "verdict": rep.verdict,
    }


def main():
    print("=" * 80)
    print("  MVP 策略腿工厂: illiq LONG/SHORT × 择时 × regime")
    print("=" * 80)

    print("\n[1/4] 加载数据 + Regime 引擎...", flush=True)
    close, volume, amount = load_price_panels("2010-01-01")
    re = RegimeEngine(close, amount)
    labels = re.classify()
    summary = re.summary()
    print(f"  Trend:  {summary['trend']}")
    print(f"  Vol:    {summary['volatility']}")
    print(f"  Liq:    {summary['liquidity']}")

    # ── 构建腿 ──
    print("\n[2/4] 构建策略腿...", flush=True)
    illiq = small_cap_factor(amount, window=60)

    legs_config = [
        # (label, direction, timing_type, regime_key, regime_val)
        ("LONG + Band      ", 1, "band", "trend", "up"),
        ("LONG + noTiming  ", 1, "none", "trend", "up"),
        ("LONG + Band      ", 1, "band", "trend", "down"),
        ("LONG + noTiming  ", 1, "none", "trend", "down"),
        ("SHORT + Band     ", -1, "band", "trend", "up"),
        ("SHORT + noTiming ", -1, "none", "trend", "up"),
        ("SHORT + Band     ", -1, "band", "trend", "down"),
        ("SHORT + noTiming ", -1, "none", "trend", "down"),
    ]

    legs = []
    for label, direction, timing_type, regime_key, regime_val in legs_config:
        w = build_weight_dict(illiq, close, top_n=25, rebalance_days=20, direction=direction)
        if timing_type == "band":
            t = build_band_timing(close, amount, ma_window=16, exp_cap=1.5)
            exp_cap = 1.5
        else:
            t = pd.Series(1.0, index=close.index)
            exp_cap = 1.0

        mask = re.get_regime_mask(**{regime_key: regime_val})
        result = evaluate_leg(w, t, exp_cap, mask, close, amount, label.strip())
        if result:
            legs.append(result)

    # ── 评估 ──
    print(f"\n[3/4] 腿评估 ({len(legs)} 条)...\n")
    print(f"  {'腿':<22} {'Regime':<12} {'Reg年化':>9} {'Reg回撤':>9} {'Reg夏普':>7} {'全日年化':>9}")
    print("  " + "-" * 75)
    for leg in legs:
        parts = leg["label"].split()
        direction, timing = parts[0], parts[1] if len(parts) > 1 else ""
        # figure out regime from label context
        print(f"  {leg['label']:<22} {'?':<12} {leg['reg_ann']:>+8.1%} "
              f"{leg['reg_dd']:>+8.1%} {leg['reg_sh']:>+6.2f} {leg['full_ann']:>+8.1%}")

    # ── 编排优化 ──
    print(f"\n[4/4] 编排优化\n")

    # 基线: LONG + Band, 当前生产
    band_exp = build_band_timing(close, amount)
    w_long = build_weight_dict(illiq, close, top_n=25, rebalance_days=20, direction=1)
    prices = PricePanel(close=close, volume=None, amount=amount)
    engine = BacktestEngine(prices=prices, config=BacktestConfig(start="2018-01-01", cost=CostModel(), leverage=1.0))
    r_base = engine.run(Signal(weights=w_long, timing=band_exp, exposure_cap=1.5,
                        family="x", version="")).returns.loc["2018-01-01":].dropna()
    base_ann = float(r_base.mean() * 252)
    base_dd = float(((1 + r_base).cumprod() / (1 + r_base).cumprod().cummax() - 1).min())
    base_nav = (1 + r_base).cumprod().iloc[-1] * 100

    # 找最佳 bull 腿 (regime=up 中最好的)
    bull_legs = [l for l in legs if "LONG" in l["label"]]
    bear_legs = [l for l in legs if "SHORT" in l["label"]]

    # 全量编排组合
    combos = []
    for bull in bull_legs:
        for bear in bear_legs:
            c = compose_and_evaluate(bull, bear, close, amount)
            combos.append(c)

    combos.sort(key=lambda x: x["nav"], reverse=True)

    print(f"  {'基线':>30}: ann={base_ann:+.1%} mdd={base_dd:.1%} nav={base_nav:.0f}万\n")
    print(f"  {'编排组合 (bull + bear)':<45} {'年化':>8} {'回撤':>8} {'夏普':>6} {'终值':>7} {'g/p':>6} {'评分':>6}")
    print("  " + "-" * 90)
    for c in combos[:10]:
        delta_ann = c["ann"] - base_ann
        delta_nav = c["nav"] - base_nav
        flag = "✅" if c["nav"] > base_nav else "❌"
        print(f"  {c['bull_leg']:<20} + {c['bear_leg']:<20} {c['ann']:>+7.1%} {c['mdd']:>+7.1%} "
              f"{c['sharpe']:>5.2f} {c['nav']:>6.0f}万 {c['gain_pain']:>5.2f} {c['asym_score']:>5.0%} {flag}")

    # 最佳 vs 基线详细对比
    if combos:
        best = combos[0]
        print(f"\n  最佳编排: {best['bull_leg']} + {best['bear_leg']}")
        print(f"    年化: {best['ann']:+.1%} (基线 {base_ann:+.1%}, Δ={best['ann']-base_ann:+.1%})")
        print(f"    回撤: {best['mdd']:.1%} (基线 {base_dd:.1%})")
        print(f"    终值: {best['nav']:.0f}万 (基线 {base_nav:.0f}万, Δ={best['nav']-base_nav:+.0f}万)")
        print(f"    gain/pain: {best['gain_pain']:.2f}x")
        print(f"    不对称性: {best['verdict']}")

    print()


if __name__ == "__main__":
    main()
