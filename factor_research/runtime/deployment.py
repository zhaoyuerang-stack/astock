"""DeploymentManifest —— 区分「已注册策略」与「当前部署」(Task 7)。

注册表回答「哪个版本通过了完整证据门」;部署清单回答「现在到底在跑哪几条腿」。
两者解耦后,registry 退役 / spec_hash 不匹配会**机械地**让部署加载失败(fail-closed),
而不是靠代码里散落的硬编码 "LIVE" 字符串当事实源。

load_active_deployment 默认查 strategy_registry,但接受注入的 registry_lookup 以便测试。
任一腿不满足(版本不存在 / 非在册 / spec_hash 不一致)即抛 DeploymentNotReady。
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "deployments" / "production.json"

# registry 中视为「可部署」的版本状态(中文台账枚举 + 英文状态机别名,Task 15 统一)
DEPLOYABLE_STATUSES = {"在册", "REGISTERED", "DEPLOYED"}


class DeploymentNotReady(RuntimeError):
    """部署清单存在某条腿无法激活(版本缺失 / 未在册 / spec_hash 不匹配)。"""


@dataclass(frozen=True)
class DeploymentLeg:
    family: str
    version: str
    spec_hash: str
    role: str


@dataclass(frozen=True)
class Deployment:
    deployment_id: str
    environment: str
    status: str
    portfolio_policy: dict
    legs: tuple[DeploymentLeg, ...]


def _default_registry_lookup(family: str, version: str) -> Optional[dict]:
    """默认实现:从 strategy_registry 读某 family/version 的版本记录(含 status/executable_spec)。"""
    import strategy_registry
    data = strategy_registry._load()
    fam = next((f for f in data.get("families", []) if f.get("id") == family), None)
    if fam is None:
        return None
    return next((v for v in fam.get("versions", []) if v.get("version") == version), None)


def _validate_leg(leg: DeploymentLeg, registry_lookup: Callable[[str, str], Optional[dict]]) -> None:
    rec = registry_lookup(leg.family, leg.version)
    if rec is None:
        raise DeploymentNotReady(
            f"{leg.family}/{leg.version} 不在注册表 —— 不能部署未注册策略")
    status = rec.get("status")
    if status not in DEPLOYABLE_STATUSES:
        raise DeploymentNotReady(
            f"{leg.family}/{leg.version} 注册状态={status!r} 非可部署({sorted(DEPLOYABLE_STATUSES)});"
            f"退役/候选版本不得激活")
    reg_hash = (rec.get("executable_spec") or {}).get("spec_hash")
    if not reg_hash:
        raise DeploymentNotReady(
            f"{leg.family}/{leg.version} 注册记录缺少 executable_spec.spec_hash;"
            f"需先迁移到 spec 化身份(Task 19)")
    if reg_hash != leg.spec_hash:
        raise DeploymentNotReady(
            f"{leg.family}/{leg.version} spec_hash 不匹配:清单={leg.spec_hash[:12]} "
            f"注册={reg_hash[:12]} —— 部署与注册身份漂移")


def load_active_deployment(
    manifest_path: Path | str = DEFAULT_MANIFEST,
    *,
    registry_lookup: Optional[Callable[[str, str], Optional[dict]]] = None,
) -> Deployment:
    """加载并校验当前激活部署。任一腿不满足即抛 DeploymentNotReady(fail-closed)。"""
    registry_lookup = registry_lookup or _default_registry_lookup
    path = Path(manifest_path)
    if not path.exists():
        raise DeploymentNotReady(f"部署清单不存在: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))

    if manifest.get("status") != "active":
        raise DeploymentNotReady(f"部署 status={manifest.get('status')!r} 非 active")
    raw_legs = manifest.get("legs") or []
    if not raw_legs:
        raise DeploymentNotReady("部署清单没有任何腿")

    legs: list[DeploymentLeg] = []
    for i, rl in enumerate(raw_legs):
        for key in ("family", "version", "spec_hash", "role"):
            if not str(rl.get(key, "")).strip():
                raise DeploymentNotReady(f"第{i}条腿缺字段 {key!r}")
        legs.append(DeploymentLeg(
            family=rl["family"], version=rl["version"],
            spec_hash=rl["spec_hash"], role=rl["role"]))

    for leg in legs:
        _validate_leg(leg, registry_lookup)

    return Deployment(
        deployment_id=manifest.get("deployment_id", ""),
        environment=manifest.get("environment", ""),
        status=manifest["status"],
        portfolio_policy=manifest.get("portfolio_policy") or {},
        legs=tuple(legs),
    )


def load_deployed_strategy_spec(leg: DeploymentLeg):
    """Load the immutable spec referenced by one already-validated deployment leg."""
    from core.strategy_spec import ExecutableStrategySpec

    record = _default_registry_lookup(leg.family, leg.version)
    executable = (record or {}).get("executable_spec") or {}
    spec_data = executable.get("spec")
    if not spec_data:
        raise DeploymentNotReady(
            f"{leg.family}/{leg.version} registry executable spec body missing"
        )
    spec = ExecutableStrategySpec.from_dict(spec_data)
    spec.validate()
    if spec.spec_hash != leg.spec_hash:
        raise DeploymentNotReady(
            f"{leg.family}/{leg.version} executable spec body hash mismatch"
        )
    return spec
