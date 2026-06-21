#!/usr/bin/env python3
"""在册策略定时衰减复测(LOOP_ENGINEERING §5.4)。

alpha 默认会失效 → 主动复测在册 ACTIVE 策略,触发 decay_signal 的标记待退役复核
(非删除,承铁律9)。建议周度 cron / 接 scheduled 维护。只读 + 落报告,不写台账。

decay_signal(governance/decay.py):滚动3年夏普 <0.5 / Rank IC 连续4季 <0。
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from governance.decay import decay_check

REPORT = ROOT / "data_lake" / "governance" / "decay_monitor.jsonl"
LATEST = ROOT / "reports" / "decay_status.json"
CHINA_TZ = ZoneInfo("Asia/Shanghai")


def main():
    print("=" * 72)
    print("  在册策略衰减复测(§5.4)")
    print("=" * 72)
    try:
        from portfolio.strategy_runners import run_active
    except Exception as e:
        print(f"❌ 无法加载在册组合: {e}", file=sys.stderr)
        sys.exit(1)

    from governance.holdout import current_data_fingerprint
    from runtime.production_readiness import current_deployment_identity

    identity = current_deployment_identity()
    active = run_active(start="2018-01-01")
    if not active:
        print("无 ACTIVE 在册策略,跳过。")
        return

    rows = []
    decayed = []
    for name, ret in active.items():
        res = decay_check(ret)
        rows.append({"strategy": name, **res})
        tag = "⚠️衰减" if res["decayed"] else "健康"
        sh = res.get("rolling_3y_sharpe_latest")
        print(f"  {name:28} 滚动3年夏普={sh}  {tag}  {res['action']}")
        if res["decayed"]:
            decayed.append((name, res["reasons"]))

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
    latest_date = max(
        (str(ret.dropna().index[-1].date()) for ret in active.values() if len(ret.dropna())),
        default="",
    )
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
