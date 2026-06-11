"""组合只读视图:当前组合(纸面/实盘)+ 目标组合(选股层 top-N)。

当前组合读 paper/account.json + signals/state.json(不触发计算)。
目标组合用 strategies/factors 的 canonical 选股路径现算最新 top-N 权重
(等权 top-N,独立于择时——展示"在市情景"的目标持仓)。
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

from contracts.views import Holding, PortfolioView

ROOT = Path(__file__).resolve().parents[2]


def _read_json(rel: str):
    p = ROOT / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def _latest_signal_json() -> dict:
    sig_dir = ROOT / "signals"
    files = sorted(sig_dir.glob("20*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else {}


@functools.lru_cache(maxsize=8)
def _target_cached(start: str, top_n: int, rebalance_days: int, factor_window: int) -> tuple:
    """现算最新 top-N 选股权重并缓存(目标组合一天才变一次,无需每请求重算)。

    缓存随进程生命周期;后端重启(或 --reload)即刷新。返回 hashable 元组。
    """
    from strategies.small_cap import load_price_panels, build_rebalance_weights
    from factors.small_cap import small_cap_factor

    close, _volume, amount = load_price_panels(start)
    factor = small_cap_factor(amount, window=factor_window)
    weights = build_rebalance_weights(factor, close, top_n=top_n, rebalance_days=rebalance_days)
    if not weights:                       # dict {effective_date: Series(等权 top_n)}
        return ()
    latest = weights[max(weights.keys())].sort_values(ascending=False)
    return tuple((str(c), float(w)) for c, w in latest.items())


def target_portfolio(start: str = "2023-01-01", top_n: int = 25,
                     rebalance_days: int = 20, factor_window: int = 60) -> list[Holding]:
    """最新 top-N 选股权重(canonical 路径,受控接缝;结果缓存,秒回)。"""
    return [Holding(code=c, weight=w) for c, w in _target_cached(start, top_n, rebalance_days, factor_window)]


def current_portfolio(with_target: bool = True) -> PortfolioView:
    acct = _read_json("paper/account.json")
    state = _read_json("signals/state.json")
    sig = _latest_signal_json()
    positions = acct.get("positions", {}) or {}
    cur = [Holding(code=str(c), weight=float(v.get("weight", 0.0)) if isinstance(v, dict) else 0.0)
           for c, v in positions.items()]
    rotation = sig.get("rotation", {}) or {}
    view = PortfolioView(
        nav=float(acct.get("cash", 0.0)) + 0.0,
        cash=float(acct.get("cash", 0.0)),
        current_positions=cur,
        stance=state.get("last_action", sig.get("action", "")),
        regime=sig.get("regime", ""),
        note=rotation.get("note", ""),
    )
    if with_target:
        tgt = target_portfolio()
        view.target_holdings = tgt
        view.target_as_of = str(sig.get("date", ""))
        view.target_note = "选股层 top-25(等权,未叠加择时;当前择时为空仓)"
    return view
