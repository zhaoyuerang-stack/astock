"""TOC 机制证伪:右尾 PnL 到底落在「去 DSP 化光通信/CPO 链」还是泛双创?

逻辑链断言(logic_chains/ai_compute_toc_bottleneck.json):钱来自 DSP 功耗墙倒逼
LPO/CPO,核心低功耗光器件链毛利爆发。可证伪预测:驱动右尾的暴击票应集中在
光通信/光模块链(申万「通信/电子」内的光器件),而非散在无关双创行业(医药/军工/新能源)。

口径:A1A2 臂(右尾最优),OOS 2023-06~2026(alpha 所在),逐票累加 weight*前向收益 = PnL 归因。
判据:
  - 若 通信+电子 占正 PnL 远高于其在持仓中的票数占比 → 机制方向成立,升级概念精确口径
  - 若散在无关行业 / 通信电子不超配 → 机制被证伪(因子=泛盈利加速,CPO 是事后叙事)
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

from core.engine import PricePanel
from strategies.ai_compute_toc import (
    StrategyConfig, load_price_panels, build_factor, build_timing,
)
from lake.load_lake import load_raw_close, load_fina_indicator_panel

# 复用实验里的 A1A2 weights 构造
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "research"))
from toc_right_tail_experiment import build_weights  # noqa: E402

WIN_START = pd.Timestamp("2023-06-01")


def per_name_attribution(weights_history, close, win_start):
    """逐票累加 weight*前向收益 (持有期前向),返回 name->{contrib, n, best}。"""
    dates = sorted(d for d in weights_history if d >= win_start)
    agg = {}
    for i, d in enumerate(dates):
        if d not in close.index:
            continue
        nxt = dates[i + 1] if i + 1 < len(dates) else close.index[-1]
        idx_nxt = close.index[close.index <= nxt]
        if len(idx_nxt) == 0:
            continue
        p0, p1 = close.loc[d], close.loc[idx_nxt[-1]]
        for name, wt in weights_history[d].items():
            r0, r1 = p0.get(name), p1.get(name)
            if pd.isna(r0) or pd.isna(r1) or r0 <= 0:
                continue
            fwd = float(r1) / float(r0) - 1.0
            a = agg.setdefault(name, {"contrib": 0.0, "n": 0, "best": -9.9})
            a["contrib"] += float(wt) * fwd
            a["n"] += 1
            a["best"] = max(a["best"], fwd)
    return agg


def main():
    cfg = StrategyConfig(start="2010-06-01")
    buf = io.StringIO()
    with redirect_stdout(buf):
        close, volume, amount = load_price_panels("2010-01-01")
        codes = list(close.columns)
        roe_panel = load_fina_indicator_panel(close.index, codes=codes, fields=["roe"])["roe"].shift(1)
        factor = build_factor(close, close.index, accel_diff=cfg.accel_diff)

    sched = build_weights(factor, close, amount, roe_panel, cfg.top_n,
                          cfg.rebalance_days, cfg.roe_threshold,
                          weight_scheme="convex", buffer_mult=2.0)

    agg = per_name_attribution(sched, close, WIN_START)

    # 行业映射(申万一级);code 形如 300xxx.SZ -> 取 6 位
    ind = pd.read_parquet("data_lake/meta/industry.parquet")
    ind["code6"] = ind["ts_code"].str[:6]
    l1 = dict(zip(ind["code6"], ind["industry_l1_name"].str.replace("(申万)", "", regex=False)))
    nm = dict(zip(ind["code6"], ind["name"]))

    def c6(x):
        return str(x).split(".")[0][:6]

    rows = []
    for name, a in agg.items():
        k = c6(name)
        rows.append({
            "code": name, "stock": nm.get(k, "?"), "l1": l1.get(k, "未知"),
            "contrib": a["contrib"], "n": a["n"], "best": a["best"],
        })
    df = pd.DataFrame(rows)

    total = df["contrib"].sum()
    pos = df[df["contrib"] > 0]["contrib"].sum()

    # 行业聚合(按正贡献)
    by_l1 = (df.groupby("l1")
               .agg(contrib=("contrib", "sum"), n_names=("code", "nunique"))
               .sort_values("contrib", ascending=False))
    by_l1["pnl_share"] = by_l1["contrib"] / total
    by_l1["name_share"] = by_l1["n_names"] / df["code"].nunique()

    tech = ["通信", "电子", "计算机"]
    tech_pnl = by_l1.loc[by_l1.index.isin(tech), "contrib"].sum()
    tech_names = by_l1.loc[by_l1.index.isin(tech), "n_names"].sum()

    report = {
        "window": f"{WIN_START.date()}~end",
        "n_unique_names": int(df["code"].nunique()),
        "total_contrib": float(total),
        "pos_contrib": float(pos),
        "tech_pnl_share_of_total": float(tech_pnl / total) if total else None,
        "tech_name_share": float(tech_names / df["code"].nunique()),
        "by_l1": by_l1.reset_index().to_dict("records"),
        "top15_winners": df.sort_values("contrib", ascending=False)
                           .head(15)[["stock", "l1", "contrib", "n", "best"]]
                           .to_dict("records"),
    }
    with open("scratch/toc_mechanism_falsify.json", "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)

    print(f"OOS {report['window']}  唯一持仓 {report['n_unique_names']} 票\n")
    print("=== 行业 PnL 归因(申万一级,按贡献排序) ===")
    print(f"{'行业':8} {'PnL占比':>9} {'票数占比':>9} {'票数':>5}")
    for r in report["by_l1"]:
        print(f"{r['l1']:8} {r['pnl_share']:+9.1%} {r['name_share']:9.1%} {r['n_names']:5d}")
    print(f"\n科技硬件(通信+电子+计算机): PnL {report['tech_pnl_share_of_total']:+.1%} | 票数 {report['tech_name_share']:.1%}")
    print("\n=== Top15 赢家(贡献) ===")
    print(f"{'股票':10} {'行业':8} {'贡献':>9} {'期数':>4} {'最佳期':>8}")
    for w in report["top15_winners"]:
        print(f"{w['stock']:10} {w['l1']:8} {w['contrib']:+9.4f} {w['n']:4d} {w['best']:+8.1%}")


if __name__ == "__main__":
    main()
