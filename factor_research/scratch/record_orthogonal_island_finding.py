"""一次性:把独立数据族隔离岛(股东行为+资金流)筛选结果存进 research_ledger。

读 orthogonal_island_screen.json + orthogonal_island_largecap_screen.json,
写一条 ResearchRunRecord,避免下次重新发现同一条线索。
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_ledger.ledger import ResearchRunRecord, record_research_run

NEW_FACTORS = ("holder_count_chg", "holdertrade_net", "large_order_net_ratio")


def main():
    s1 = json.loads((ROOT / "scratch" / "orthogonal_island_screen.json").read_text())
    s2 = json.loads((ROOT / "scratch" / "orthogonal_island_largecap_screen.json").read_text())

    fullmarket = {
        r["name"]: {
            "L0_sharpe": r["L0_sharpe"], "ic_mean": r["ic_mean"], "ic_t": r["ic_t"],
            "corr_vs_illiq": s1["orthogonality_vs_price_volume_cluster"].get(r["name"], {}).get("illiq_amihud20"),
            "corr_vs_size": s1["orthogonality_vs_price_volume_cluster"].get(r["name"], {}).get("size_neg_adv"),
        }
        for r in s1["factors"] if r["name"] in NEW_FACTORS
    }
    largecap = {
        f"{r['name']}@u{r['universe']}": {
            "L0_sharpe": r["L0_sharpe"], "ic_mean": r["ic_mean"], "ic_ir": r["ic_ir"], "n_ic": r["n_ic"],
        }
        for r in s2["results"]
    }

    notes = (
        "全市场 top25 多头下三者都不是 real_alpha(L0夏普<0.8),且与 illiquidity/size 簇相关 0.66-0.83"
        "(怀疑是全市场 top-N-by-rank 选股本身的小盘漏斗效应,不是数据缺信息)。收窄到大中盘"
        "(u800/u300 ADV)重测后,独立IC 反而走强(holder_count_chg 0.021→0.028→0.042;"
        "holdertrade_net 0.008→0.018→0.030;u300 处 IC_IR 仍偏低 0.14-0.40),但 top25 集中持仓的"
        "组合夏普仍弱/为负——说明信息可能是真实的,但分散在横截面上,没有集中到 top25 多头能吃到的尾部。"
        "下一步建议:在不改变样本/口径/成本前提下,试 top50-100 更宽持仓或多空结构再判断,"
        "而非进一步提高集中度;不要重复本轮已验证过的 top25 全市场/u800/u300 多头路径。"
    )

    rec = ResearchRunRecord(
        script="scripts/research/orthogonal_island_screen.py + orthogonal_island_largecap_screen.py",
        hypothesis=(
            "股东行为(holder_count_chg户数变化/holdertrade_net高管增减持)+ 资金流"
            "(large_order_net_ratio大单净占比)是与价量簇(illiquidity/size)正交的独立 alpha 来源"
            "(LOOP_ENGINEERING.md #5 独立数据族隔离岛)。数据(holdernumber/holdertrade/moneyflow)"
            "已全量入库,新增 factors/shareholder.py + factors/capital_flow.py 并接入 autoresearch DSL"
            "(factors/autoresearch_dsl.py::_FACTOR_CALLS)。"
        ),
        data_vintage={
            "window": s1.get("window"), "universes_tested": ["全市场(top25 by rank)", 800, 300],
            "holdout_boundary": "2025-01-01(全程未触碰,§5.2)",
        },
        metrics={"fullmarket_top25": fullmarket, "largecap_top25_by_universe": largecap},
        verdict="PENDING_REVIEW",
        artifact_paths=[
            "factor_research/factors/shareholder.py", "factor_research/factors/capital_flow.py",
            "factor_research/scripts/research/orthogonal_island_screen.py",
            "factor_research/scripts/research/orthogonal_island_largecap_screen.py",
            "factor_research/scratch/orthogonal_island_screen.json",
            "factor_research/scratch/orthogonal_island_largecap_screen.json",
        ],
        next_action="HUMAN_REVIEW",
        source="claude_session",
        notes=notes,
    )
    view = record_research_run(rec)
    print(json.dumps(view, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
