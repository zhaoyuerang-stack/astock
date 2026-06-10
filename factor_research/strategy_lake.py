"""
策略迁移到 data_lake 加载层复测 —— 打假验证
统一使用 core.engine.BacktestEngine: data_lake 口径 + 真实换手成本 + 融资成本。

验证：①2018-2026对比旧40.4%(看active过滤/幸存者偏差的影响)
      ②2010-2026压力测试(含2015股灾/2017小盘崩盘)
"""
import warnings; warnings.filterwarnings("ignore")
import os
from pathlib import Path
os.chdir(Path(__file__).parent)

# Phase-2 migration: use unified BacktestEngine instead of legacy run_small_cap_strategy()
from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from strategies.small_cap import load_price_panels, build_rebalance_weights
from factors.small_cap import small_cap_factor, small_cap_timing
from engine.metrics import metrics, yearly_returns


def run_backtest(label, start):
    print(f"\n{label}", flush=True)

    # Load data
    close, volume, amount = load_price_panels(start)
    prices = PricePanel(close=close, volume=volume, amount=amount)

    # Build signal via unified engine
    factor = small_cap_factor(amount, window=60)
    timing, _, _ = small_cap_timing(close, amount, ma_window=16)
    scheduled = build_rebalance_weights(factor, close, top_n=25, rebalance_days=20)

    engine = BacktestEngine(
        prices=prices,
        config=BacktestConfig(
            start=start,
            cost=CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.065),
            leverage=1.25,
        ),
    )
    signal = Signal(
        weights=scheduled,
        timing=timing,
        family="small-cap-size",
        version="v2.0",
    )
    result = engine.run(signal)

    # Output (identical format to legacy)
    m = result.metrics
    print(f"  载入 {close.shape[1]}只 × {close.shape[0]}日 "
          f"[{close.index[0].date()}~{close.index[-1].date()}]", flush=True)
    print(f"  → 年化={m['annual']:+.2%} 回撤={m['maxdd']:.2%} 夏普={m['sharpe']:.2f} "
          f"卡玛={m['calmar']:.2f} 达标={'✅' if m['hit'] else '❌'}", flush=True)
    print(f"  成本: 年均换手={result.detail['turnover'].mean()*252:.1f}x "
          f"年均成本拖累={result.detail['cost'].mean()*252:.2%}", flush=True)
    yearly = result.yearly_returns
    print("  分年度:", " ".join(f"{y}:{r:+.0%}" for y, r in yearly.items()), flush=True)
    return result


def main():
    for label, start in [
        ("① 2018-2026 (真实成本·data_lake)", "2018-01-01"),
        ("② 2010-2026 (压力测试·含2015股灾/2017小盘崩盘)", "2010-01-01"),
    ]:
        run_backtest(label, start)


if __name__ == "__main__":
    main()
