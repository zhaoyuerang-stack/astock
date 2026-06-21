"""一次性烟雾测试:确认 holder_count_chg/holdertrade_net/large_order_net_ratio
注册进 factory.autoresearch.registry.ALLOWED_FACTORS 后,岛屿搜索的随机变异/初始化
真能产出并评估使用这些新因子的候选(不只是 DSL 能算,搜索引擎也真的会摸到它们)。

纯变异(use_llm=False),tiny population/generation,< holdout boundary,只看 wiring。
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import random

from factory.autoresearch.islands import run_island_search
from governance.holdout import boundary


def main():
    from strategies.small_cap import load_price_panels

    b = boundary()
    close, volume, amount = load_price_panels("2022-01-01")
    close = close[close.index < b]
    volume = volume[volume.index < b]
    amount = amount[amount.index < b]
    forward_ret = close.shift(-20) / close - 1.0

    res = run_island_search(
        close, volume, amount, forward_ret,
        vintage_id="smoke-test-orthogonal-wiring",
        n_islands=1, generations=2, population=6, elite=1, top_k=3,
        final_stage="l0", seeds=None, rng_seed=123, sample_dates=60,
        novelty_weight=0.0, corr_weight=0.0, turnover_weight=0.0,
    )

    new_factor_names = {"holder_count_chg", "holdertrade_net", "large_order_net_ratio"}
    hit = [c for c in res.champions if any(n in c.expr for n in new_factor_names)]

    print(f"evaluated={res.evaluated}, champions={len(res.champions)}")
    for c in res.champions:
        print(f"   {c.fingerprint}: {c.expr}  icir={c.icir:.3f}")
    if hit:
        print(f"✅ 新因子已被搜索摸到,{len(hit)} 个候选用了它们:")
        for c in hit:
            print(f"   {c.fingerprint}: {c.expr}")
    else:
        print("⚠️ 本次小样本运气没摸到新因子(population 太小是常见原因,不代表没接上)。")
        print("   随机抽样确认 registry 本身可达:")
        rng = random.Random(123)
        from factory.autoresearch.registry import ALLOWED_FACTORS
        draws = [rng.choice(sorted(ALLOWED_FACTORS)) for _ in range(2000)]
        for n in new_factor_names:
            print(f"   {n}: 2000次均匀抽样命中 {draws.count(n)} 次(应≈{2000/len(ALLOWED_FACTORS):.0f})")


if __name__ == "__main__":
    main()
