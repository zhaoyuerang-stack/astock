"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import Card from "@/components/ui/Card";
import StatusBanner from "@/components/ui/StatusBanner";
import DataTable from "@/components/ui/DataTable";
import { api } from "@/lib/api";
import type { RiskReport, RiskRuleCheck } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

const STATUS_TONE: Record<string, string> = {
  ok: "text-ok", warn: "text-warn", breach: "text-danger", na: "text-subink",
};
const STATUS_LABEL: Record<string, string> = {
  ok: "通过", warn: "预警", breach: "超限", na: "无法计算",
};

function fmt(v: number | null) {
  if (v === null) return "—";
  return Math.abs(v) < 1 && v !== 0 ? v.toFixed(4) : v.toFixed(2);
}

export default function RiskPage() {
  const [r, setR] = useState<RiskReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState<Record<string, boolean>>({});
  const setContext = useAgent((s) => s.setContext);

  const load = useCallback(() => {
    api
      .risk()
      .then((d) => {
        setR(d);
        setContext({
          page: "risk",
          title: "风控助手",
          summary: `风控判定:${d.verdict}。${d.control_actions.length} 项控制动作待人工确认。`,
          evidence: d.checks.map((c) => `${c.rule}: ${fmt(c.current)} / 阈值 ${fmt(c.threshold)} → ${STATUS_LABEL[c.status]}`),
          risk: d.checks.filter((c) => c.status === "breach").map((c) => `${c.rule}超限`),
          recommendation: d.control_actions.map((a) => `${a.reason} → ${a.recommendation}`),
          nextActions: ["确认或驳回控制动作", "行业/市值集中度规则待补 industry_map"],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext]);
  useAutoRefresh(load);

  const tone = r ? (r.verdict === "正常" ? "ok" : r.verdict === "预警" ? "warn" : "danger") : "default";

  return (
    <div>
      <PageHeader title="风险控制" desc="声明式 risk_policy 评估 + 控制回路(超限→ControlAction 待确认) · 实时 /risk" />
      {err && <div className="card text-sm text-danger mb-4">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}
      {!r && !err && <div className="card text-sm text-subink">加载中…</div>}

      {r && (
        <>
          {/* 风控态势头条:一眼回答「组合有没有触发风控、要不要我处理」 */}
          {(() => {
            const breach = r.checks.filter((c) => c.status === "breach").length;
            const warn = r.checks.filter((c) => c.status === "warn").length;
            const na = r.checks.filter((c) => c.status === "na").length;
            return (
              <div className="mb-5">
                <StatusBanner
                  status={r.verdict === "正常" ? "ready" : r.verdict === "预警" ? "attention" : "blocked"}
                  title={`风控态势:${r.verdict}`}
                  detail={[
                    breach ? `${breach} 条超限` : null,
                    warn ? `${warn} 条预警` : null,
                    r.control_actions.length ? `${r.control_actions.length} 项控制动作待人工确认` : "无待确认控制动作",
                    na ? `${na} 条规则待补数据(未臆造)` : null,
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                />
              </div>
            );
          })()}

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
            <MetricCard label="风控判定" value={r.verdict} tone={tone as any} sub={`评估对象:${r.evaluated_on}`} />
            <MetricCard label="规则数" value={String(r.checks.length)} sub="声明式 risk_policy" />
            <MetricCard label="超限/预警" value={String(r.checks.filter((c) => c.status !== "ok" && c.status !== "na").length)} tone="warn" />
            <MetricCard label="待确认动作" value={String(r.control_actions.length)} tone={r.control_actions.length ? "warn" : "ok"} />
          </div>

          <Card title="风险规则 / 熔断规则" className="mb-5">
            <DataTable<RiskRuleCheck>
              rows={r.checks}
              getRowKey={(c) => c.rule}
              columns={[
                { key: "rule", header: "规则", className: "text-ink", render: (c) => (<>{c.rule}{c.note ? <span className="text-[11px] text-subink"> · {c.note}</span> : null}</>) },
                { key: "current", header: "当前值", align: "right", className: "text-ink", render: (c) => fmt(c.current) },
                { key: "threshold", header: "阈值", align: "right", className: "text-subink", render: (c) => fmt(c.threshold) },
                { key: "status", header: "状态", align: "right", render: (c) => <span className={STATUS_TONE[c.status]}>{STATUS_LABEL[c.status]}</span> },
              ]}
            />
            <div className="text-[11px] text-subink mt-2">注:行业/市值集中度规则待 data_lake 补 industry_map/market_cap 后接入(当前无数据,不臆造)。</div>
          </Card>

          <Card title="风控操作建议(ControlAction · 需人工二次确认)">
            {r.control_actions.length === 0 ? (
              <div className="text-sm text-ok">✅ 无超限,无待确认动作。</div>
            ) : (
              <div className="space-y-3">
                {r.control_actions.map((a) => (
                  <div key={a.action_id} className="border border-cardline rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-ink font-medium">{a.reason}</span>
                      <span className="text-[11px] px-1.5 py-0.5 rounded bg-bg text-warn border border-cardline">{a.action} · 待确认</span>
                    </div>
                    <div className="text-[12px] text-subink mt-1">触发:{a.trigger_state}</div>
                    <div className="text-[12px] text-ink mt-0.5">建议:{a.recommendation}</div>
                    <div className="mt-2 flex gap-2">
                      <button
                        disabled={confirmed[a.action_id]}
                        onClick={() => setConfirmed((s) => ({ ...s, [a.action_id]: true }))}
                        className="text-[12px] rounded px-3 py-1 bg-brand text-white disabled:opacity-50"
                      >
                        {confirmed[a.action_id] ? "已确认(本地)" : "二次确认"}
                      </button>
                      <span className="text-[11px] text-subink self-center">Agent 不可自动执行;高风险动作必须人工确认</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
