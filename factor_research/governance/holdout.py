"""Holdout 金库(LOOP_ENGINEERING.md §5.2)。

一段 loop **从未、永不**用于搜索的数据(date >= boundary)。研究/搜索回测必须
全部落在 < boundary;仅晋级前 validate_on_holdout **唯一一次**校验,且记账防重复偷看。
这是唯一能戳穿「过拟合到适应度函数」的东西——loop 自己不得触碰。

boundary 来自 app_config/settings.yaml::holdout.start(缺省 2025-01-01)。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

_DEFAULT_BOUNDARY = "2025-01-01"
_VALIDATIONS = Path(__file__).resolve().parents[1] / "data_lake" / "governance" / "holdout_validations.jsonl"


class HoldoutBreach(Exception):
    """搜索/研究回测触碰了 holdout 金库(date >= boundary)。"""


_SETTINGS_YAML = Path(__file__).resolve().parents[1] / "app_config" / "settings.yaml"


def boundary() -> pd.Timestamp:
    """金库起点:date >= 此为 holdout,搜索只能用 < 此。

    直读 settings.yaml::holdout.start(Settings dataclass 是固定 schema 不含此 section),
    缺省 2025-01-01。
    """
    start = _DEFAULT_BOUNDARY
    try:
        import yaml
        cfg = yaml.safe_load(_SETTINGS_YAML.read_text()) or {}
        start = (cfg.get("holdout") or {}).get("start", start)
    except Exception:
        pass
    return pd.Timestamp(start)


def is_holdout(date) -> bool:
    return pd.Timestamp(date) >= boundary()


def assert_search_clean(dates, *, label: str = "") -> None:
    """自查门:搜索/研究回测用到的日期必须全部 < boundary,否则抛 HoldoutBreach。

    dates:回测收益/面板的 DatetimeIndex,或单个最大日期。供 screener/factory 自纠。
    """
    if isinstance(dates, (pd.Series, pd.DataFrame, pd.DatetimeIndex)):
        idx = dates.index if hasattr(dates, "index") and not isinstance(dates, pd.DatetimeIndex) else dates
        max_date = pd.Timestamp(pd.DatetimeIndex(idx).max())
    else:
        max_date = pd.Timestamp(dates)
    b = boundary()
    if max_date >= b:
        raise HoldoutBreach(
            f"{label or '搜索回测'} 触碰 holdout 金库:数据末日 {max_date.date()} >= 金库起点 {b.date()}。"
            f" 搜索必须截到 < {b.date()};holdout 仅 validate_on_holdout 唯一一次校验。"
        )


_MIN_HOLDOUT_OBS = 20  # holdout 段至少这么多观测才算得动 DSR(短段 DSR 不可靠,留 None)


def holdout_trials(path: Path | None = None) -> int:
    """已在金库上验证过的**不同候选**数 = 金库的跨候选多重检验负担(§5.2 缝②)。

    每多一个候选在同一段金库上验证,金库就更接近"第二个样本内";holdout_dsr 用此累计数
    惩罚,防止规模化 p-hack 金库(跑够多候选总有几个靠运气过 sharpe 门)。
    """
    p = path or _VALIDATIONS
    if not p.exists():
        return 0
    ids = set()
    for line in p.read_text().splitlines():
        if not line.strip():
            continue
        try:
            cid = json.loads(line).get("candidate_id")
        except json.JSONDecodeError:
            continue
        if cid:
            ids.add(cid)
    return len(ids)


def validate_on_holdout(candidate_id: str, returns: pd.Series, *,
                        ts: str | None = None, path: Path | None = None) -> dict:
    """晋级前**唯一一次**在金库上校验(date >= boundary 段)。记账防重复偷看。

    返回 holdout 段绩效 + peek_count(同候选重复偷看)+ holdout_trials(跨候选多重检验数)
    + holdout_dsr_p/sig(按累计验证数惩罚后的 deflated Sharpe)。**仅 sharpe 高不够**——必须
    扛过"已有 N 个不同候选在同段金库上试过"的多重检验,否则金库退化成第二个样本内(§5.2 缝②)。
    """
    from engine.metrics import metrics
    b = boundary()
    r = pd.Series(returns).dropna()
    r_ho = r[r.index >= b]
    m = metrics(r_ho) if len(r_ho) else {"n": 0, "note": "holdout 段无数据"}

    p = path or _VALIDATIONS
    p.parent.mkdir(parents=True, exist_ok=True)
    prior = 0
    seen_ids: set[str] = set()
    if p.exists():
        for line in p.read_text().splitlines():
            if not line.strip():
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            cid = d.get("candidate_id")
            if cid:
                seen_ids.add(cid)
            if cid == candidate_id:
                prior += 1
    peek = prior + 1
    n_trials = len(seen_ids | {candidate_id})  # 含本候选的跨候选多重检验数

    # 按累计验证数惩罚的 holdout DSR(短段算不动留 None,退回 sharpe 门兜底)
    dsr_p, dsr_sig = None, None
    if isinstance(m.get("sharpe"), (int, float)) and m.get("n", 0) >= _MIN_HOLDOUT_OBS:
        from core.analysis.walk_forward import deflated_sharpe
        rep = deflated_sharpe(observed_sr=m["sharpe"], n_trials=n_trials, n_periods=m["n"],
                              skew=m.get("skew", 0.0), kurt=m.get("kurtosis_excess", 0.0) + 3.0,
                              annualized=True)
        dsr_p, dsr_sig = round(float(rep["p_value"]), 4), bool(rep["significant_05"])

    rec = {
        "ts": ts or datetime.now(timezone.utc).isoformat(),
        "candidate_id": candidate_id,
        "boundary": str(b.date()),
        "peek_count": peek,
        "holdout_trials": n_trials,
        "holdout_dsr_p": dsr_p,
        "holdout_dsr_sig": dsr_sig,
        "holdout_metrics": {k: (float(m[k]) if isinstance(m.get(k), (int, float, np.floating)) else m.get(k))
                            for k in ("annual", "sharpe", "maxdd", "n") if k in m},
    }
    with open(p, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    out = dict(rec["holdout_metrics"])
    out["peek_count"] = peek
    out["holdout_trials"] = n_trials
    out["holdout_dsr_p"] = dsr_p
    out["holdout_dsr_sig"] = dsr_sig
    if peek > 1:
        out["warning"] = f"⚠️ candidate {candidate_id} 已第 {peek} 次偷看 holdout — 多次偷看=隐性过拟合,采信存疑"
    return out
