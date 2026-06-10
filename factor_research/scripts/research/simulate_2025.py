"""
2025年全年交易明细模拟 —— v2.0策略，100万起始资金，输出Excel

模型假设（Excel首页"假设"sheet会标注）：
  本金100万 · 1.25x杠杆(负现金=融资,年息6.5%) · 每20交易日调仓 · 择时空仓则清仓
  成本: 买入0.225%(佣金0.025%+冲击0.2%) / 卖出0.275%(印花税0.05%+佣金0.025%+冲击0.2%)
  股数按100股(1手)取整
"""
import warnings; warnings.filterwarnings("ignore")
import os
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
import sys
sys.path.insert(0, str(ROOT))
import numpy as np, pandas as pd
from strategies.small_cap import StrategyConfig, run_small_cap_strategy

INIT, LEV = 1_000_000, 1.25
TOP_N, SIZE_WIN, TIMING_MA, REBAL = 25, 60, 16, 20
C_BUY, C_SELL = 0.00025 + 0.002, 0.0005 + 0.00025 + 0.002   # 0.225% / 0.275%
FIN_DAILY = 0.065 / 252

# ── 加载数据 + 算因子/择时 (2023起，给因子缓冲) ──
core_result = run_small_cap_strategy(StrategyConfig(start="2023-01-01"))
close = core_result["close"]
size = core_result["factor"]
timing = core_result["timing"]

dates = close.loc["2025-01-01":"2025-12-31"].index
rebal_days = set(dates[::REBAL])          # 2025年初起每20交易日调仓

# ── 逐日模拟 ──
cash = float(INIT)
holdings = {}                              # code -> shares
trades, daily, rebal_log = [], [], []

def mv(d):                                 # 当日持仓市值
    return sum(sh * close.at[d, c] for c, sh in holdings.items()
               if c in close.columns and not np.isnan(close.at[d, c]))

for d in dates:
    # 融资利息(负现金部分)
    if cash < 0:
        cash -= abs(cash) * FIN_DAILY

    if d in rebal_days:
        in_mkt = bool(timing.loc[d])
        nav = cash + mv(d)
        # 目标持仓
        if in_mkt and nav > 0:
            f = size.loc[d].dropna()
            active = close.loc[d].dropna().index
            target = f.reindex(active).dropna().nlargest(TOP_N).index.tolist()
        else:
            target = []
        n_sell = n_buy = 0; cost_today = 0.0
        # 卖出(不在target的)
        for c in list(holdings.keys()):
            if c not in target:
                p = close.at[d, c]
                if np.isnan(p): continue
                sh = holdings.pop(c); amt = sh * p; cost = amt * C_SELL
                cash += amt - cost; cost_today += cost; n_sell += 1
                trades.append([d.date(), c, "卖出", round(p, 2), sh, round(amt), round(cost)])
        # 买入(target等权,1.25杠杆)
        if target:
            nav = cash + mv(d)
            tgt_val = nav * LEV / TOP_N
            for c in target:
                p = close.at[d, c]
                if np.isnan(p): continue
                cur = holdings.get(c, 0) * p
                buy_val = tgt_val - cur
                sh = int(buy_val / p / 100) * 100
                if sh <= 0: continue
                amt = sh * p; cost = amt * C_BUY
                cash -= amt + cost; cost_today += cost; n_buy += 1
                holdings[c] = holdings.get(c, 0) + sh
                trades.append([d.date(), c, "买入", round(p, 2), sh, round(amt), round(cost)])
        rebal_log.append([d.date(), "满仓" if in_mkt else "空仓", len(holdings),
                          n_buy, n_sell, round(cost_today), round(cash + mv(d))])

    nav = cash + mv(d)
    daily.append([d.date(), round(mv(d)), round(cash), round(nav)])

# ── 汇总 ──
df_tr = pd.DataFrame(trades, columns=["日期", "代码", "方向", "成交价", "股数", "金额", "成本"])
df_rb = pd.DataFrame(rebal_log, columns=["调仓日", "择时", "持仓数", "买入笔", "卖出笔", "当期成本", "期末总资产"])
df_dl = pd.DataFrame(daily, columns=["日期", "持仓市值", "现金", "总资产"])

final = df_dl["总资产"].iloc[-1]
total_cost = df_tr["成本"].sum()
turnover = df_tr["金额"].sum()
peak = df_dl["总资产"].cummax(); dd = (df_dl["总资产"] / peak - 1).min()
summary = pd.DataFrame({
    "项目": ["起始资金", "期末总资产", "全年收益", "全年收益率", "总交易成本",
            "成本占本金", "总成交额", "换手率(成交额/本金)", "交易笔数", "调仓次数",
            "最大回撤", "杠杆", "成本假设(买/卖)"],
    "值": [f"{INIT:,.0f}", f"{final:,.0f}", f"{final-INIT:+,.0f}", f"{final/INIT-1:+.1%}",
          f"{total_cost:,.0f}", f"{total_cost/INIT:.1%}", f"{turnover:,.0f}",
          f"{turnover/INIT:.1f}x", f"{len(df_tr)}", f"{len(df_rb)}",
          f"{dd:.1%}", f"{LEV}x", f"{C_BUY:.3%}/{C_SELL:.3%}"]
})

REPORTS = Path("reports")
REPORTS.mkdir(exist_ok=True)
out = REPORTS / "2025年交易明细_v2.0策略.xlsx"
with pd.ExcelWriter(out, engine="openpyxl") as w:
    summary.to_excel(w, sheet_name="年度汇总", index=False)
    df_rb.to_excel(w, sheet_name="调仓记录", index=False)
    df_tr.to_excel(w, sheet_name="交易明细", index=False)
    df_dl.to_excel(w, sheet_name="每日资金曲线", index=False)

print(f"✅ 已生成 {out.resolve()}")
print(f"\n年度汇总:")
print(summary.to_string(index=False))
print(f"\n调仓记录({len(df_rb)}次):")
print(df_rb.to_string(index=False))
