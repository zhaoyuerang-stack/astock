"""A 实验 DSR 多重检验:把网格 + 结构臂的真实搜索规模计入,看 A1A2 惩罚后是否仍显著。

复用 canonical core.analysis.walk_forward.deflated_sharpe(López de Prado & Bailey 2014)。
不挑单一魔数 n_trials(那会自欺),而是画 DSR p 随 trial 数的衰减曲线,看显著性在哪里塌。

trial 数口径:
  - grid_search_results.csv = 321 行参数网格(rebalance/top_n/roe/accel_diff)
  - 结构臂 = {equal,convex} × {buffer,no-buffer} = 4
  - 诚实上界 ≈ 321 × 4 ≈ 1284;台账旧值 3 = 严重低估
"""
import os
import sys
import json
import csv
from pathlib import Path

PROJECT_ROOT = Path("/Users/kiki/astcok/factor_research")
os.chdir(PROJECT_ROOT)
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.analysis.walk_forward import deflated_sharpe

EXP = json.load(open("scratch/toc_right_tail_experiment.json"))

# 真实网格规模
with open("scratch/grid_search_results.csv") as f:
    n_grid = sum(1 for _ in csv.reader(f)) - 1  # 去表头

N_STRUCTURAL = 4  # {equal,convex}×{buffer,no-buffer}
TRIAL_GRID = [1, 3, 50, n_grid, n_grid * N_STRUCTURAL]
WINDOWS = ["stress_2010_2026", "oos_2023_2026"]  # 全样本(最不挑) + OOS(最亮)


def dsr_p(arm, win, n_trials):
    p = EXP[arm]["windows"][win]["portfolio"]
    rep = deflated_sharpe(
        observed_sr=p["sharpe"],
        n_trials=n_trials,
        n_periods=p["n"],
        skew=p["skew"],
        kurt=p["kurtosis_excess"] + 3.0,  # canonical 要原始峰度(正态=3)
        annualized=True,
    )
    return rep["p_value"], rep["dsr"], rep["significant_05"]


def main():
    print(f"真实网格 n_grid={n_grid}, 结构臂={N_STRUCTURAL}, 诚实上界 n_trials≈{n_grid*N_STRUCTURAL}\n")
    for win in WINDOWS:
        print(f"=== 窗口 {win} ===")
        hdr = f"{'arm':10} {'sharpe':>7} " + " ".join(f"p@{t}".rjust(9) for t in TRIAL_GRID)
        print(hdr)
        print("-" * len(hdr))
        for arm in EXP:
            sh = EXP[arm]["windows"][win]["portfolio"]["sharpe"]
            cells = []
            for t in TRIAL_GRID:
                p, _, sig = dsr_p(arm, win, t)
                mark = "*" if sig else " "
                cells.append(f"{p:8.3f}{mark}")
            print(f"{arm:10} {sh:7.2f} " + " ".join(cells))
        print()
    print("* = DSR p<0.05(惩罚后仍显著)。p 越靠 0.5 = 越像运气。")


if __name__ == "__main__":
    main()
