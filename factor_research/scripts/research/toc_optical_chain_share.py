"""光模块/CPO 链精确 PnL 占比(tushare 概念接口无权限 → 透明人工白名单)。

白名单口径声明:
  - tushare 打板专题/概念接口(ths_index/dc_index/concept)对本 token 全部 40203 无权限;
    本地数据湖亦无概念成分。故改用按【公开产业链归属】构造的双创光链白名单,与回测收益无关。
  - 从宽:纳入所有已知双创(30x/688x/301x)光模块/光器件/光芯片/CPO/硅光名,给机制最好机会。
  - 双重核验:另用「票名含『光』且属通信/电子」关键词网兜,两者收敛则结论稳。
  - 策略宇宙仅双创 → 主板光链(光迅002281/亨通600487/长飞601869等)本就不在持仓,无需纳入。

判据:若白名单 PnL 占比 << 71%(科技硬件) → 「泛 AI 硬件 ≠ CPO 链」被精确钉死。
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

import pandas as pd

from strategies.ai_compute_toc import (
    StrategyConfig, load_price_panels, build_factor,
)
from lake.load_lake import load_fina_indicator_panel

sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "research"))
from toc_right_tail_experiment import build_weights          # noqa: E402
from toc_mechanism_falsify import per_name_attribution, WIN_START  # noqa: E402

# 双创光模块/光器件/光芯片/CPO/硅光 产业链(公开归属,与收益无关)
OPTICAL_CHAIN = {
    "300308": "中际旭创(光模块龙头)", "300502": "新易盛(光模块)",
    "300394": "天孚通信(光器件/封装)", "300570": "太辰光(光器件)",
    "301205": "联特科技(光模块)", "300548": "博创科技(光模块/硅光)",
    "300620": "光库科技(光器件/激光)", "688313": "仕佳光子(光芯片/器件)",
    "688498": "源杰科技(光芯片DFB)", "688048": "长光华芯(激光芯片)",
    "300757": "罗博特科(CPO设备)", "300353": "东土科技(工业光网)",
}


def c6(x):
    return str(x).split(".")[0][:6]


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

    ind = pd.read_parquet("data_lake/meta/industry.parquet")
    ind["code6"] = ind["ts_code"].str[:6]
    l1 = dict(zip(ind["code6"], ind["industry_l1_name"].str.replace("(申万)", "", regex=False)))
    nm = dict(zip(ind["code6"], ind["name"]))

    total = sum(a["contrib"] for a in agg.values())

    # A) 人工白名单
    wl_rows, wl_pnl = [], 0.0
    for code, a in agg.items():
        if c6(code) in OPTICAL_CHAIN:
            wl_pnl += a["contrib"]
            wl_rows.append((OPTICAL_CHAIN[c6(code)], a["contrib"], a["best"]))

    # B) 关键词网兜:票名含「光」且属 通信/电子
    kw_pnl, kw_rows = 0.0, []
    for code, a in agg.items():
        k = c6(code)
        nme, sec = nm.get(k, ""), l1.get(k, "")
        if "光" in nme and sec in ("通信", "电子"):
            kw_pnl += a["contrib"]
            kw_rows.append((nme, sec, a["contrib"]))

    report = {
        "total_contrib": float(total),
        "optical_whitelist": {
            "n_in_universe": len(wl_rows),
            "n_whitelist": len(OPTICAL_CHAIN),
            "pnl_share": float(wl_pnl / total) if total else None,
            "names": [{"name": n, "contrib": float(c), "best": float(b)}
                      for n, c, b in sorted(wl_rows, key=lambda x: -x[1])],
        },
        "keyword_optical": {
            "pnl_share": float(kw_pnl / total) if total else None,
            "names": [{"name": n, "sec": s, "contrib": float(c)}
                      for n, s, c in sorted(kw_rows, key=lambda x: -x[2])],
        },
    }
    with open("scratch/toc_optical_chain_share.json", "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=float)

    w = report["optical_whitelist"]
    print(f"=== 光链精确 PnL 占比(OOS 2023-06~end) ===")
    print(f"白名单 {w['n_whitelist']} 名,持仓命中 {w['n_in_universe']} 名 → "
          f"PnL 占比 {w['pnl_share']:+.1%}  (对照:科技硬件 +71.0%)")
    print("命中白名单的光链票贡献:")
    for r in w["names"]:
        print(f"  {r['name']:24} {r['contrib']:+8.4f}  最佳期 {r['best']:+.1%}")
    k = report["keyword_optical"]
    print(f"\n关键词网兜(名含『光』∩通信/电子) PnL 占比 {k['pnl_share']:+.1%}:")
    for r in k["names"]:
        print(f"  {r['name']:10} {r['sec']:6} {r['contrib']:+8.4f}")


if __name__ == "__main__":
    main()
