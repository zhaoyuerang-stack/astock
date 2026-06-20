"use client";

import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import Card from "@/components/ui/Card";
import PlanCard from "@/components/paper/PlanCard";
import TradesTable from "@/components/paper/TradesTable";
import NavChart from "@/components/paper/NavChart";
import TimeTravelSimulator from "@/components/paper/TimeTravelSimulator";
import { api, pct } from "@/lib/api";
import type { NavCurveView, PaperTradesView, PortfolioView, TradePlanView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

const TABS = ["组合概览", "今日操作卡", "交易记录", "净值曲线", "时空穿梭机"] as const;
type Tab = (typeof TABS)[number];

export default function PortfolioPage() {
  const [tab, setTab] = useState<Tab>("组合概览");
  const [p, setP] = useState<PortfolioView | null>(null);
  const [plan, setPlan] = useState<TradePlanView | null>(null);
  const [trades, setTrades] = useState<PaperTradesView | null>(null);
  const [nav, setNav] = useState<NavCurveView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const setContext = useAgent((s) => s.setContext);

  const loadPaper = useCallback(() => {
    api.paperPlan().then(setPlan).catch((e) => setErr(String(e)));
    api.paperTrades().then(setTrades).catch(() => {});
    api.paperNav().then(setNav).catch(() => {});
  }, []);

  const load = useCallback(() => {
    api.portfolio().then(setP).catch((e) => setErr(String(e)));
    loadPaper();
  }, [loadPaper]);
  useAutoRefresh(load);

  useEffect(() => {
    if (!p && !plan) return;
    const regime = plan?.regime || p?.regime || "";
    setContext({
      page: "portfolio",
      title: "组合优化助手",
      summary: plan
        ? `模拟盘跟单:${plan.signal_date} ${plan.action}(${regime});净值 ${(plan.nav / 10000).toFixed(2)}万,今日成交 ${plan.executed.length} 笔,明日计划 ${plan.plan.length} 腿${plan.bond?.active ? ` + 债券轮动 ${plan.bond.side}` : ""}。`
        : `当前 ${p?.stance || "—"}(${regime});现金 ${((p?.cash ?? 0) / 10000).toFixed(0)}万。`,
      evidence: [
        plan?.bond?.note || p?.note || "—",
        plan ? `今日成交 ${plan.executed.length} 笔 / 受阻 ${plan.blocked.length} 笔` : "—",
      ],
      recommendation: [
        "操作卡为策略信号的机械呈现,模拟盘按真实盘 T+1 口径自动执行",
        "债券轮动(P5)已接入模拟盘:BEAR 闲置资金买 511010,BULL 卖出换股",
      ],
      nextActions: ["查看今日操作卡与净值曲线", "查看风险控制页评估目标组合"],
    });
  }, [p, plan, setContext]);

  return (
    <div>
      <PageHeader title="组合管理" desc="模拟盘跟单(真实盘 T+1 口径)· 当前组合 vs 目标组合 · 实时 /portfolio + /paper" />
      {err && <div className="card text-sm text-danger mb-4">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}

      <div className="flex gap-1 mb-4 border-b border-cardline">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-1.5 text-[13px] rounded-t border-b-2 -mb-px ${
              tab === t ? "border-brand text-brand font-medium" : "border-transparent text-subink hover:text-ink"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {tab === "组合概览" && (
        <>
          {!p && !err && <div className="card text-sm text-subink">加载中…</div>}
          {p && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
                <MetricCard label="组合净值" value={`${(p.nav / 10000).toFixed(2)}万`} sub="纸面账户" />
                <MetricCard label="现金占比" value={p.nav > 0 ? pct(p.cash / p.nav, 0) : "—"} tone="ok" sub={p.stance} />
                <MetricCard label="当前持仓" value={String(p.current_positions.length)} sub={`市场状态 ${p.regime}`} />
                <MetricCard label="目标持仓" value={String(p.target_holdings.length)} sub="选股层 top-N(等权)" />
              </div>

              {p.note && (
                <div className="card mb-5 text-sm text-subink">
                  <span className="text-ink font-medium">当前择时:</span> {p.stance} —— {p.note}
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <Card title="当前组合 vs 目标组合">
                  <div className="text-[13px] space-y-1.5">
                    <div className="flex justify-between"><span className="text-subink">当前</span><span className="text-ink">{p.current_positions.length ? `${p.current_positions.length} 只持仓` : "空仓 / 全现金"}</span></div>
                    <div className="flex justify-between"><span className="text-subink">目标</span><span className="text-ink">{p.target_holdings.length} 只 · 单票 {pct(p.target_holdings[0]?.weight ?? 0, 1)}</span></div>
                    <div className="text-[11px] text-subink pt-1">{p.target_note}</div>
                  </div>
                </Card>

                <Card title={`目标持仓(${p.target_as_of || "—"})`}>
                  <div className="max-h-64 overflow-y-auto">
                    <table className="w-full text-[13px]">
                      <thead>
                        <tr className="text-subink text-left border-b border-cardline sticky top-0 bg-[#24354D]">
                          <th className="py-1 font-medium">代码</th>
                          <th className="py-1 font-medium text-right">目标权重</th>
                        </tr>
                      </thead>
                      <tbody>
                        {p.target_holdings.map((h) => (
                          <tr key={h.code} className="border-b border-cardline/60">
                            <td className="py-1 text-ink">{h.code}</td>
                            <td className="py-1 text-right text-subink">{pct(h.weight, 2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              </div>
            </>
          )}
        </>
      )}

      {tab === "今日操作卡" && (
        <>
          {!plan && !err && <div className="card text-sm text-subink">加载中…</div>}
          {plan && (
            <>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                <MetricCard label="总资产" value={`${(plan.nav / 10000).toFixed(2)}万`} sub={`结算日 ${plan.account_date || plan.signal_date}`} />
                <MetricCard label="现金" value={`${(plan.cash / 10000).toFixed(2)}万`} sub={plan.action || "—"} />
                <MetricCard label="累计收益" value={`${plan.total_return >= 0 ? "+" : ""}${(plan.total_return * 100).toFixed(2)}%`} tone={plan.total_return >= 0 ? "ok" : "danger"} sub="vs 本金 100万" />
                <MetricCard label="Regime" value={plan.regime === "bear" ? "BEAR" : plan.regime === "bull" ? "BULL" : "—"} tone={plan.regime === "bear" ? "danger" : "ok"} sub={`信号日 ${plan.signal_date}`} />
              </div>
              <PlanCard plan={plan} />
            </>
          )}
        </>
      )}

      {tab === "交易记录" && (
        <>
          {!trades && !err && <div className="card text-sm text-subink">加载中…</div>}
          {trades && <TradesTable data={trades} />}
        </>
      )}

      {tab === "净值曲线" && (
        <>
          {!nav && !err && <div className="card text-sm text-subink">加载中…</div>}
          {nav && <NavChart data={nav} />}
        </>
      )}

      {tab === "时空穿梭机" && (
        <TimeTravelSimulator nav={nav} trades={trades} />
      )}

      <div className="text-[11px] text-subink mt-6">
        AI 生成内容仅供研究参考,不构成投资建议。回测与模拟盘结果不代表未来收益,实盘交易存在亏损风险。
      </div>
    </div>
  );
}
