"""illiquidity v1.0 模拟盘(真实盘成交逻辑):T+1 开盘价成交 + pending order + 停牌/涨跌停约束。

真实盘口径(你要求"所有模拟按真实盘"):
  · T 日盘后出信号 → 记 pending → **T+1 开盘按不复权开盘价成交**(收盘后才看到信号,只能次日买)
  · 停牌(当天无开盘价)不可买卖;一字涨停(开盘=涨停价)买不进、一字跌停卖不出
  · 等权 1/top_n,A股 100 股整数倍;成交/估值全用不复权价(daily_raw 的 raw_open/raw_close)
  · 本金 100 万,1.0x;成本 买 0.225% / 卖 0.275%
  · 回测口径(core 的 run_small_cap_strategy 收盘撮合)不动——回测归回测,成交归真实买卖
状态: paper/account.json(含 pending) + trades.csv + nav.csv
输出: <OBSIDIAN>/今日操作.md(覆盖) + 历史/YYYY-MM-DD.md(归档)
用法(cwd=factor_research): /usr/bin/python3 -m scripts.ops.paper_trade [--preview]
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from app_config.settings import get_settings

_cost_cfg = get_settings().cost

INIT_CAPITAL = 1_000_000.0
LEVERAGE = 1.0  # 模拟盘固定 1.0x
BUY_COST = _cost_cfg.buy_cost
SELL_COST = _cost_cfg.sell_cost
LOT = 100

SIGNALS = ROOT / "signals"
PAPER = ROOT / "paper"
ACCOUNT_FP = PAPER / "account.json"
TRADES_FP = PAPER / "trades.csv"
NAV_FP = PAPER / "nav.csv"
RAW = ROOT / "data_lake/price/daily_raw"
OBSIDIAN = Path("/Users/kiki/Personal Wiki/30.output/A股模拟盘")


# ── 价格:全部不复权(daily_raw)──
def _raw(code):
    fp = RAW / f"{code}.parquet"
    return pd.read_parquet(fp) if fp.exists() else None


def get_close(code, date):
    """date(含)前最近不复权收盘——估值用。"""
    df = _raw(code)
    if df is None:
        return None
    df = df[pd.to_datetime(df["date"]) <= pd.Timestamp(date)]
    return float(df["raw_close"].iloc[-1]) if len(df) else None


def get_open(code, date):
    """date 当天不复权开盘——T+1 成交价;停牌(当天无数据/无 open)返回 None。"""
    df = _raw(code)
    if df is None or "raw_open" not in df.columns:
        return None
    row = df[pd.to_datetime(df["date"]) == pd.Timestamp(date)]
    if not len(row):
        return None
    o = row["raw_open"].iloc[0]
    return float(o) if pd.notna(o) and o > 0 else None


def get_prev_close(code, date):
    """date 前一交易日不复权收盘——算涨跌停基准。"""
    df = _raw(code)
    if df is None:
        return None
    df = df[pd.to_datetime(df["date"]) < pd.Timestamp(date)]
    return float(df["raw_close"].iloc[-1]) if len(df) else None


# ── 涨跌停(按板块)──
def limit_pct(code, name):
    if name and "ST" in str(name).upper():
        return 0.05
    if code[:3] in ("300", "301", "688"):   # 创业板/科创
        return 0.20
    return 0.10                              # 主板(北交所已不在universe)


def buyable_open(code, date, name):
    """T+1 可买入开盘价:未停牌且非开盘涨停;否则 None(买不进)。"""
    o = get_open(code, date)
    if o is None:
        return None
    pc = get_prev_close(code, date)
    if pc and o >= round(pc * (1 + limit_pct(code, name)), 2) - 1e-6:   # 开盘即涨停(涨停价按分四舍五入)
        return None
    return o


def sellable_open(code, date, name):
    """T+1 可卖出开盘价:未停牌且非开盘跌停;否则 None(卖不出)。"""
    o = get_open(code, date)
    if o is None:
        return None
    pc = get_prev_close(code, date)
    if pc and o <= round(pc * (1 - limit_pct(code, name)), 2) + 1e-6:   # 开盘即跌停(跌停价按分四舍五入)
        return None
    return o


# ── account / 流水 IO ──
def load_names():
    fp = ROOT / "data_lake/meta/codes.parquet"
    if fp.exists():
        df = pd.read_parquet(fp)
        return dict(zip(df["code"].astype(str), df["name"]))
    return {}


def load_account():
    if ACCOUNT_FP.exists():
        return json.loads(ACCOUNT_FP.read_text())
    return {"init_capital": INIT_CAPITAL, "inception": None, "cash": INIT_CAPITAL,
            "positions": {}, "pending": None, "last_date": None}


def save_account(acc):
    PAPER.mkdir(exist_ok=True)
    ACCOUNT_FP.write_text(json.dumps(acc, ensure_ascii=False, indent=2))


def append_trades(rows):
    PAPER.mkdir(exist_ok=True)
    new = not TRADES_FP.exists()
    with TRADES_FP.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["date", "code", "name", "side", "shares", "price", "notional", "cost", "cash_after"])
        w.writerows(rows)


def upsert_nav(date, nav, cash, pos_value, ret):
    PAPER.mkdir(exist_ok=True)
    rows = {}
    if NAV_FP.exists():
        with NAV_FP.open() as f:
            for r in csv.DictReader(f):
                rows[r["date"]] = r
    rows[date] = {"date": date, "nav": f"{nav:.2f}", "cash": f"{cash:.2f}",
                  "position_value": f"{pos_value:.2f}", "total_return": f"{ret:.6f}"}
    with NAV_FP.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "nav", "cash", "position_value", "total_return"])
        w.writeheader()
        for d in sorted(rows):
            w.writerow(rows[d])


# ── T+1 开盘成交:把持仓调到 target ──
def execute_to_target(acc, date, target, top_n, names, trades, blocked):
    target = set(target)
    # 1. 卖出:持仓中不在 target 的(掉出名单),用 date 开盘价
    for code in list(acc["positions"]):
        if code in target:
            continue
        price = sellable_open(code, date, names.get(code))
        if price is None:
            blocked.append(("卖出", code, names.get(code, code), "停牌/一字跌停,卖不出"))
            continue
        pos = acc["positions"].pop(code)
        notional = pos["shares"] * price
        cost = notional * SELL_COST
        acc["cash"] += notional - cost
        trades.append([date, code, names.get(code, code), "SELL", pos["shares"],
                       round(price, 3), round(notional, 2), round(cost, 2), round(acc["cash"], 2)])
    # 2. 买入:target 中未持有的(新进名单),等权 total_equity/top_n,用 date 开盘价
    pos_value = sum(p["shares"] * (get_close(c, date) or p["avg_cost"]) for c, p in acc["positions"].items())
    budget_each = (acc["cash"] + pos_value) * LEVERAGE / top_n
    for code in target:
        if code in acc["positions"]:
            continue
        price = buyable_open(code, date, names.get(code))
        if price is None:
            blocked.append(("买入", code, names.get(code, code), "停牌/一字涨停,买不进"))
            continue
        shares = int(budget_each / price // LOT) * LOT
        if shares <= 0:
            continue
        notional = shares * price
        cost = notional * BUY_COST
        if notional + cost > acc["cash"]:
            continue
        acc["cash"] -= notional + cost
        acc["positions"][code] = {"shares": shares, "avg_cost": round(price, 3)}
        trades.append([date, code, names.get(code, code), "BUY", shares,
                       round(price, 3), round(notional, 2), round(cost, 2), round(acc["cash"], 2)])


def valuation(acc, date):
    pos_value = 0.0
    detail = []
    for code, pos in acc["positions"].items():
        price = get_close(code, date)
        mv = pos["shares"] * price if price else 0.0
        pos_value += mv
        pnl = (price - pos["avg_cost"]) * pos["shares"] if price else 0.0
        detail.append({"code": code, "shares": pos["shares"], "cost": pos["avg_cost"],
                       "price": price, "mv": mv, "pnl": pnl})
    return acc["cash"] + pos_value, pos_value, detail


def estimate_basket(date, codes, equity, top_n, names):
    """按参考价(date 收盘)估算等权建仓清单——给"明日计划"/预览展示,实际按 T+1 开盘成交。"""
    budget_each = equity * LEVERAGE / top_n
    rows = []
    for code in codes:
        ref = get_close(code, date)
        if not ref:
            continue
        shares = int(budget_each / ref // LOT) * LOT
        if shares > 0:
            rows.append((code, names.get(code, code), shares, ref, shares * ref))
    return rows


def fmt(x):
    return f"{x:,.0f}"


def read_decay():
    dp = ROOT / "reports/decay_status.json"
    return json.loads(dp.read_text()) if dp.exists() else None


def render_card(date, signal, decay, acc, nav, pos_value, detail, trades, blocked, names, exec_from):
    ret = nav / acc["init_capital"] - 1
    buys = [t for t in trades if t[3] == "BUY"]
    sells = [t for t in trades if t[3] == "SELL"]
    lines = [
        f"# A股 模拟盘 · {date}",
        "",
        f"> 自动生成 {datetime.now():%Y-%m-%d %H:%M} | illiquidity v1.0 | 本金 {fmt(acc['init_capital'])} | "
        f"杠杆 {LEVERAGE}x | 真实盘 T+1 开盘成交",
        "",
        "## 📋 今日开盘成交" + (f"(执行 {exec_from} 信号)" if exec_from else ""),
        "",
    ]
    if not exec_from:
        lines += ["今日无待执行订单(模拟盘首日或上一信号为空仓)。", ""]
    elif not trades and not blocked:
        lines += ["目标与持仓一致,今日开盘无买卖。", ""]
    else:
        if sells:
            lines += [f"**卖出 {len(sells)} 只(开盘价):**", "", "| 代码 | 名称 | 股数 | 开盘价 | 金额 |", "|--|--|--|--|--|"]
            lines += [f"| {t[1]} | {t[2]} | {t[4]} | {t[5]} | {fmt(t[6])} |" for t in sells]
            lines += [""]
        if buys:
            tot = sum(t[6] for t in buys)
            lines += [f"**买入 {len(buys)} 只(开盘价,合计 ≈ {fmt(tot)}):**", "",
                      "| 代码 | 名称 | 股数 | 开盘价 | 金额 |", "|--|--|--|--|--|"]
            lines += [f"| {t[1]} | {t[2]} | {t[4]} | {t[5]} | {fmt(t[6])} |" for t in buys]
            lines += [""]
        if blocked:
            lines += [f"**⛔ 未成交 {len(blocked)} 笔(真实盘约束):**", "", "| 方向 | 代码 | 名称 | 原因 |", "|--|--|--|--|"]
            lines += [f"| {b[0]} | {b[1]} | {b[2]} | {b[3]} |" for b in blocked]
            lines += [""]

    # 明日计划(本日信号 → 次日开盘执行)
    pend = acc.get("pending") or {}
    target = pend.get("target") or []
    lines += ["## 📅 明日开盘计划" + f"(本日 {date} 信号 → 次日开盘执行)", ""]
    if signal["in_market"] and target:
        plan = estimate_basket(date, target, nav, signal["top_n"], names)
        lines += [f"目标持仓 {len(target)} 只等权;次日开盘买入(参考价=今收,实际按开盘价):", "",
                  "| 代码 | 名称 | 预计股数 | 参考价 | 预计金额 |", "|--|--|--|--|--|"]
        lines += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]:.2f} | {fmt(r[4])} |" for r in plan]
        lines += [""]
    else:
        lines += ["**空仓观望**,明日开盘不建仓(若有持仓则次日开盘清仓)。", ""]

    lines += [
        "## 💰 账户", "", "| 指标 | 值 |", "|--|--|",
        f"| 总资产 | {fmt(nav)} |",
        f"| 现金 | {fmt(acc['cash'])} |",
        f"| 持仓市值 | {fmt(pos_value)} |",
        f"| 累计收益 | {ret:+.2%} |",
        f"| 持仓数 | {len(detail)} 只 |",
        f"| 起始日 | {acc.get('inception')} |",
        "",
    ]
    if detail:
        lines += ["## 📦 当前持仓", "", "| 代码 | 名称 | 股数 | 成本 | 现价 | 市值 | 浮盈 |", "|--|--|--|--|--|--|--|"]
        for d in sorted(detail, key=lambda x: -x["mv"]):
            pr = f"{d['price']:.2f}" if d["price"] else "停牌"
            lines += [f"| {d['code']} | {names.get(d['code'], d['code'])} | {d['shares']} | "
                      f"{d['cost']:.2f} | {pr} | {fmt(d['mv'])} | {d['pnl']:+,.0f} |"]
        lines += [""]
    else:
        lines += ["## 📦 当前持仓", "", "(空仓,持币观望)", ""]

    dist = signal.get("small_index_vs_ma16", 0)
    lines += ["## 📈 择时 & 失效监控", "",
              f"- 择时: {'🟢 持仓' if signal['in_market'] else '🔴 空仓'}  (小盘指数 vs MA16: {dist:+.2%})"]
    if decay:
        lines += [f"- 失效: {decay['status']}  (IC {decay['ic']} vs 历史 {decay['ic_hist']} | "
                  f"小盘动量 {decay['rel_mom']:+.1%} | 滚动夏普 {decay['roll_sharpe']})  更新 {decay.get('updated')}"]
        if decay.get("msgs"):
            lines += [f"  - 触发: {', '.join(decay['msgs'])}"]
    else:
        lines += ["- 失效: (decay_status.json 缺失,跑 decay_monitor 刷新)"]

    lines += [
        "", "## 📖 卖出规则(系统自动执行)", "",
        "- 择时转空(小盘指数跌破 MA16)→ 次日开盘**全部清仓**",
        "- 调仓日(每 20 交易日)→ 次日开盘卖掉**掉出 top25** 的、买入新进的",
        "- 无单只止盈止损(截面策略,靠分散+调仓控制风险)",
        "", "## ⚠️ 口径声明", "",
        "- **真实盘成交**:T 日盘后出信号 → **T+1 开盘价**成交(你收盘后才看到信号,只能次日买)",
        "- **停牌/涨跌停**:停牌不可买卖;一字涨停买不进、一字跌停卖不出(见上「未成交」)",
        f"- 成交/估值用**不复权价**(daily_raw);成本 买 {BUY_COST:.3%} / 卖 {SELL_COST:.3%}",
        f"- 杠杆 {LEVERAGE}x;容量:本金 {fmt(acc['init_capital'])} ≪ 策略容量 ~2000万",
        "- 回测口径(收盘撮合)另算——回测归回测,本卡是真实买卖逻辑",
    ]
    return "\n".join(lines) + "\n"


def build_preview(names):
    """假设择时转多:展示「次日开盘建仓清单」(不碰正式账户)。"""
    from core.backtest import load_price_panels
    from factors.utils import safe_zscore, mad_clip
    from factors.small_cap import small_cap_timing
    print("[preview] 加载数据 + 计算 illiquidity top25 名单(约 1-2 分钟)...")
    close, volume, amount = load_price_panels("2010-01-01")
    last = close.index[-1]
    # illiquidity factor
    ret_abs = close.pct_change(fill_method=None).abs().replace([float('inf'), float('-inf')], float('nan'))
    illiq_raw = (ret_abs / (amount + 1)).rolling(20, min_periods=10).mean()
    factor = safe_zscore(mad_clip(illiq_raw))
    f = factor.loc[last].dropna()
    active = close.loc[last].dropna().index
    holdings = f.reindex(active).dropna().nlargest(25).index.tolist()
    # Timing dist
    timing_raw, _, timing_dist = small_cap_timing(close, amount, 16)
    dist = float(timing_dist.loc[last]) if last in timing_dist.index else 0.0
    sig = {"date": last, "holdings": holdings, "top_n": 25, "timing_dist": dist,
           "in_market": bool(timing_raw.loc[last])}
    date = str(sig["date"].date())
    plan = estimate_basket(date, sig["holdings"], INIT_CAPITAL, 25, names)
    tot = sum(r[4] for r in plan)
    warn = (f"> 🔮 **建仓预览** —— 假如择时转多,系统会在**次日开盘**按此清单建仓。\n"
            f"> ⛔ **当前实际择时 🔴 空仓({sig['timing_dist']:+.2%} vs MA16),切勿照此买入!**\n"
            f"> 参考价=信号日({date})收盘,实际按 T+1 开盘价成交。\n\n")
    lines = [warn, f"# 建仓预览 · {date}", "",
             f"**目标 {len(plan)} 只等权,合计 ≈ {fmt(tot)},剩余 ≈ {fmt(INIT_CAPITAL - tot)}**", "",
             "| 代码 | 名称 | 预计股数 | 参考价 | 预计金额 |", "|--|--|--|--|--|"]
    lines += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]:.2f} | {fmt(r[4])} |" for r in plan]
    OBSIDIAN.mkdir(parents=True, exist_ok=True)
    (OBSIDIAN / "建仓预览.md").write_text("\n".join(lines) + "\n")
    print(f"=== 建仓预览 {date}(假设转多,次日开盘建仓)===")
    print(f"  目标 {len(plan)} 只 | 合计 {fmt(tot)} | 剩余 {fmt(INIT_CAPITAL - tot)}")
    print(f"  → Obsidian: {OBSIDIAN / '建仓预览.md'}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="生成次日开盘建仓预览,不碰正式账户")
    args = ap.parse_args()
    if args.preview:
        return build_preview(load_names())

    sig_files = sorted(SIGNALS.glob("[0-9]*-[0-9]*-[0-9]*.json"))
    if not sig_files:
        print("无 signals/*.json,先跑 run_daily.py")
        return 1
    signal = json.loads(sig_files[-1].read_text())
    date = signal["date"]
    names = load_names()
    decay = read_decay()
    acc = load_account()
    if acc["inception"] is None:
        acc["inception"] = date

    trades, blocked = [], []
    exec_from = None
    if acc["last_date"] != date:
        # 1. 结算上次 pending:用 date(=上个信号的次日)开盘价执行上个信号的目标
        pend = acc.get("pending")
        if pend:
            exec_from = pend["signal_date"]
            execute_to_target(acc, date, pend["target"], signal["top_n"], names, trades, blocked)
            if trades:
                append_trades(trades)
        # 2. 记录新 pending:本信号 → 下个交易日开盘执行
        target = signal["holdings"] if signal["in_market"] else []
        acc["pending"] = {"signal_date": date, "target": target}
        acc["last_date"] = date

    nav, pos_value, detail = valuation(acc, date)
    ret = nav / acc["init_capital"] - 1
    upsert_nav(date, nav, acc["cash"], pos_value, ret)
    save_account(acc)

    card = render_card(date, signal, decay, acc, nav, pos_value, detail, trades, blocked, names, exec_from)
    OBSIDIAN.mkdir(parents=True, exist_ok=True)
    (OBSIDIAN / "今日操作.md").write_text(card)
    (OBSIDIAN / "历史").mkdir(exist_ok=True)
    (OBSIDIAN / "历史" / f"{date}.md").write_text(card)

    print(f"=== illiquidity v1.0 模拟盘(真实盘 T+1){date} ===")
    print(f"  今日开盘成交: 买{len([t for t in trades if t[3]=='BUY'])} 卖{len([t for t in trades if t[3]=='SELL'])} "
          f"受阻{len(blocked)}" + (f"(执行{exec_from}信号)" if exec_from else "(无待执行)"))
    nxt = (acc.get("pending") or {}).get("target") or []
    print(f"  明日开盘计划: {'建仓/持有 '+str(len(nxt))+' 只' if (signal['in_market'] and nxt) else '空仓观望'}")
    print(f"  总资产 {fmt(nav)} | 现金 {fmt(acc['cash'])} | 持仓 {len(detail)}只 {fmt(pos_value)} | 累计 {ret:+.2%}")
    print(f"  → Obsidian: {OBSIDIAN / '今日操作.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
