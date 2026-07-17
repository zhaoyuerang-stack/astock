#!/usr/bin/env python3
"""R-COST-001 守卫：钉死 CostModel 三费率默认值(hash-pin)。

背景:holdout.start 有 EXPECTED_BOUNDARY_HASH 机械锁(改动即 exit 1,强制走 ADR);
但 core.engine.CostModel 的 buy_cost/sell_cost/financing_rate 此前只有
test_cost_single_source 的"单一来源"比对——全部对着 CostModel() 自适应,
下调费率仍全绿。这是「禁止为达标临时下调滑点/佣金」唯一没有机械强制的部分。

范式照抄 check_holdout_compliance.py 的 boundary pin:
  sha256(canonical JSON, sort_keys) vs 钉死的 EXPECTED_COST_HASH。
改费率须先记 DECISIONS(ADR)并同步四处(见 docs/cost_model.md §4)再更新本 pin。

检测函数可注入 dict/dataclass(便于 fixture 对抗测试);默认读真实 CostModel()。
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]  # factor_research/

# ── 钉死值:与 core.engine.CostModel 默认字段一一对应 ──
# 变更路径:DECISIONS ADR → 改 CostModel + cost_model.md + 受影响报告 → 更新本 pin
EXPECTED_COST = {
    "buy_cost": 0.00225,
    "sell_cost": 0.00275,
    "financing_rate": 0.065,
}
# sha256(json.dumps(EXPECTED_COST, sort_keys=True, separators=(",", ":")))
EXPECTED_COST_HASH = "40f40fbaefebb10e38b6ccc37e39c77573ebbf0bb941458d745c1645fdbaf43b"

_RATE_KEYS = ("buy_cost", "sell_cost", "financing_rate")


def cost_snapshot(cost: Any | None = None) -> dict[str, float]:
    """从 CostModel / Mapping / 可属性访问对象提取三费率。

    ``cost=None`` 时 import 并实例化真实 ``CostModel()``(守卫主路径)。
    测试可注入 dict 或 SimpleNamespace/dataclass 做对抗。
    """
    if cost is None:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from core.engine import CostModel  # noqa: WPS433 — 延迟 import 避免守卫 import 副作用

        cost = CostModel()
    if isinstance(cost, Mapping):
        return {k: float(cost[k]) for k in _RATE_KEYS}
    return {k: float(getattr(cost, k)) for k in _RATE_KEYS}


def canonical_cost_json(snapshot: Mapping[str, float]) -> str:
    """稳定序列化:sort_keys + 无空格,保证 hash 可复现。"""
    payload = {k: float(snapshot[k]) for k in sorted(_RATE_KEYS)}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def cost_hash(snapshot: Mapping[str, float]) -> str:
    return hashlib.sha256(canonical_cost_json(snapshot).encode("utf-8")).hexdigest()


def check_cost_pin(cost: Any | None = None) -> list[str]:
    """比对三费率 hash 与钉死值。返回违规消息列表(空 = 通过)。

    可注入 ``cost``(dict/dataclass/CostModel)便于 fixture;默认读真实 CostModel()。
    """
    snap = cost_snapshot(cost)
    h = cost_hash(snap)
    if h == EXPECTED_COST_HASH:
        return []
    return [
        "CostModel 默认费率被改动(R-COST-001 hash-pin 失败):\n"
        f"  当前: {snap} (hash {h[:12]}…)\n"
        f"  钉死: {EXPECTED_COST} (hash {EXPECTED_COST_HASH[:12]}…)\n"
        "改费率须先记 DECISIONS(ADR)并同步四处"
        "(见 factor_research/docs/cost_model.md §4)再更新本 pin"
        f"(EXPECTED_COST / EXPECTED_COST_HASH in {Path(__file__).name})。"
    ]


def main() -> int:
    errors = check_cost_pin()
    if errors:
        for msg in errors:
            print(f"❌ {msg}", file=sys.stderr)
        return 1
    snap = cost_snapshot()
    print(
        f"✅ CostModel 费率 hash-pin 通过: "
        f"buy={snap['buy_cost']} sell={snap['sell_cost']} "
        f"fin={snap['financing_rate']} "
        f"(hash {EXPECTED_COST_HASH[:12]}…)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
