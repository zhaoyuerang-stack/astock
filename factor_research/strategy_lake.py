"""
策略迁移到 data_lake 加载层复测 —— 打假验证
统一使用 core.backtest: data_lake 口径 + 真实换手成本 + 融资成本。

验证：①2018-2026对比旧40.4%(看active过滤/幸存者偏差的影响)
      ②2010-2026压力测试(含2015股灾/2017小盘崩盘)
"""
import warnings; warnings.filterwarnings("ignore")
import os
from pathlib import Path
os.chdir(Path(__file__).parent)
from core.backtest import StrategyConfig, metrics, run_small_cap_strategy, yearly_returns


def run_backtest(label, start):
    print(f"\n{label}", flush=True)
    config = StrategyConfig(start=start)
    result = run_small_cap_strategy(config)
    close = result["close"]
    strat = result["returns"]
    detail = result["detail"]
    m = metrics(strat)
    print(f"  载入 {close.shape[1]}只 × {close.shape[0]}日 "
          f"[{close.index[0].date()}~{close.index[-1].date()}]", flush=True)
    print(f"  → 年化={m['annual']:+.2%} 回撤={m['maxdd']:.2%} 夏普={m['sharpe']:.2f} "
          f"卡玛={m['calmar']:.2f} 达标={'✅' if m['hit'] else '❌'}", flush=True)
    print(f"  成本: 年均换手={detail['turnover'].mean()*252:.1f}x "
          f"年均成本拖累={detail['cost'].mean()*252:.2%}", flush=True)
    yearly = yearly_returns(strat)
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
