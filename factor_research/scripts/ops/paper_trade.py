"""v2.0 模拟盘 (paper trading):读当日 signal → 模拟成交(真实成本)→ 更新账户 → 写 Obsidian 卡片。

口径(第一版,均可调):
  · 本金 100 万,1.0x(满仓=本金,不融资;策略默认 1.25x)
  · 成交价 = 信号日收盘价 + 真实成本(买0.225%/卖0.275%);实盘需次日开盘执行,有隔夜跳空偏差
  · 等权 1/top_n;A股 100 股整数倍;调仓日全部换新名单
  · 卖出由规则触发:择时转空→清仓;每 20 交易日调仓→卖掉出名单的
状态: paper/account.json + paper/trades.csv + paper/nav.csv
输出: <OBSIDIAN>/今日操作.md(覆盖) + 历史/YYYY-MM-DD.md(归档)
用法(cwd=factor_research): /usr/bin/python3 -m scripts.ops.paper_trade
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

import pandas as pd  # noqa: E402

INIT_CAPITAL = 1_000_000.0
LEVERAGE = 1.0          # 满仓=本金;改 1.25 复现策略默认融资版
BUY_COST = 0.00225
SELL_COST = 0.00275
LOT = 100               # A股最小交易单位

SIGNALS = ROOT / "signals"
PAPER = ROOT / "paper"
ACCOUNT_FP = PAPER / "account.json"
TRADES_FP = PAPER / "trades.csv"
NAV_FP = PAPER / "nav.csv"
OBSIDIAN = Path("/Users/kiki/Personal Wiki/30.output/A股v2.0模拟盘")


def get_price(code, date):
    """取 code 在 date(含)之前最近一个【不复权】收盘价(真实股价,用于算股数/成交/估值;
    后复权价虚高数倍会让 100 股预算买成 0 股)。停牌则用最近收盘估值。"""
    fp = ROOT / f"data_lake/price/daily_raw/{code}.parquet"
    if not fp.exists():
        return None
    df = pd.read_parquet(fp, columns=["date", "raw_close"])
    df = df[pd.to_datetime(df["date"]) <= pd.Timestamp(date)]
    return float(df["raw_close"].iloc[-1]) if len(df) else None


def load_names():
    fp = ROOT / "data_lake/meta/codes.parquet"
    if fp.exists():
        df = pd.read_parquet(fp)
        return dict(zip(df["code"].astype(str), df["name"]))
    return {}


def load_account():
    if ACCOUNT_FP.exists():
        return json.loads(ACCOUNT_FP.read_text())
    return {
        "init_capital": INIT_CAPITAL,
        "inception": None,
        "cash": INIT_CAPITAL,
        "positions": {},          # code -> {"shares": int, "avg_cost": float}
        "last_date": None,
    }


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


def sell_all(acc, date, names, trades):
    for code, pos in list(acc["positions"].items()):
        price = get_price(code, date)
        if price is None:
            continue
        notional = pos["shares"] * price
        cost = notional * SELL_COST
        acc["cash"] += notional - cost
        trades.append([date, code, names.get(code, code), "SELL", pos["shares"],
                       round(price, 3), round(notional, 2), round(cost, 2), round(acc["cash"], 2)])
    acc["positions"] = {}


def buy_basket(acc, date, holdings, top_n, names, trades):
    equity = acc["cash"]                      # 调仓前已全部卖出,equity≈cash
    budget_each = equity * LEVERAGE / top_n
    for code in holdings:
        price = get_price(code, date)
        if price is None or price <= 0:
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
        price = get_price(code, date)
        mv = pos["shares"] * price if price else 0.0
        pos_value += mv
        pnl = (price - pos["avg_cost"]) * pos["shares"] if price else 0.0
        detail.append({"code": code, "shares": pos["shares"], "cost": pos["avg_cost"],
                       "price": price, "mv": mv, "pnl": pnl})
    nav = acc["cash"] + pos_value
    return nav, pos_value, detail


def fmt(x):
    return f"{x:,.0f}"


def render_card(date, signal, decay, acc, nav, pos_value, detail, trades, names):
    ret = nav / acc["init_capital"] - 1
    action = signal["action"]
    lines = [
        f"# A股 v2.0 模拟盘 · {date}",
        "",
        f"> 自动生成 {datetime.now():%Y-%m-%d %H:%M} | 策略 small-cap-size/v2.0 | 本金 {fmt(acc['init_capital'])} | 杠杆 {LEVERAGE}x",
        "",
        "## 📋 今日操作",
    ]
    buys = [t for t in trades if t[3] == "BUY"]
    sells = [t for t in trades if t[3] == "SELL"]
    if action in ("空仓观望",):
        lines += ["**空仓观望,不建仓**(择时🔴)。今日无买卖,继续持币。", ""]
    elif action == "维持原仓位":
        lines += ["**维持原仓位**,今日无买卖(距上次调仓不足 20 交易日)。", ""]
    else:
        lines += [f"**{action}**", ""]
        if sells:
            lines += [f"**卖出 ({len(sells)} 只):**", "", "| 代码 | 名称 | 股数 | 价格 | 金额 |", "|--|--|--|--|--|"]
            lines += [f"| {t[1]} | {t[2]} | {t[4]} | {t[5]} | {fmt(t[6])} |" for t in sells]
            lines += [""]
        if buys:
            tot = sum(t[6] for t in buys)
            lines += [f"**买入 ({len(buys)} 只,合计 ≈ {fmt(tot)}):**", "",
                      "| 代码 | 名称 | 股数 | 参考价 | 金额 |", "|--|--|--|--|--|"]
            lines += [f"| {t[1]} | {t[2]} | {t[4]} | {t[5]} | {fmt(t[6])} |" for t in buys]
            lines += [""]

    lines += [
        "## 💰 账户",
        "",
        "| 指标 | 值 |",
        "|--|--|",
        f"| 总资产 | {fmt(nav)} |",
        f"| 现金 | {fmt(acc['cash'])} |",
        f"| 持仓市值 | {fmt(pos_value)} |",
        f"| 累计收益 | {ret:+.2%} |",
        f"| 持仓数 | {len(detail)} 只 |",
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
    lines += [
        "## 📈 择时 & 失效监控",
        "",
        f"- 择时: {'🟢 持仓' if signal['in_market'] else '🔴 空仓'}  (小盘指数 vs MA16: {dist:+.2%})",
    ]
    if decay:
        warn = str(decay.get("status", "")).startswith("🔴")
        lines += [f"- 失效: {decay['status']}  (IC {decay['ic']} vs 历史 {decay['ic_hist']} | "
                  f"小盘动量 {decay['rel_mom']:+.1%} | 滚动夏普 {decay['roll_sharpe']})  更新 {decay.get('updated')}"]
        if decay.get("msgs"):
            lines += [f"  - 触发: {', '.join(decay['msgs'])}"]
    else:
        warn = False
        lines += ["- 失效: (decay_status.json 缺失,跑 decay_monitor 刷新)"]

    lines += [
        "",
        "## 📖 卖出规则(系统自动执行)",
        "",
        "- 择时转空(小盘指数跌破 MA16)→ **全部清仓**",
        "- 调仓日(每 20 交易日)→ 卖掉**掉出 top25 名单**的股票,换入新进的",
        "- 无单只止盈止损(截面策略,靠分散+调仓控制风险)",
        "",
        "## ⚠️ 口径声明",
        "",
        "- **成交价 = 信号日收盘价**;你 16:30 收盘后才看到信号,实盘需**次日开盘**买入,会有隔夜跳空偏差",
        f"- 成本: 买 {BUY_COST:.3%} / 卖 {SELL_COST:.3%}(含佣金/印花税/过户费/滑点)",
        f"- 杠杆 {LEVERAGE}x(满仓=本金;策略默认 1.25x 融资版,如需告诉我)",
        f"- 容量: 本金 {fmt(acc['init_capital'])} ≪ 策略容量 ~2000万,无冲击成本压力",
    ]
    if signal["in_market"] and warn:
        lines += ["", "> ⚠️ **失效预警期**:此为模拟盘;真上实盘建议半仓起步,盯紧 IC 与小盘动量,恶化即退。"]
    return "\n".join(lines) + "\n"


def read_decay():
    dp = ROOT / "reports/decay_status.json"
    return json.loads(dp.read_text()) if dp.exists() else None


def build_preview(names):
    """假设择时转多,用当前 top25 名单生成建仓预览卡片(不碰正式账户)。"""
    from core.backtest import latest_signal, StrategyConfig
    print("[preview] 加载数据 + 计算当前 top25 名单(约 1-2 分钟)...")
    sig = latest_signal(StrategyConfig(start="2010-01-01"))
    date = str(sig["date"].date())
    psig = {"date": date, "action": "建仓买入", "in_market": sig["in_market"],
            "holdings": sig["holdings"], "top_n": 25,
            "small_index_vs_ma16": sig["timing_dist"]}
    acc = {"init_capital": INIT_CAPITAL, "inception": date, "cash": INIT_CAPITAL,
           "positions": {}, "last_date": None}
    trades = []
    buy_basket(acc, date, psig["holdings"], psig["top_n"], names, trades)
    nav, pos_value, detail = valuation(acc, date)
    card = render_card(date, psig, read_decay(), acc, nav, pos_value, detail, trades, names)
    warn = (f"> 🔮 **建仓预览** —— 这是「假如今天择时转多」系统会给出的可执行指令。\n"
            f"> ⛔ **当前实际择时 🔴 空仓({sig['timing_dist']:+.2%} vs MA16),切勿照此买入!**\n"
            f"> 仅展示买入清单格式、仓位分配与参考价。真实建仓信号到来时会自动写入「今日操作.md」。\n\n")
    OBSIDIAN.mkdir(parents=True, exist_ok=True)
    (OBSIDIAN / "建仓预览.md").write_text(warn + card)
    print(f"=== 建仓预览 {date}(假设转多)===")
    print(f"  买入 {len(trades)} 只 | 合计 {fmt(sum(t[6] for t in trades))} | 剩余现金 {fmt(acc['cash'])}")
    print(f"  → Obsidian: {OBSIDIAN/'建仓预览.md'}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preview", action="store_true", help="生成建仓预览(假设择时转多),不碰正式账户")
    args = ap.parse_args()
    if args.preview:
        return build_preview(load_names())

    sig_files = sorted(SIGNALS.glob("[0-9]*-[0-9]*-[0-9]*.json"))
    if not sig_files:
        print("无 signals/*.json,先跑 run_daily.py")
        return 1
    signal = json.loads(sig_files[-1].read_text())
    date = signal["date"]

    decay = read_decay()
    names = load_names()
    acc = load_account()
    if acc["inception"] is None:
        acc["inception"] = date

    trades = []
    already = acc["last_date"] == date
    if already:
        print(f"[skip] {date} 已处理过,仅刷新估值与卡片(不重复成交)")
    else:
        action = signal["action"]
        if action in ("建仓买入", "调仓买入"):
            sell_all(acc, date, names, trades)
            buy_basket(acc, date, signal["holdings"], signal["top_n"], names, trades)
        elif action == "清仓":
            sell_all(acc, date, names, trades)
        # 空仓观望 / 维持原仓位 → 无成交
        if trades:
            append_trades(trades)
        acc["last_date"] = date

    nav, pos_value, detail = valuation(acc, date)
    ret = nav / acc["init_capital"] - 1
    upsert_nav(date, nav, acc["cash"], pos_value, ret)
    save_account(acc)

    card = render_card(date, signal, decay, acc, nav, pos_value, detail, trades, names)
    OBSIDIAN.mkdir(parents=True, exist_ok=True)
    (OBSIDIAN / "今日操作.md").write_text(card)
    (OBSIDIAN / "历史").mkdir(exist_ok=True)
    (OBSIDIAN / "历史" / f"{date}.md").write_text(card)

    print(f"=== v2.0 模拟盘 {date} ===")
    print(f"  操作: {signal['action']}  成交 {len(trades)} 笔")
    print(f"  总资产 {fmt(nav)} | 现金 {fmt(acc['cash'])} | 持仓 {len(detail)}只 {fmt(pos_value)} | 累计 {ret:+.2%}")
    print(f"  → Obsidian: {OBSIDIAN/'今日操作.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
