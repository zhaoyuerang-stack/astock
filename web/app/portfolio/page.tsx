"use client";

import { useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import { api, pct } from "@/lib/api";
import type { PortfolioView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";

export default function PortfolioPage() {
  const [p, setP] = useState<PortfolioView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const setContext = useAgent((s) => s.setContext);

  useEffect(() => {
    api
      .portfolio()
      .then((d) => {
        setP(d);
        setContext({
          page: "portfolio",
          title: "组合优化助手",
          summary: `当前 ${d.stance || "—"}(${d.regime});现金 ${(d.cash / 10000).toFixed(0)}万,持仓 ${d.current_positions.length} 只。目标选股层 ${d.target_holdings.length} 只(等权)。`,
          evidence: [d.note || "—", d.target_note],
          recommendation: ["当前空仓为择时结果(BEAR);目标组合展示选股层意图", "调仓前过风控页检查规则"],
          nextActions: ["查看风险控制页评估目标组合"],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext]);

  return (
    <div>
      <PageHeader title="组合管理" desc="当前组合(纸面)vs 目标组合(选股层 top-N) · 实时 /portfolio" />
      {err && <div className="card text-sm text-danger mb-4">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}
      {!p && !err && <div className="card text-sm text-subink">加载中…</div>}

      {p && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
            <MetricCard label="组合净值" value={`${(p.nav / 10000).toFixed(1)}万`} sub="纸面账户" />
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
            <div className="card">
              <div className="text-sm font-medium mb-2">当前组合 vs 目标组合</div>
              <div className="text-[13px] space-y-1.5">
                <div className="flex justify-between"><span className="text-subink">当前</span><span className="text-ink">{p.current_positions.length ? `${p.current_positions.length} 只持仓` : "空仓 / 全现金"}</span></div>
                <div className="flex justify-between"><span className="text-subink">目标</span><span className="text-ink">{p.target_holdings.length} 只 · 单票 {pct(p.target_holdings[0]?.weight ?? 0, 1)}</span></div>
                <div className="text-[11px] text-subink pt-1">{p.target_note}</div>
              </div>
            </div>

            <div className="card">
              <div className="text-sm font-medium mb-2">目标持仓({p.target_as_of || "—"})</div>
              <div className="max-h-64 overflow-y-auto">
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="text-subink text-left border-b border-cardline sticky top-0 bg-white">
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
            </div>
          </div>
        </>
      )}
    </div>
  );
}
