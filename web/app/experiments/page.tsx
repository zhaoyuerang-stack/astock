"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import Card from "@/components/ui/Card";
import DataTable from "@/components/ui/DataTable";
import { api, pct, num } from "@/lib/api";
import type { FunnelView, HypothesisView, RegisteredExperimentView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";
import AutoResearchLab from "./AutoResearchLab";
import LogicalChainsView from "./LogicalChainsView";
import ShadowIncubationView from "./ShadowIncubationView";
import AmountTimingValidationView from "./AmountTimingValidationView";

const STAGE_LABEL: Record<string, string> = {
  drafted: "草拟", queued: "入队", l0_passed: "L0", l1_passed: "L1",
  l2_passed: "L2", l3_passed: "L3", promoted: "已登记", discarded: "淘汰", shelved: "搁置",
};

const FILTERS = ["l3_passed", "l2_passed", "l1_passed", "discarded", "shelved"];

export default function ExperimentsPage() {
  const [tab, setTab] = useState<"pool" | "logical-chains" | "autoresearch" | "shadow-incubation" | "amount-timing-validation">("pool");
  const [funnel, setFunnel] = useState<FunnelView | null>(null);
  const [reg, setReg] = useState<RegisteredExperimentView[]>([]);
  const [hyps, setHyps] = useState<HypothesisView[]>([]);
  const [filter, setFilter] = useState<string>("l3_passed");
  const [err, setErr] = useState<string | null>(null);
  const setContext = useAgent((s) => s.setContext);

  const load = useCallback(() => {
    if (tab !== "pool") return;
    api.hypotheses(filter, 40).then(setHyps).catch(() => setHyps([]));
    Promise.all([api.funnel(), api.registeredExperiments()])
      .then(([f, r]) => {
        setFunnel(f);
        setReg(r);
        setContext({
          page: "experiments",
          title: "实验助手",
          summary: `假设池 ${f.total} 个候选,淘汰率 ${pct(f.discard_ratio, 0)};${f.stages.find((s) => s.stage === "l3_passed")?.count ?? 0} 个在 L3 待晋级,已登记 ${f.registered} 个。`,
          evidence: f.stages.map((s) => `${STAGE_LABEL[s.stage]}: ${s.count}`),
          recommendation: ["L3_PASSED 候选可经 workflow promote 晋级", "已登记实验带 config_hash 可复现"],
          nextActions: ["对比已登记实验的 IS/OOS/压力 绩效"],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext, tab, filter]);
  useAutoRefresh(load);

  const l3Count = funnel?.stages.find((s) => s.stage === "l3_passed")?.count ?? 0;
  const survivalRate = funnel && funnel.total > 0 ? l3Count / funnel.total : 0;
  const maxCount = funnel ? Math.max(1, ...funnel.stages.map((s) => s.count)) : 1;

  // Sort registered experiments by Sharpe descending for better decision-making
  const sortedReg = [...reg].sort((a, b) => (b.metrics.sharpe ?? 0) - (a.metrics.sharpe ?? 0));

  return (
    <div className="space-y-6">
      <PageHeader title="研究实验室" desc="因子流水线管理与量化策略孵化决策系统 · 实时流水线 & 晋级在册台账" />

      <div className="flex flex-wrap gap-1.5 mb-6 border-b border-line/30 pb-3">
        {([
          ["pool", "假设池漏斗"],
          ["logical-chains", "研报逻辑传导链条"],
          ["autoresearch", "AutoResearch 实验室"],
          ["shadow-incubation", "影子策略与本体分析"],
          ["amount-timing-validation", "择时模型敏感度验证"],
        ] as const).map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)}
            className={`text-[13px] px-4 py-2 rounded-lg transition-all duration-150 ${
              tab === key
                ? "bg-brand text-white font-semibold shadow-sm"
                : "bg-white text-subink hover:text-ink border border-line hover:border-brand/40"
            }`}>
            {label}
          </button>
        ))}
      </div>

      {tab === "logical-chains" && <LogicalChainsView />}

      {tab === "autoresearch" && <AutoResearchLab />}

      {tab === "shadow-incubation" && <ShadowIncubationView />}

      {tab === "amount-timing-validation" && <AmountTimingValidationView />}

      {tab === "pool" && err && <div className="card text-sm text-danger mb-4">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}

      {tab === "pool" && funnel && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
            <MetricCard label="假设池候选" value={String(funnel.total)} sub="去重唯一身份(内容哈希)" />
            <MetricCard label="L3 待晋级" value={String(l3Count)} tone="warn" sub={`漏斗生存率: ${pct(survivalRate, 1)}`} />
            <MetricCard label="已登记实验" value={String(funnel.registered)} tone="ok" sub="晋级成功入册台账" />
            <MetricCard label="淘汰率" value={pct(funnel.discard_ratio, 0)} tone="danger" sub="先证伪再相信" />
          </div>

          {/* 漏斗 pipeline */}
          <Card title="假设流水线(假设 → L0~L3 → 登记)" className="mb-5">
            <div className="flex items-end gap-2.5 h-36 bg-jilan/10 p-4 rounded-xl border border-line/20">
              {funnel.stages.map((s) => (
                <div key={s.stage} className="flex-1 flex flex-col items-center justify-end h-full group">
                  <span className="text-[12px] text-ink font-mono font-bold mb-1 opacity-0 group-hover:opacity-100 transition-opacity duration-150">{s.count}</span>
                  <div 
                    className="w-full rounded-t bg-brand hover:bg-brand-light transition-all duration-300 shadow-sm" 
                    style={{ height: `${(s.count / maxCount) * 80}%`, minHeight: s.count ? "4px" : "0" }} 
                  />
                  <span className="text-[11px] text-subink font-medium mt-2">{STAGE_LABEL[s.stage]}</span>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-2.5 mt-4">
              {funnel.side.map((s) => (
                <span key={s.stage} className="px-2.5 py-1 bg-jilan/25 border border-line/40 rounded-lg text-[11px] text-subink">
                  {STAGE_LABEL[s.stage]}:<span className="text-ink font-bold font-quant ml-1">{s.count}</span>
                </span>
              ))}
            </div>
          </Card>

          {/* 已登记实验对比 */}
          <Card title="已登记实验对比(IS / OOS-2023 / 压力-2010)" className="mb-5">
            <div className="overflow-x-auto">
              <DataTable<RegisteredExperimentView>
                rows={sortedReg}
                getRowKey={(e) => e.strategy_id}
                columns={[
                  { key: "strategy_id", header: "实验", className: "text-ink font-semibold", render: (e) => e.strategy_id },
                  { key: "status", header: "状态", render: (e) => <span className={e.status === "在册" ? "text-ok font-semibold" : e.status === "退役" ? "text-danger" : "text-warn"}>{e.status}</span> },
                  { key: "annual", header: "年化", align: "right", render: (e) => e.metrics.annual != null ? <span className="font-mono text-songshi font-bold">{pct(e.metrics.annual)}</span> : "—" },
                  { key: "sharpe", header: "夏普", align: "right", render: (e) => e.metrics.sharpe != null ? <span className="font-mono text-ink font-bold">{num(e.metrics.sharpe)}</span> : "—" },
                  { key: "maxdd", header: "回撤", align: "right", className: "text-subink font-mono", render: (e) => e.metrics.maxdd != null ? pct(e.metrics.maxdd) : "—" },
                  { key: "annual_2023", header: "年化(2023)", align: "right", className: "text-subink font-mono", render: (e) => e.metrics.annual_2023 != null ? pct(e.metrics.annual_2023) : "—" },
                  { 
                    key: "calmar", 
                    header: "卡玛比率", 
                    align: "right", 
                    render: (e) => {
                      if (e.metrics.annual != null && e.metrics.maxdd != null && e.metrics.maxdd !== 0) {
                        const calmar = e.metrics.annual / Math.abs(e.metrics.maxdd);
                        return <span className="font-mono text-ink">{num(calmar)}</span>;
                      }
                      return "—";
                    }
                  },
                  { 
                    key: "config_hash", 
                    header: "config_hash (点击复制)", 
                    align: "right", 
                    className: "font-mono text-[11px] text-subink", 
                    render: (e) => (
                      <span 
                        className="cursor-pointer hover:text-brand hover:underline font-mono text-[11px]" 
                        title="点击复制完整 Hash"
                        onClick={() => {
                          navigator.clipboard.writeText(e.config_hash);
                          alert("已成功复制完整 Hash 到剪贴板！");
                        }}
                      >
                        {e.config_hash.slice(0, 8)}...
                      </span>
                    )
                  },
                ]}
              />
            </div>
          </Card>

          {/* 假设列表 + 状态过滤 */}
          <Card
            title="假设列表"
            right={
              <div className="flex gap-1.5">
                {FILTERS.map((f) => (
                  <button key={f} onClick={() => setFilter(f)}
                    className={`text-[12px] px-2.5 py-1 rounded-md transition-all duration-150 ${
                      filter === f
                        ? "bg-brand text-white font-semibold shadow-sm"
                        : "bg-white text-subink border border-line hover:border-brand/40"
                    }`}>
                    {STAGE_LABEL[f]}
                  </button>
                ))}
              </div>
            }
          >
            <div className="max-h-80 overflow-y-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="text-subink text-left border-b border-line sticky top-0 bg-jilan">
                    <th className="py-2 px-3 font-semibold">假设</th>
                    <th className="py-2 px-3 font-semibold">来源</th>
                    <th className="py-2 px-3 font-semibold">机制</th>
                  </tr>
                </thead>
                <tbody>
                  {hyps.map((h) => (
                    <tr key={h.id} className="border-b border-line/50 hover:bg-jilan/10">
                      <td className="py-2 px-3 text-ink font-medium whitespace-nowrap pr-3">{h.name}</td>
                      <td className="py-2 px-3 text-subink pr-3">{h.source}</td>
                      <td className="py-2 px-3 text-subink truncate max-w-[420px]" title={h.mechanism}>{h.mechanism || "—"}</td>
                    </tr>
                  ))}
                  {hyps.length === 0 && <tr><td colSpan={3} className="py-4 text-center text-subink">该状态无假设</td></tr>}
                </tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
