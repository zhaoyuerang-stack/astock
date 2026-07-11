"""小程序专用数据服务 —— 脱敏层 + 聚合层。

职责(MINIPROGRAM_ARCHITECTURE §合规四道防线):
1. 内容脱敏:买入/卖出指令 → 进入/移出研究观察池;不展示委托数量/价格/金额
2. 数据聚合:首页一次请求拿全(市场状态+KPI+候选池+预警)
3. 免责声明注入:每条响应带 disclaimer

只读 services.read.* 现有视图,不写业务层。

⚠️ 镜像文件:实际运行于 factor_research/services/read/miniapp.py,修改请同步两边。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    yaml = None

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "app_config" / "miniapp_settings.yaml"


def _load_config() -> dict:
    if yaml is None or not CONFIG_PATH.exists():
        return {}
    try:
        return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001
        return {}


_CONFIG = _load_config()
_DESENS = _CONFIG.get("desensitization", {}) or {}
DISCLAIMER = _DESENS.get("disclaimer", "本工具为研究方法学分析工具,不构成任何投资建议。")
KEYWORD_BLACKLIST = _DESENS.get("keyword_blacklist", []) or []
ACTION_MAP = _DESENS.get("action_map", {}) or {}


# ─────────────────────────────────────────
# 首页聚合
# ─────────────────────────────────────────

def get_home_data(openid: str) -> dict:
    """首页聚合数据:市场状态 + KPI + 候选池 + 预警 + 结论 + 用户额度。"""
    from services.read.miniapp_auth import get_user

    user = get_user(openid)

    # 市场状态(读 signals/state.json)
    market = _read_market_state()

    # KPI(读注册表在册策略 metrics)
    kpi = _read_headline_kpi()

    # 候选池摘要(读目标组合 top-N)
    candidates = _read_candidate_pool()

    return {
        "marketStatus": market.get("regime", ""),
        "stance": market.get("stance", ""),
        "lastSignalDate": market.get("lastSignalDate", ""),
        "kpi": kpi,
        "candidatePool": candidates,
        "alerts": [],
        "conclusion": "研究参考:当前策略组合处于观察期",
        "user": {
            "plan": user.get("plan", "free"),
            "tokenBalance": user.get("tokenBalance", 0),
            "tokenQuota": user.get("tokenQuota", 0),
        },
        "disclaimer": DISCLAIMER,
    }


def _read_market_state() -> dict:
    """读当前持仓/动作状态(脱敏:动作 → 观察池话术)。"""
    try:
        from services.read.portfolio import current_portfolio
        view = current_portfolio(with_target=False)
        stance = _sanitize_action(view.stance)
        return {
            "regime": view.regime or "",
            "stance": stance,
            "lastSignalDate": "",
        }
    except Exception:  # noqa: BLE001
        return {"regime": "", "stance": "观察中", "lastSignalDate": ""}


def _read_headline_kpi() -> dict:
    """读在册策略的 headline 指标(年化/夏普/回撤/DSR)。"""
    try:
        from services.read.registry import list_strategies
        strategies = list_strategies()
        # 取第一个在册策略
        in_registry = [s for s in strategies
                       if s.status in ("registered", "在册", "ACTIVE")] or strategies
        if not in_registry:
            return _mock_kpi()
        s = in_registry[0]
        m = s.metrics or {}
        ng = s.nine_gate or {}
        return {
            "annual": _fmt_pct(m.get("annual")),
            "sharpe": _fmt_num(m.get("sharpe")),
            "maxDrawdown": _fmt_pct(m.get("maxdd"), signed=True),
            "dsrP": _fmt_num(ng.get("dsr_p") or m.get("dsr_p")),
        }
    except Exception:  # noqa: BLE001
        return _mock_kpi()


def _read_candidate_pool() -> dict:
    """读目标组合 top-N 候选池(脱敏:只展示代码,标注研究候选)。"""
    try:
        from services.read.portfolio import current_portfolio
        view = current_portfolio(with_target=True)
        holdings = view.target_holdings or []
        return {
            "count": len(holdings),
            "top": [
                {"code": h.code, "weight": round(h.weight, 4)}
                for h in holdings[:5]
            ],
            "asOf": view.target_as_of or "",
            "label": "研究候选,非投资建议",
        }
    except Exception:  # noqa: BLE001
        return {"count": 0, "top": [], "asOf": "", "label": "研究候选,非投资建议"}


def _mock_kpi() -> dict:
    return {
        "annual": "—",
        "sharpe": "—",
        "maxDrawdown": "—",
        "dsrP": "—",
    }


# ─────────────────────────────────────────
# 组合页(脱敏)
# ─────────────────────────────────────────

def get_portfolio_data(openid: str) -> dict:
    """组合页数据:净值 + 当前持仓(脱敏) + 目标持仓 + 状态。

    脱敏规则:
    - 动作(买/卖)→ 进入/移出研究观察池
    - 不展示数量/价格/金额,只展示代码 + 权重 + 方向标签
    - 全部标注"研究候选,非投资建议"
    """
    try:
        from services.read.portfolio import current_portfolio
        view = current_portfolio(with_target=True)

        current = [
            {
                "code": h.code,
                "weight": round(h.weight, 4),
                "label": "研究观察池",
            }
            for h in (view.current_positions or [])
        ]
        target = [
            {
                "code": h.code,
                "weight": round(h.weight, 4),
                "label": "研究候选",
            }
            for h in (view.target_holdings or [])
        ]

        return {
            "nav": round(view.nav, 4) if view.nav else 0.0,
            "cash": round(view.cash, 2) if view.cash else 0.0,
            "stance": _sanitize_action(view.stance),
            "regime": view.regime or "",
            "note": _sanitize_text(view.note),
            "currentPositions": current,
            "targetHoldings": target,
            "targetAsOf": view.target_as_of or "",
            "targetNote": _sanitize_text(view.target_note),
            "disclaimer": DISCLAIMER,
        }
    except Exception:  # noqa: BLE001
        return {
            "nav": 0.0,
            "cash": 0.0,
            "stance": "观察中",
            "regime": "",
            "note": "",
            "currentPositions": [],
            "targetHoldings": [],
            "targetAsOf": "",
            "targetNote": "",
            "disclaimer": DISCLAIMER,
        }


# ─────────────────────────────────────────
# 策略列表(脱敏)
# ─────────────────────────────────────────

def get_strategies_list(openid: str) -> list[dict]:
    """策略列表(脱敏后):只展示概要,不展示具体参数/配置。"""
    try:
        from services.read.registry import list_strategies
        strategies = list_strategies()
        out = []
        for s in strategies:
            ng = s.nine_gate or {}
            out.append({
                "strategyId": s.strategy_id,
                "family": s.family,
                "familyName": s.family_name,
                "version": s.version,
                "status": s.status,
                "hypothesis": _sanitize_text(s.hypothesis),
                "regime": s.regime,
                "desc": _sanitize_text(s.desc),
                "metrics": {
                    "annual": _fmt_pct((s.metrics or {}).get("annual")),
                    "sharpe": _fmt_num((s.metrics or {}).get("sharpe")),
                    "maxDrawdown": _fmt_pct((s.metrics or {}).get("maxdd"), signed=True),
                },
                "dsrP": _fmt_num(ng.get("dsr_p")),
                "label": "研究候选,非投资建议",
            })
        return out
    except Exception:  # noqa: BLE001
        return []


# ─────────────────────────────────────────
# 审计历史 / 结果(转发给 miniapp_audit)
# ─────────────────────────────────────────

def get_audit_history(openid: str, limit: int = 20) -> list[dict]:
    from services.read.miniapp_audit import list_jobs
    return list_jobs(openid, limit=limit)


def get_audit_result(job_id: str, openid: str) -> Optional[dict]:
    from services.read.miniapp_audit import load_job_result
    result = load_job_result(job_id, openid)
    if result and isinstance(result, dict):
        result.setdefault("disclaimer", DISCLAIMER)
    return result


# ─────────────────────────────────────────
# 脱敏辅助
# ─────────────────────────────────────────

def _sanitize_action(action: str) -> str:
    """动作指令 → 研究观察池话术。BUY → 进入研究观察池。"""
    if not action:
        return "观察中"
    action_upper = action.upper()
    for key, mapped in ACTION_MAP.items():
        if key in action_upper:
            return mapped
    # 含"空仓"/"持债"等也归一化
    if "空仓" in action or "空仓观望" in action:
        return "移出研究观察池"
    if "持债" in action or "避险" in action:
        return "转入避险观察"
    return action


def _sanitize_text(text: str) -> str:
    """过滤黑名单关键词(替换为 ***),其余原样。"""
    if not text:
        return ""
    out = text
    for kw in KEYWORD_BLACKLIST:
        if kw in out:
            out = out.replace(kw, "***")
    return out


def _fmt_num(v) -> str:
    if v is None or v == "":
        return "—"
    try:
        return f"{float(v):.3f}"
    except (TypeError, ValueError):
        return str(v)


def _fmt_pct(v, signed: bool = False) -> str:
    if v is None or v == "":
        return "—"
    try:
        f = float(v)
        if abs(f) < 1:
            f = f * 100
        sign = "+" if signed and f > 0 else ""
        return f"{sign}{f:.1f}%"
    except (TypeError, ValueError):
        return str(v)
