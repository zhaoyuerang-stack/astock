"use client";

import { useCallback, useMemo, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import Card from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { StrategyView } from "@/lib/types";
import { toInstitutionalRow, sortLeaderboard, groupFamilies } from "@/lib/institutional";
import { LeaderboardView, FamilyView, GateView, DrilldownPanel } from "@/components/factors/EvaluationViews";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

type SubView = "leaderboard" | "family" | "gate";

const VIEWS: [SubView, string, string][] = [
  ["leaderboard", "版本排行", "台账版本按 production_score 排序"],
  ["family", "家族折叠", "按 lineage 折叠,看换皮 / 选择偏差 / PBO"],
  ["gate", "Gate 热力图", "9-Gate 门禁通过矩阵"],
];

export default function FactorsPage() {
  const [subView, setSubView] = useState<SubView>("leaderboard");
  const [strategies, setStrategies] = useState<StrategyView[]>([]);
  const [activeStrategy, setActiveStrategy] = useState<StrategyView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const setContext = useAgent((s) => s.setContext);

  const load = useCallback(() => {
    setErr(null);
    api.strategies()
      .then((s) => {
        setStrategies(s);
        const registered = s.filter((x) => x.status === "在册");
        const dsrPass = s.filter((x) => x.nine_gate?.gate4_verdict === "PASS");
        setContext({
          page: "factors",
          title: "因子与策略评估",
          summary: `在册策略 ${registered.length} 只,扛过多重检验(DSR)仅 ${dsrPass.length} 只:${dsrPass.map((x) => x.strategy_id).join("、") || "无"}。`,
          evidence: dsrPass.map((x) => `${x.strategy_id}: DSR_p=${(x.nine_gate?.dsr_p ?? 0).toFixed(3)} PASS`),
          recommendation: [
            "把表当「哪些因子还没被杀死」的审计面板,而非「谁收益最高」的排行榜",
            "ρ≥0.9 视为换皮(同因子微调),不重复计入有效 alpha",
            "PBO≥0.3 的家族版本选择过拟合,入册需谨慎",
          ],
          nextActions: ["给未审计在册补 DSR", "高 PBO 家族做参数邻域稳定性(param grid)"],
        });
      })
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, [setContext]);
  useAutoRefresh(load);

  const registeredCount = strategies.filter((x) => x.status === "在册").length;
  const dsrPassCount = strategies.filter((x) => x.nine_gate?.gate4_verdict === "PASS").length;
  const observationCount = strategies.filter((x) => ["候选", "SHADOW", "shadow", "观察", "参考"].includes(x.status)).length;
  const retiredCount = strategies.filter((x) => ["退役", "已证伪"].includes(x.status)).length;
  const dupCount = strategies.filter((x) => (x.nine_gate?.corr_to_parent ?? 0) >= 0.9).length;

  const rows = useMemo(() => sortLeaderboard(strategies.map(toInstitutionalRow)), [strategies]);
  const families = useMemo(() => groupFamilies(strategies.map(toInstitutionalRow)), [strategies]);
  const activeRow = useMemo(() => (activeStrategy ? toInstitutionalRow(activeStrategy) : null), [activeStrategy]);

  return (
    <div className="space-y-5">
      <PageHeader title="因子与策略评估" desc="正式研究资产目录：台账版本、家族血缘与 Nine-Gate 审计；未登记候选留在研究实验室" />

      {loading && <div className="card text-sm text-subink animate-pulse">数据加载中…</div>}
      {err && <div className="card text-sm text-danger">API 错误:{err}<br />请确认后端已启动 (uvicorn :8011)。</div>}

      {!loading && !err && (
        <>
          {/* KPI 带 —— 诚实口径,突出决策信号 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard label="在册策略" value={String(registeredCount)} sub="过单母策略门槛" />
            <MetricCard label="过多重检验 (DSR)" value={String(dsrPassCount)} tone="ok" sub="扛过 DSR 惩罚 = 可信" />
            <MetricCard label="观察版本" value={String(observationCount)} tone="warn" sub="已登记但未进入正式在册" />
            <MetricCard label="退役 / 换皮" value={`${retiredCount} / ${dupCount}`} tone="warn" sub="退役资产与 ρ≥0.9 版本" />
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            <div className="inline-flex rounded-lg border border-line p-0.5 bg-jilan/30">
              {VIEWS.map(([key, label, hint]) => (
                <button key={key} onClick={() => setSubView(key)} title={hint}
                  className={`px-3.5 py-1.5 text-[12px] rounded-md transition-colors font-quant ${
                    subView === key ? "bg-white text-brand font-medium shadow-sm" : "text-subink hover:text-ink"
                  }`}>
                  {label}
                </button>
              ))}
            </div>
          </div>

          {/* 内容 + Drilldown */}
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
            <Card
              title={VIEWS.find(([k]) => k === subView)?.[2]}
              className={`${activeRow ? "lg:col-span-3" : "lg:col-span-5"} transition-all duration-300`}
            >
              {subView === "leaderboard" && <LeaderboardView rows={rows} activeId={activeStrategy?.strategy_id ?? null} onSelect={(s) => setActiveStrategy(activeStrategy?.strategy_id === s.strategy_id ? null : s)} />}
              {subView === "family" && <FamilyView groups={families} onSelect={(s) => setActiveStrategy(s)} />}
              {subView === "gate" && <GateView rows={rows} onSelect={(s) => setActiveStrategy(activeStrategy?.strategy_id === s.strategy_id ? null : s)} />}
            </Card>
            {activeRow && <DrilldownPanel row={activeRow} onClose={() => setActiveStrategy(null)} />}
          </div>
        </>
      )}
    </div>
  );
}
