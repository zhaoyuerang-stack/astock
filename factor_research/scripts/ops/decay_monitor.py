#!/usr/bin/env python3
"""在册策略定时衰减复测(LOOP_ENGINEERING §5.4)。

alpha 默认会失效 → 主动复测全部「在册」版本(strategy_registry,不止当前部署的那一条
腿——`run_active()` 只覆盖 deployments/production.json 的 legs,RESEARCH_STRATEGY_CATALOG
里压根没有 hq-momentum-hedged/large-cap-growth-hedged 等家族的 runner,范围天生不够),
触发 decay_signal 的标记待退役复核(非删除,承铁律9)。建议周度 cron / 接 scheduled 维护。
落报告 + 经 strategy_registry.attach_decay_check() 写回每个版本的 decay_check 字段
(供 Web /factors 展示实测衰减状态);不改 status/admission,是否退役仍走 workflow 人工决策。

收益序列读 data_lake/version_returns/<family>__<version>.csv(run_nine_gates_all.py
--persist 写的)而非现场回测——新鲜度取决于该版本上次审计时间,不是每次现算;
--audit-stale 在同一 cron 序列里紧邻跑,正常不会长期陈旧。

decay_signal(governance/decay.py):滚动3年夏普 <0.5 / Rank IC 连续4季 <0。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from governance.decay import decay_check

REPORT = ROOT / "data_lake" / "governance" / "decay_monitor.jsonl"
LATEST = ROOT / "reports" / "decay_status.json"
VERSION_RETURNS = ROOT / "data_lake" / "version_returns"
CHINA_TZ = ZoneInfo("Asia/Shanghai")


def main():
    print("=" * 72)
    print("  在册策略衰减复测(§5.4)")
    print("=" * 72)

    import strategy_registry
    from governance.holdout import current_data_fingerprint
    from runtime.production_readiness import current_deployment_identity

    try:
        identity = current_deployment_identity()
    except Exception as e:
        identity = {"deployment_identity_error": str(e)[:200]}
        print(f"  [identity] current_deployment_identity() 失败(不阻断报告): {e}", file=sys.stderr)

    data = strategy_registry._load()
    rows = []
    decayed = []
    latest_dates = []
    for fam in data.get("families", []):
        family = fam["id"]
        for v in fam.get("versions", []):
            if v.get("status") != "在册":
                continue
            version = v["version"]
            name = f"{family}.{version}"
            fp = VERSION_RETURNS / f"{family}__{version}.csv"
            if not fp.exists():
                print(f"  [skip] {name}: 无收益序列({fp.name}),需先跑一次 9-Gate --persist")
                continue
            ret = pd.read_csv(fp, index_col=0)["ret"]
            ret.index = pd.to_datetime(ret.index)
            ret = ret.dropna()
            if not len(ret):
                continue
            latest_dates.append(ret.index[-1])
            res = decay_check(ret)
            rows.append({"strategy": name, **res})
            tag = "⚠️衰减" if res["decayed"] else "健康"
            sh = res.get("rolling_3y_sharpe_latest")
            print(f"  {name:28} 滚动3年夏普={sh}  {tag}  {res['action']}")
            if res["decayed"]:
                decayed.append((name, res["reasons"]))
            try:
                strategy_registry.attach_decay_check(family, version, res)
            except Exception as e:
                print(f"  [persist] {name} 写台账失败(继续,不阻断报告): {e}", file=sys.stderr)

    if not rows:
        print("无可复测的在册策略(均缺收益序列),跳过。")
        return

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT, "a") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=float) + "\n")

    print("-" * 72)
    if decayed:
        print(f"⚠️ {len(decayed)} 个在册策略触发衰减信号,建议走 workflow 标退役复核:")
        for name, reasons in decayed:
            print(f"   {name}: {'; '.join(reasons)}")
    else:
        print("✅ 全部在册策略健康,无衰减。")
    generated_at = datetime.now(CHINA_TZ).isoformat(timespec="seconds")
    latest_date = str(max(latest_dates).date()) if latest_dates else ""
    envelope = {
        "report_type": "decay",
        "generated_at": generated_at,
        **identity,
        "data_fingerprint": current_data_fingerprint(),
        "as_of_date": latest_date,
        "status": "red" if decayed else "green",
        "strategies": rows,
    }
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(envelope, ensure_ascii=False, indent=2, default=float))
    print(f"明细落 {REPORT.relative_to(ROOT)}")
    print(f"控制面最新状态落 {LATEST.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
