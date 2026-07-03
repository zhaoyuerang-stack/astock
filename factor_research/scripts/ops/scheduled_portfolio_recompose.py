#!/usr/bin/env python3
"""周度组合再构成(WS-D,ADR-034 后续):多策略组合的定期重排提案。

06-30 的复合组合(40/40/20)证明了正交对冲价值,但那是一次性人工实验——
组合层此前没有定时任务,「多策略组合」不会随台账/衰减状态自动重估。本脚本:

  读:strategy_registry 在册版本 + data_lake/version_returns/<family>__<version>.csv
     (run_nine_gates_all.py --persist 产物,与 decay_monitor 同源同口径)
  算:portfolio.recompose(确定性内核:多目标排名 + 非冗余腿静态 inverse-vol 提案
     + 组合自身 decay_check;口径 RANKING_VERSION 锚定,R-OBJECTIVE-001)
  写:reports/research/portfolio_recompose.json(latest)+ 按日期归档(R-PROD-001:
     排名由后端确定性代码产出并**持久化**,不得只在前端瞬时算)

不写台账、不改部署、不自动开 paper 账户——纯 advisory,决策收件箱透出后由人裁决
(LOOP §6)。挂载:scheduled_weekly_maintenance(研究旁路,失败不标 failed)。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

VERSION_RETURNS = ROOT / "data_lake" / "version_returns"
LATEST = ROOT / "reports" / "research" / "portfolio_recompose.json"
ARCHIVE_DIR = ROOT / "reports" / "research" / "portfolio_recompose"
CHINA_TZ = ZoneInfo("Asia/Shanghai")


def load_registered_returns() -> tuple[dict, list[str]]:
    """在册版本 → 日收益序列(与 decay_monitor 同源:9-Gate --persist 的 csv)。

    返回 (returns, missing):缺收益序列的在册版本如实列出,不静默跳过。
    """
    import strategy_registry

    data = strategy_registry._load()
    returns: dict[str, pd.Series] = {}
    missing: list[str] = []
    for fam in data.get("families", []):
        for v in fam.get("versions", []):
            if v.get("status") != "在册":
                continue
            name = f"{fam['id']}.{v['version']}"
            fp = VERSION_RETURNS / f"{fam['id']}__{v['version']}.csv"
            if not fp.exists():
                missing.append(name)
                continue
            ret = pd.read_csv(fp, index_col=0)["ret"]
            ret.index = pd.to_datetime(ret.index)
            ret = ret.dropna()
            if len(ret):
                returns[name] = ret
            else:
                missing.append(name)
    return returns, missing


def main() -> int:
    print("=" * 72)
    print("  周度组合再构成(WS-D:多策略组合定期重排,advisory)")
    print("=" * 72)

    from portfolio.recompose import recompose

    returns, missing = load_registered_returns()
    print(f"  在册腿收益序列:{len(returns)} 条可用,{len(missing)} 条缺失")
    for name in missing:
        print(f"  [missing] {name}: 无 version_returns 序列,需先跑一次 9-Gate --persist")

    result = recompose(returns)
    result["generated_at"] = datetime.now(CHINA_TZ).isoformat(timespec="seconds")
    result["universe"] = "strategy_registry status=在册(SHADOW/候选不入池,加入是人决策)"
    result["missing_returns"] = missing

    LATEST.parent.mkdir(parents=True, exist_ok=True)
    LATEST.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=float),
                      encoding="utf-8")
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    archive = ARCHIVE_DIR / f"{datetime.now(CHINA_TZ).date().isoformat()}.json"
    archive.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=float),
                       encoding="utf-8")

    prop = result["proposal"]
    print("-" * 72)
    if prop.get("status") == "ok":
        w = ", ".join(f"{k}={v}" for k, v in prop["weights"].items())
        cm = prop["composite_metrics"]
        print(f"  提案权重:{w}")
        print(f"  组合体检:sharpe={cm.get('sharpe')} maxdd={cm.get('maxdd')} "
              f"decayed={prop['composite_decay']['decayed']}")
        print(f"  paper 名单(top-N,R-PROD-001):{result['paper_candidates']}")
    else:
        print(f"  {prop.get('note', '空提案')}")
    print(f"  已持久化:{LATEST}(归档 {archive.name})")
    print("  ⚠️ advisory:权重生效/开 paper/退役由人经 canonical 入口执行(LOOP §6)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
