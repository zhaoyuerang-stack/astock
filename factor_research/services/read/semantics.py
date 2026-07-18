"""语义卡片只读聚合门面 —— 三类实体口径一跳读。

零新存储、零新 schema、零第二真相源。字段一律从 canonical 源 PULL:

* 因子 → ``factors.registry``(``discover()`` + ``FACTOR_REGISTRY``)
* 数据集 → ``data_lake/_manifest.json`` + ``tushare_manifest.json``(json 只读;
  tushare 文件缺失时该源贡献 0 个数据集,文件级 fail-soft)
* 策略 → ``services.read.registry.list_strategies()``(不得绕过直读 json)

未知实体 ``raise KeyError``(fail-closed)。源头缺字段给空值 + 显式 missing,
绝不填充默认口径描述。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from contracts.views import (
    DatasetSemanticsView,
    FactorSemanticsView,
    SemanticInventoryView,
    StrategySemanticsView,
)


ROOT = Path(__file__).resolve().parents[2]
_CORE_MANIFEST = ROOT / "data_lake" / "_manifest.json"
_TUSHARE_MANIFEST = ROOT / "data_lake" / "tushare_manifest.json"


def _load_manifest(path: Path) -> dict[str, Any]:
    """只读 load 一个 manifest;文件不存在返回空 dict(fail-soft,仅用于 tushare)。"""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return {}
    return data


def _dataset_entries() -> dict[str, tuple[str, dict]]:
    """合并 core + tushare 数据集条目。

    返回 ``{name: (source_manifest, entry_dict)}``。
    core 优先;同名不覆盖(core 赢)。跳过 ``_`` 开头元键。
    """
    out: dict[str, tuple[str, dict]] = {}
    core = _load_manifest(_CORE_MANIFEST)
    for name, entry in core.items():
        if str(name).startswith("_"):
            continue
        if isinstance(entry, dict):
            out[str(name)] = ("core", entry)
    tushare = _load_manifest(_TUSHARE_MANIFEST)
    for name, entry in tushare.items():
        if str(name).startswith("_"):
            continue
        key = str(name)
        if key in out:
            continue
        if isinstance(entry, dict):
            out[key] = ("tushare", entry)
    return out


def _dataset_from_entry(name: str, source: str, entry: dict) -> DatasetSemanticsView:
    """从单条 manifest entry 拼卡片;缺键不编造。"""
    contract_missing = "contract" not in entry
    raw_contract = entry.get("contract") if not contract_missing else {}
    contract = raw_contract if isinstance(raw_contract, dict) else {}
    raw_fields = entry.get("fields", [])
    if isinstance(raw_fields, list):
        fields = list(raw_fields)
    elif isinstance(raw_fields, dict):
        # 少数源可能用 dict 描述字段;原样 keys 列表会丢信息,保留为 list of pairs 太重
        # —— 只接受 list;非 list 不编造,退空 list(但 dict 也是真实键,透传为 list(keys)?)
        # 规格字段类型为 list:非 list 给空,不发明字段名。
        fields = []
    else:
        fields = []
    last_check = entry.get("last_check", "")
    if last_check is None:
        last_check = ""
    else:
        last_check = str(last_check)
    path = entry.get("path", "")
    if path is None:
        path = ""
    else:
        path = str(path)
    return DatasetSemanticsView(
        name=name,
        source_manifest=source,
        last_check=last_check,
        fields=fields,
        path=path,
        contract=contract if isinstance(contract, dict) else {},
        contract_missing=contract_missing,
    )


def factor_card(name: str) -> FactorSemanticsView:
    """因子语义卡片。PULL 自 factors.registry:先 discover() 再查 FACTOR_REGISTRY。"""
    from factors.registry import FACTOR_REGISTRY, discover

    discover()
    rec = FACTOR_REGISTRY.get(name)
    if rec is None:
        raise KeyError(name)
    data = list(rec.data) if rec.data is not None else []
    return FactorSemanticsView(
        name=rec.name,
        definition=rec.definition or "",
        params=dict(rec.params or {}),
        data=data,
        input=rec.input or "",
        searchable=bool(rec.searchable),
        evidence=rec.evidence or "",
        source_hash=rec.source_hash or "",
    )


def dataset_card(name: str) -> DatasetSemanticsView:
    """数据集语义卡片。PULL 自 core/tushare manifest(只读 json.load)。"""
    entries = _dataset_entries()
    hit = entries.get(name)
    if hit is None:
        raise KeyError(name)
    source, entry = hit
    return _dataset_from_entry(name, source, entry)


def strategy_card(family: str, version: str | None = None) -> StrategySemanticsView:
    """策略语义卡片。复用 list_strategies();version=None 取该 family 第一个 version。"""
    from services.read.registry import list_strategies

    rows = list_strategies()
    if version is None:
        match = next((r for r in rows if r.family == family), None)
        if match is None:
            raise KeyError(family)
    else:
        strategy_id = f"{family}/{version}"
        match = next((r for r in rows if r.strategy_id == strategy_id), None)
        if match is None:
            raise KeyError(strategy_id)
    nine_gate = match.nine_gate or {}
    nine_gate_present = isinstance(nine_gate, dict) and len(nine_gate) > 0
    return StrategySemanticsView(
        family=match.family,
        version=match.version,
        hypothesis=match.hypothesis or "",
        regime=match.regime or "",
        decay_signal=match.decay_signal or "",
        status=match.status or "",
        nine_gate_present=nine_gate_present,
    )


def list_semantic_entities() -> SemanticInventoryView:
    """三类实体名字清单 + 计数。"""
    from factors.registry import discover
    from services.read.registry import list_strategies

    factors = sorted(discover().keys())
    datasets = sorted(_dataset_entries().keys())
    strategies = [f"{r.family}/{r.version}" for r in list_strategies()]
    return SemanticInventoryView(
        factors=factors,
        datasets=datasets,
        strategies=strategies,
        n_factors=len(factors),
        n_datasets=len(datasets),
        n_strategies=len(strategies),
    )
