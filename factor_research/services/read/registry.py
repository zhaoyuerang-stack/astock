"""只读包住 strategy_registry —— 台账 family/version → StrategyView。

只读 ``_load()``;绝不调 register/_save(台账唯一写入口仍是 strategy_registry)。
"""
from __future__ import annotations

from contracts.views import StrategyView


def list_strategies() -> list[StrategyView]:
    import strategy_registry  # 受控接缝:services 可碰台账

    data = strategy_registry._load()
    out: list[StrategyView] = []
    for fam in data.get("families", []):
        for v in fam.get("versions", []):
            out.append(StrategyView(
                strategy_id=f"{fam['id']}/{v.get('version', '')}",
                family=fam["id"],
                family_name=fam.get("name", ""),
                family_status=fam.get("status", ""),
                version=v.get("version", ""),
                status=v.get("status", ""),
                hypothesis=fam.get("hypothesis", ""),
                regime=fam.get("regime", ""),
                desc=v.get("desc", ""),
                data_scope=v.get("data_scope", ""),
                metrics=v.get("metrics", {}) or {},
                config=v.get("config", {}) or {},
                notes=v.get("notes", ""),
            ))
    return out
