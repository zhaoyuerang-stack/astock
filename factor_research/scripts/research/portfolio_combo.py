"""组合路线评估:small-cap-size baseline + 低相关分散件 sleeve,按权重网格三段真实成本审计。

目标:验证"组合路线"——不强求 sleeve 单独达标,只要它与 baseline 低相关,
小权重混入能否改善组合的回撤/夏普(尤其样本外)。

用法(cwd=factor_research):
    /usr/bin/python3 -m scripts.research.portfolio_combo
"""
import os
import sys
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from core.backtest import metrics                              # noqa: E402
from factory.evaluator import prepare_context, run_candidate_returns  # noqa: E402
from factory.search_space import Candidate                    # noqa: E402

PERIODS = {"样本内2018": "2018-01-01", "样本外2023": "2023-01-01", "压力2010": "2010-01-01"}
WEIGHTS = [0.0, 0.10, 0.15, 0.20, 0.25, 0.30]

# 低相关分散件:timing sweep 中 none 择时 corr 最低的 fundamental sleeve(~0.46)
SLEEVE = replace(
    Candidate(
        "fund-epsyield-bp-cfo", "sleeve",
        "fund_eps_yield_pctile+fund_bp_value+fund_cfo_ind_rank",
        ["fund_eps_yield_pctile", "fund_bp_value", "fund_cfo_ind_rank"],
        [0.2597, 0.3438, 0.3965],
        top_n=25, rebalance_days=60, leverage=1.0,
    ),
    timing="none",
)


def run():
    for label, start in PERIODS.items():
        close, amount, library, baseline_ret = prepare_context(start)
        sleeve_ret, _ = run_candidate_returns(SLEEVE, close, amount, library, start)
        idx = baseline_ret.index.intersection(sleeve_ret.index)
        b = baseline_ret.reindex(idx).fillna(0.0)
        s = sleeve_ret.reindex(idx).fillna(0.0)
        corr = float(b.corr(s))
        print(f"\n=== {label} ({start}~) | baseline=small-cap-size · sleeve corr={corr:.2f} ===")
        print(f"{'w_sleeve':>9} {'年化':>8} {'回撤':>8} {'夏普':>7} {'卡玛':>7}")
        for w in WEIGHTS:
            combo = (1.0 - w) * b + w * s
            m = metrics(combo)
            tag = "  <- 纯 baseline" if w == 0 else ""
            print(f"{w:>8.0%} {m['annual']:>8.1%} {m['maxdd']:>8.1%} "
                  f"{m['sharpe']:>7.2f} {m.get('calmar', 0):>7.2f}{tag}")


if __name__ == "__main__":
    run()
