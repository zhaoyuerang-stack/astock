"""风控评估:用声明式 risk_policy(settings.yaml)评估组合 → 逐条规则 + 超限生成 ControlAction。

控制回路(SPEC §3.4 / §10.3):规则超限 → 生成 ControlAction(requires_confirmation=True,
executed=False)→ 由人确认后才执行。本服务只**评估与建议**,绝不自动执行。
"""
from __future__ import annotations

from pathlib import Path

from contracts.models import ControlAction
from contracts.views import RiskReport, RiskRuleCheck
from services.read.portfolio import target_portfolio

ROOT = Path(__file__).resolve().parents[2]

_DEFAULT_POLICY = {
    "max_single_position_weight": 0.10,
    "max_position_count": 30,
    "max_leverage": 1.30,
    "max_drawdown_warning": -0.15,
    "max_drawdown_stop": -0.20,
    "max_turnover_annual": 25.0,
}


def _settings() -> dict:
    try:
        import yaml
    except ImportError:
        return {}
    p = ROOT / "app_config" / "settings.yaml"
    if not p.exists():
        return {}
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def load_risk_policy() -> dict:
    return {**_DEFAULT_POLICY, **(_settings().get("risk_policy") or {})}


def _registered_maxdd() -> float | None:
    """从台账取 illiquidity 在册版本的 maxdd(防御性匹配多种 key)。"""
    import strategy_registry
    data = strategy_registry._load()
    for fam in data.get("families", []):
        for v in fam.get("versions", []):
            if v.get("status") == "在册":
                m = v.get("metrics", {}) or {}
                for k in ("maxdd", "max_drawdown", "回撤", "mdd"):
                    if k in m:
                        try:
                            return float(m[k])
                        except (TypeError, ValueError):
                            pass
    return None


def _cap_check(rule, threshold, current, *, warn_ratio=0.9) -> RiskRuleCheck:
    """上限型规则:current>threshold = breach;>=warn_ratio*threshold = warn。"""
    if current is None:
        return RiskRuleCheck(rule=rule, threshold=threshold, current=None, status="na",
                             note="无法计算(空仓/缺数据)")
    if current > threshold:
        status = "breach"
    elif current >= warn_ratio * threshold:
        status = "warn"
    else:
        status = "ok"
    return RiskRuleCheck(rule=rule, threshold=threshold, current=current, status=status)


def risk_report() -> RiskReport:
    pol = load_risk_policy()
    sett = _settings()
    holds = target_portfolio()
    n = len(holds)
    max_w = max((h.weight for h in holds), default=0.0)
    leverage = float((sett.get("strategy") or {}).get("leverage", 1.25))
    maxdd = _registered_maxdd()

    checks: list[RiskRuleCheck] = [
        _cap_check("单票最大权重", pol["max_single_position_weight"], round(max_w, 4)),
        _cap_check("持仓数", pol["max_position_count"], n),
        _cap_check("杠杆", pol["max_leverage"], leverage),
    ]
    # 回撤:负值双阈值(warning/stop)
    if maxdd is None:
        checks.append(RiskRuleCheck(rule="最大回撤", threshold=pol["max_drawdown_stop"],
                                    current=None, status="na", note="台账无 maxdd"))
    else:
        if maxdd <= pol["max_drawdown_stop"]:
            st = "breach"
        elif maxdd <= pol["max_drawdown_warning"]:
            st = "warn"
        else:
            st = "ok"
        checks.append(RiskRuleCheck(rule="最大回撤", threshold=pol["max_drawdown_stop"],
                                    current=round(maxdd, 4), status=st, note="台账在册版本历史回撤"))

    actions: list[dict] = []
    for c in checks:
        if c.status in ("breach", "warn"):
            act = "decrease" if c.status == "breach" else "alert"
            actions.append(ControlAction(
                action_id=f"ca-{c.rule}",
                object_type="portfolio",
                object_id=f"{(sett.get('strategy') or {}).get('family','')}/{(sett.get('strategy') or {}).get('version','')}",
                trigger_state=f"{c.rule}={c.current} vs 阈值 {c.threshold}",
                action=act,
                reason=f"{c.rule} {'超限' if c.status=='breach' else '接近阈值'}",
                recommendation="降低该敞口至阈值内" if c.status == "breach" else "关注,暂不动作",
                requires_confirmation=True,
                executed=False,
                executed_by="",
            ).model_dump())

    if any(c.status == "breach" for c in checks):
        verdict = "超限"
    elif any(c.status == "warn" for c in checks):
        verdict = "预警"
    else:
        verdict = "正常"

    return RiskReport(evaluated_on="target", checks=checks, control_actions=actions, verdict=verdict)
