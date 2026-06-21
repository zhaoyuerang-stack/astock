"""一次性:把修复引擎后,illiquidity 之外4家族7个版本的衰减检查结果存进 research_ledger。

发现:hq-momentum-hedged、large-cap-growth-hedged(对冲组合)两个家族的多版本
decay_check 判 decayed=True(滚动3年夏普<0.5,LOOP_ENGINEERING §5.4 机械触发退役复核),
长历史版本回撤 -85.9%~-95.9%、多年滚动夏普为负——不是统计证据薄弱,是真衰减/可能从未真正起效。
size-earnings、small-cap-size 两个家族健康,未触发衰减,small-cap-size v2.0 回撤(-17.7%)
甚至在单策略入册线(<20%)以内。
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
from governance.decay import decay_check, rolling_3y_sharpe
from research_ledger.ledger import ResearchRunRecord, record_research_run

FILES = [
    ("hq-momentum-hedged", "v1.0"), ("hq-momentum-hedged", "v1.0-full"),
    ("large-cap-growth-hedged", "v1.0"), ("large-cap-growth-hedged", "v1.1"),
    ("large-cap-growth-hedged", "v1.1-full"),
    ("size-earnings", "v1.0"), ("small-cap-size", "v2.0"),
]


def main():
    metrics = {}
    for fam, ver in FILES:
        s = pd.read_csv(f"data_lake/version_returns/{fam}__{ver}.csv", index_col=0)["ret"]
        s.index = pd.to_datetime(s.index)
        s = s.dropna()
        dc = decay_check(s)
        nav = (1 + s).cumprod()
        dd = nav / nav.cummax() - 1
        metrics[f"{fam}/{ver}"] = {
            "decayed": dc["decayed"], "rolling_3y_sharpe_latest": dc["rolling_3y_sharpe_latest"],
            "reasons": dc["reasons"], "maxdd": round(float(dd.min()), 4),
            "n_days": len(s), "date_range": f"{s.index.min().date()}~{s.index.max().date()}",
        }

    notes = (
        "用引擎修复(5ebcdde7c)后重新持久化的收益序列跑 governance.decay.decay_check:"
        "hq-momentum-hedged(v1.0/v1.0-full)与 large-cap-growth-hedged(v1.0/v1.1/v1.1-full,"
        "v1.0短历史例外未触发)均 decayed=True——滚动3年夏普<0.5,长历史版本(v1.0-full/"
        "v1.1-full)滚动夏普从2018年起连续7年为负,回撤-85.2%~-95.9%,这是 LOOP_ENGINEERING "
        "§5.4 设计的机械退役复核触发条件,不是统计证据薄弱的问题——这两个对冲组合家族大概率"
        "从未真正起效或早已失效。size-earnings(v1.0)与 small-cap-size(v2.0)未触发衰减,"
        "滚动夏普持续健康(0.4~2.0区间);small-cap-size v2.0 回撤-17.7%甚至在单策略入册线"
        "(<20%)以内,是当前registry里唯一一个全历史回撤达标的版本。"
        "与 illiquidity 家族对比(同batch查过,未decay但回撤超线):五个家族健康度排序大致"
        "= small-cap-size > size-earnings > illiquidity > large-cap-growth-hedged ≈ "
        "hq-momentum-hedged(后两者应走退役复核,非仅'统计不显著')。"
    )

    rec = ResearchRunRecord(
        script="governance/decay.py::decay_check (引擎修复后批量复核)",
        hypothesis="illiquidity 之外4家族7个版本,在修复后引擎的真实收益序列上是否触发衰减信号。",
        data_vintage={"engine_fix_commit": "5ebcdde7c", "reaudit_at": "2026-06-21"},
        metrics=metrics,
        verdict="REFUTED",
        artifact_paths=[f"factor_research/data_lake/version_returns/{f}__{v}.csv" for f, v in FILES],
        next_action="RETIRE_REVIEW",
        source="claude_session",
        notes=notes,
    )
    view = record_research_run(rec)
    print(json.dumps(view, ensure_ascii=False, indent=2)[:600])


if __name__ == "__main__":
    main()
