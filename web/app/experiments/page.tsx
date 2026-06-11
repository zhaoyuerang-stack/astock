"use client";

import { useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import { api, pct, num } from "@/lib/api";
import type { FunnelView, HypothesisView, RegisteredExperimentView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";

const STAGE_LABEL: Record<string, string> = {
  drafted: "草拟", queued: "入队", l0_passed: "L0", l1_passed: "L1",
  l2_passed: "L2", l3_passed: "L3", promoted: "已登记", discarded: "淘汰", shelved: "搁置",
};

const FILTERS = ["l3_passed", "l2_passed", "l1_passed", "discarded", "shelved"];

export default function ExperimentsPage() {
  const [funnel, setFunnel] = useState<FunnelView | null>(null);
  const [reg, setReg] = useState<RegisteredExperimentView[]>([]);
  const [hyps, setHyps] = useState<HypothesisView[]>([]);
  const [filter, setFilter] = useState<string>("l3_passed");
  const [err, setErr] = useState<string | null>(null);
  const setContext = useAgent((s) => s.setContext);

  useEffect(() => {
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
  }, [setContext]);

  useEffect(() => {
    api.hypotheses(filter, 40).then(setHyps).catch(() => setHyps([]));
  }, [filter]);

  const maxCount = funnel ? Math.max(1, ...funnel.stages.map((s) => s.count)) : 1;

  return (
    <div>
      <PageHeader title="研究实验" desc="假设池漏斗 + 已登记实验 · 实时 factory/pool + registry" />
      {err && <div className="card text-sm text-danger mb-4">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}

      {funnel && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
            <MetricCard label="假设池候选" value={String(funnel.total)} sub="去重唯一身份(内容哈希)" />
            <MetricCard label="L3 待晋级" value={String(funnel.stages.find((s) => s.stage === "l3_passed")?.count ?? 0)} tone="warn" />
            <MetricCard label="已登记实验" value={String(funnel.registered)} tone="ok" sub="晋级成功入册台账" />
            <MetricCard label="淘汰率" value={pct(funnel.discard_ratio, 0)} tone="danger" sub="先证伪再相信" />
          </div>

          {/* 漏斗 pipeline */}
          <div className="card mb-5">
            <div className="text-sm font-medium mb-3">假设流水线(假设 → L0~L3 → 登记)</div>
            <div className="flex items-end gap-2 h-32">
              {funnel.stages.map((s) => (
                <div key={s.stage} className="flex-1 flex flex-col items-center justify-end h-full">
                  <span className="text-[12px] text-ink mb-1">{s.count}</span>
                  <div className="w-full rounded-t bg-brand" style={{ height: `${(s.count / maxCount) * 100}%`, minHeight: s.count ? "4px" : "0" }} />
                  <span className="text-[11px] text-subink mt-1">{STAGE_LABEL[s.stage]}</span>
                </div>
              ))}
            </div>
            <div className="flex gap-4 mt-3 text-[12px] text-subink">
              {funnel.side.map((s) => (
                <span key={s.stage}>{STAGE_LABEL[s.stage]}:<span className="text-ink"> {s.count}</span></span>
              ))}
            </div>
          </div>

          {/* 已登记实验对比 */}
          <div className="card mb-5">
            <div className="text-sm font-medium mb-3">已登记实验对比(IS / OOS-2023 / 压力-2010)</div>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="text-subink text-left border-b border-cardline">
                    <th className="py-1.5 font-medium">实验</th>
                    <th className="py-1.5 font-medium">状态</th>
                    <th className="py-1.5 font-medium text-right">年化</th>
                    <th className="py-1.5 font-medium text-right">夏普</th>
                    <th className="py-1.5 font-medium text-right">回撤</th>
                    <th className="py-1.5 font-medium text-right">年化(2023)</th>
                    <th className="py-1.5 font-medium text-right">config_hash</th>
                  </tr>
                </thead>
                <tbody>
                  {reg.map((e) => (
                    <tr key={e.strategy_id} className="border-b border-cardline/60">
                      <td className="py-1.5 text-ink">{e.strategy_id}</td>
                      <td className="py-1.5"><span className={e.status === "在册" ? "text-ok" : e.status === "退役" ? "text-danger" : "text-warn"}>{e.status}</span></td>
                      <td className="py-1.5 text-right">{e.metrics.annual != null ? pct(e.metrics.annual) : "—"}</td>
                      <td className="py-1.5 text-right">{e.metrics.sharpe != null ? num(e.metrics.sharpe) : "—"}</td>
                      <td className="py-1.5 text-right text-subink">{e.metrics.maxdd != null ? pct(e.metrics.maxdd) : "—"}</td>
                      <td className="py-1.5 text-right text-subink">{e.metrics.annual_2023 != null ? pct(e.metrics.annual_2023) : "—"}</td>
                      <td className="py-1.5 text-right font-mono text-[11px] text-subink">{e.config_hash}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 假设列表 + 状态过滤 */}
          <div className="card">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-medium">假设列表</div>
              <div className="flex gap-1">
                {FILTERS.map((f) => (
                  <button key={f} onClick={() => setFilter(f)}
                    className={`text-[12px] px-2 py-1 rounded ${filter === f ? "bg-brand text-white" : "bg-bg text-subink border border-cardline"}`}>
                    {STAGE_LABEL[f]}
                  </button>
                ))}
              </div>
            </div>
            <div className="max-h-80 overflow-y-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="text-subink text-left border-b border-cardline sticky top-0 bg-white">
                    <th className="py-1 font-medium">假设</th>
                    <th className="py-1 font-medium">来源</th>
                    <th className="py-1 font-medium">机制</th>
                  </tr>
                </thead>
                <tbody>
                  {hyps.map((h) => (
                    <tr key={h.id} className="border-b border-cardline/60">
                      <td className="py-1 text-ink whitespace-nowrap pr-3">{h.name}</td>
                      <td className="py-1 text-subink pr-3">{h.source}</td>
                      <td className="py-1 text-subink truncate max-w-[420px]" title={h.mechanism}>{h.mechanism || "—"}</td>
                    </tr>
                  ))}
                  {hyps.length === 0 && <tr><td colSpan={3} className="py-2 text-subink">该状态无假设</td></tr>}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
