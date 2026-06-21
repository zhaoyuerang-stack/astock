"""一次性:把 illiquidity 家族在 T+1 fill 引擎修复后的重审结果存进 research_ledger。

背景:core.engine 的 T+1 close fill 统一修复(commit 5ebcdde7c,2026-06-20 21:04)落地前,
illiquidity 家族 5 个版本(v1.0/v1.1/v1.3/v3.0/v3.1)的 9-Gate 审计 + 持久化收益序列
(data_lake/version_returns/illiquidity__*.csv)都是 2026-06-19 用旧引擎跑的,系统性
低估了回撤、高估了夏普(look-ahead 修复前后同一组合差异:v3.1 maxdd -14.7%→-29.3%)。
本记录是修复后用新引擎全员重审 + lineage_pbo 重算 PBO 的结果。
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
import strategy_registry

VERSIONS = ["v1.0", "v1.1", "v1.3", "v3.0", "v3.1", "clean-v1"]


def main():
    data = strategy_registry._load()
    fam = next(f for f in data["families"] if f["id"] == "illiquidity")
    metrics = {}
    for v in fam["versions"]:
        if v["version"] in VERSIONS:
            ng = v.get("nine_gate") or {}
            metrics[v["version"]] = {
                "passed_all": ng.get("passed_all"), "dsr_p": ng.get("dsr_p"),
                "gate4_verdict": ng.get("gate4_verdict"), "gate7_verdict": ng.get("gate7_verdict"),
                "pbo": ng.get("pbo"), "corr_to_parent": ng.get("corr_to_parent"),
                "corr_parent_version": ng.get("corr_parent_version"),
            }

    notes = (
        "根因:core.engine T+1 close fill 统一修复(5ebcdde7c,2026-06-20 21:04)落地前,"
        "illiquidity 家族 5 个版本(v1.0/v1.1/v1.3/v3.0/v3.1)的 9-Gate 持久化收益序列"
        "(2026-06-19 跑的)用的是修复前的旧引擎,系统性低估风险——v3.1 逐日比对显示从"
        "第一天就有差异,maxdd 从旧序列的 -14.7% 修正为新序列的 -29.3%(真实回撤发生在"
        "2019-2020 COVID 崩盘段,旧序列错误定位到 2018年末)。用新引擎对全部5个legacy版本"
        "重跑 9-Gate(n_trials=6,与原审计一致)+ clean-v1(本就是新引擎跑的)后:"
        "六个版本 passed_all 全部 False,Gate4(DSR不显著)/Gate5(回撤超-20%线,v1.0/v1.1/v1.3"
        "甚至到-41%~-42%,无veto/band风控的早期版本最差)/Gate6(成本衰减87%~110%,接近或"
        "超过净alpha)三道独立检验全部不过。lineage_pbo 用六个版本干净序列重算家族PBO=0.92"
        "(此前混用新旧序列算出0.76),v1.0与clean-v1 daily return corr=1.0(数学上同一序列,"
        "仅leverage标量差异,证实clean-v1并非独立配方)。衰减监控(decay_check)在新序列上"
        "仍判 v3.1 未衰减(滚动3年夏普2.20,逐年走高),即alpha本身没有变差——是修复前的"
        "数据一直在隐藏真实风险,不是策略突然失效,也不是闸门变严。"
        "未决:生产部署清单(deployments/production.json)仍指向 illiquidity/v3.1,"
        "而 decide_nine_gate() 严格闸(passed_all 必须True)从未真正批准过这条腿——"
        "这是部署治理决策,留给人确认,本记录不做处置。"
    )

    rec = ResearchRunRecord(
        script="scripts/research/run_nine_gates_all.py(全员重审) + lineage_pbo.py",
        hypothesis=(
            "illiquidity 家族 v1.0/v1.1/v1.3/v3.0/v3.1 的既有9-Gate审计与持久化收益序列"
            "受 core.engine T+1 fill 旧bug影响系统性失真,修复后(5ebcdde7c)需重新审计才能"
            "得到诚实结论。"
        ),
        data_vintage={
            "engine_fix_commit": "5ebcdde7c", "engine_fix_at": "2026-06-20T21:04",
            "stale_audit_at": "2026-06-19T03:50", "reaudit_at": "2026-06-21",
            "n_trials": 6,
        },
        metrics=metrics,
        verdict="FAILED",
        artifact_paths=[
            "factor_research/data_lake/version_returns/illiquidity__v1.0.csv",
            "factor_research/data_lake/version_returns/illiquidity__v1.1.csv",
            "factor_research/data_lake/version_returns/illiquidity__v1.3.csv",
            "factor_research/data_lake/version_returns/illiquidity__v3.0.csv",
            "factor_research/data_lake/version_returns/illiquidity__v3.1.csv",
            "factor_research/reports/research/illiquidity_9_gates_report.md",
        ],
        next_action="HUMAN_REVIEW",
        source="claude_session",
        notes=notes,
    )
    view = record_research_run(rec)
    print(json.dumps(view, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
