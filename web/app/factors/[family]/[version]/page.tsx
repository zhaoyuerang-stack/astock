"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import { api, num, pct } from "@/lib/api";
import { artifactSection, displayRegistryStatus } from "@/lib/researchWorkspace.mjs";
import type { StrategyDetailView } from "@/lib/types";

type Tab = "overview" | "audit" | "performance" | "monitoring" | "config";
const TABS: [Tab, string][] = [
  ["overview", "概览"],
  ["audit", "Nine-Gate 审计"],
  ["performance", "绩效与成本"],
  ["monitoring", "影子 / 衰减监控"],
  ["config", "配置与研究记录"],
];

function metric(metrics: Record<string, number>, key: string, format: "pct" | "num" = "num") {
  const value = metrics[key];
  return value == null ? "—" : format === "pct" ? pct(value) : num(value);
}

function artifactPreview(value: unknown) {
  const serialized = JSON.stringify(value, null, 2);
  const limit = 12_000;
  return serialized.length > limit
    ? `${serialized.slice(0, limit)}\n\n… 产物较大，仅展示前 ${limit.toLocaleString()} 个字符。`
    : serialized;
}

export default function FactorVersionPage({ params }: { params: { family: string; version: string } }) {
  const [data, setData] = useState<StrategyDetailView | null>(null);
  const [tab, setTab] = useState<Tab>("overview");
  const [error, setError] = useState("");

  useEffect(() => {
    api.strategyDetail(params.family, params.version).then(setData).catch((e) => setError(String(e)));
  }, [params.family, params.version]);

  const artifactEntries = useMemo(() => Object.entries(data?.artifacts ?? {}), [data]);
  const performanceArtifacts = useMemo(
    () => artifactEntries.filter(([name]) => artifactSection(name) === "performance"),
    [artifactEntries],
  );
  const monitoringArtifacts = useMemo(
    () => artifactEntries.filter(([name]) => artifactSection(name) === "monitoring"),
    [artifactEntries],
  );
  const strategy = data?.strategy;
  const metrics = strategy?.metrics ?? {};
  const gate = strategy?.nine_gate ?? {};

  return (
    <div className="space-y-5">
      <PageHeader title={strategy?.strategy_id || `${params.family}/${params.version}`} desc="台账版本完整研究档案" />
      <Link href="/factors" className="text-[12px] text-brand hover:underline">← 返回因子研究</Link>
      {error && <div className="card text-sm text-danger">{error}</div>}
      {strategy && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <MetricCard label="生命周期" value={displayRegistryStatus(strategy.status)} />
            <MetricCard label="净年化" value={metric(metrics, "annual", "pct")} tone={(metrics.annual ?? 0) > 0 ? "ok" : "warn"} />
            <MetricCard label="最大回撤" value={metric(metrics, "maxdd", "pct")} tone={Math.abs(metrics.maxdd ?? 0) > 0.2 ? "danger" : "ok"} />
            <MetricCard label="夏普" value={metric(metrics, "sharpe")} />
            <MetricCard label="DSR p" value={gate.dsr_p == null ? "未审计" : Number(gate.dsr_p).toFixed(3)} tone={gate.gate4_verdict === "PASS" ? "ok" : "warn"} />
          </div>
          <div className="flex flex-wrap gap-1 border-b border-line pb-2">
            {TABS.map(([key, label]) => <button key={key} onClick={() => setTab(key)} className={`px-3 py-1.5 rounded text-[12px] ${tab === key ? "bg-brand text-white" : "text-subink hover:text-ink"}`}>{label}</button>)}
          </div>

          {tab === "overview" && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
              <div className="lg:col-span-2 card space-y-4">
                <h2 className="font-bold">经济假设与适用边界</h2>
                <p className="text-[13px]">{strategy.hypothesis || "—"}</p>
                <div className="text-[12px]"><span className="text-subink">适用 Regime：</span>{strategy.regime || "—"}</div>
                <div className="text-[12px]"><span className="text-subink">版本说明：</span>{strategy.desc || "—"}</div>
                <div className="text-[12px]"><span className="text-subink">准入轨：</span>{strategy.admission?.track || "未声明"} {strategy.admission?.rationale || ""}</div>
              </div>
              <div className="card space-y-2 text-[12px]">
                <h2 className="font-bold">版本身份</h2>
                <div><span className="text-subink">Family：</span>{strategy.family_name}</div>
                <div><span className="text-subink">Version：</span>{strategy.version}</div>
                <div><span className="text-subink">容量：</span>{strategy.capacity_m ? `${strategy.capacity_m} 百万` : "—"}</div>
                <div><span className="text-subink">数据口径：</span>{typeof strategy.data_scope === "string" ? strategy.data_scope : JSON.stringify(strategy.data_scope)}</div>
              </div>
            </div>
          )}

          {tab === "audit" && (
            <div className="card">
              <h2 className="font-bold mb-4">Nine-Gate 与版本血缘</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-[12px]">
                {Object.entries(gate).map(([key, value]) => <div key={key} className="border border-line rounded-lg p-3"><div className="text-[10px] text-subink">{key}</div><div className="font-mono mt-1 break-all">{typeof value === "object" ? JSON.stringify(value) : String(value)}</div></div>)}
              </div>
              {Object.keys(gate).length === 0 && <div className="text-sm text-subink">尚未持久化 Nine-Gate 审计。</div>}
            </div>
          )}

          {tab === "performance" && (
            <div className="space-y-4">
              <div className="card">
                <h2 className="font-bold mb-3">台账绩效与成本</h2>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-[12px]">
                  {Object.entries(metrics).map(([key, value]) => <div key={key} className="border border-line rounded-lg p-3"><div className="text-[10px] text-subink">{key}</div><div className="font-mono mt-1">{typeof value === "number" ? num(value, 4) : String(value)}</div></div>)}
                </div>
              </div>
              {performanceArtifacts.map(([name, artifact]) => (
                <details key={name} className="card" open={name.includes("timing")}>
                  <summary className="cursor-pointer font-semibold text-sm">专项验证：{name}</summary>
                  <pre className="mt-3 max-h-[520px] overflow-auto text-[10px]">{artifactPreview(artifact)}</pre>
                </details>
              ))}
              {performanceArtifacts.length === 0 && <div className="card text-sm text-subink">尚无与该版本绑定的绩效或成本专项结果。</div>}
            </div>
          )}

          {tab === "monitoring" && (
            <div className="space-y-5">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                <div className="card space-y-3 text-[12px]">
                  <h2 className="font-bold">失效边界</h2>
                  <div>{strategy.decay_signal || "未定义失效信号"}</div>
                  <pre className="text-[10px] bg-jilan/30 rounded p-3 overflow-auto">{JSON.stringify(strategy.failure_boundaries || {}, null, 2)}</pre>
                </div>
                <div className="card">
                  <h2 className="font-bold mb-3">影子 / 研究运行</h2>
                  <div className="space-y-2 text-[11px]">
                    {(data?.research_runs ?? []).map((run, index) => <div key={`${run.run_id}-${index}`} className="border-t border-line/50 pt-2"><div className="flex justify-between"><span className="font-semibold">{run.source}</span><span>{run.verdict}</span></div><div className="text-subink">{run.run_at} · {run.notes}</div></div>)}
                    {(data?.research_runs ?? []).length === 0 && <div className="text-subink">尚无与该版本绑定的研究运行。</div>}
                  </div>
                </div>
              </div>
              {monitoringArtifacts.map(([name, artifact]) => (
                <details key={name} className="card">
                  <summary className="cursor-pointer font-semibold text-sm">影子产物：{name}</summary>
                  <pre className="mt-3 max-h-[520px] overflow-auto text-[10px]">{artifactPreview(artifact)}</pre>
                </details>
              ))}
            </div>
          )}

          {tab === "config" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
              <details className="card" open><summary className="font-semibold cursor-pointer">版本配置</summary><pre className="mt-3 text-[10px] overflow-auto max-h-[620px]">{JSON.stringify(strategy.config, null, 2)}</pre></details>
              <div className="card space-y-3"><h2 className="font-bold">研究记录</h2><div className="text-[12px] whitespace-pre-wrap">{strategy.notes || "—"}</div><pre className="text-[10px] overflow-auto max-h-[420px]">{JSON.stringify(data?.research_runs ?? [], null, 2)}</pre></div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
