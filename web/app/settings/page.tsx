"use client";

import { useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import { api, pct } from "@/lib/api";
import type { SystemConfigView, AuditView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";

function Row({ k, v, locked }: { k: string; v: React.ReactNode; locked?: boolean }) {
  return (
    <div className="flex justify-between py-1 border-b border-cardline/60 text-[13px]">
      <span className="text-subink">{k}{locked && <span className="ml-1 text-warn">🔒</span>}</span>
      <span className="text-ink">{v}</span>
    </div>
  );
}

export default function SettingsPage() {
  const [c, setC] = useState<SystemConfigView | null>(null);
  const [audit, setAudit] = useState<AuditView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const setContext = useAgent((s) => s.setContext);

  useEffect(() => {
    Promise.all([api.systemConfig(), api.audit(30)])
      .then(([cfg, a]) => {
        setC(cfg);
        setAudit(a);
        setContext({
          page: "settings",
          title: "配置助手",
          summary: `成本铁律已锁定(只读);AI 模型 ${cfg.ai_model.mode};${cfg.quarantine_ranges} 个隔离区间;审计 ${a.total} 条。`,
          evidence: cfg.services.map((s) => `${s.name}: ${s.status}`),
          recommendation: ["成本/口径为铁律,UI 不可调低", "接真 LLM:设 ANTHROPIC_API_KEY"],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext]);

  return (
    <div>
      <PageHeader title="系统设置" desc="配置 / 服务状态 / 审计 · 实时 /settings" />
      {err && <div className="card text-sm text-danger mb-4">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}

      {c && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {/* 回测默认参数 / 成本铁律(只读)*/}
          <div className="card">
            <div className="text-sm font-medium mb-2">回测默认参数 · 成本(铁律锁定)</div>
            <Row k="买入成本" v={pct(Number(c.cost.buy_cost), 3)} locked />
            <Row k="卖出成本" v={pct(Number(c.cost.sell_cost), 3)} locked />
            <Row k="融资利率(年)" v={pct(Number(c.cost.financing_rate), 1)} locked />
            <div className="text-[11px] text-warn mt-2">🔒 成本与口径为铁律固化,UI 不可调低(防止在前端放宽以美化曲线)。</div>
          </div>

          {/* 策略 */}
          <div className="card">
            <div className="text-sm font-medium mb-2">当前策略</div>
            {Object.entries(c.strategy).map(([k, v]) => <Row key={k} k={k} v={String(v)} />)}
          </div>

          {/* 风控规则 */}
          <div className="card">
            <div className="text-sm font-medium mb-2">风控规则(risk_policy)</div>
            {Object.entries(c.risk_policy).map(([k, v]) => <Row key={k} k={k} v={String(v)} />)}
            <div className="text-[11px] text-subink mt-2">行业/市值集中度待 industry_map 入湖。</div>
          </div>

          {/* AI 模型 + 服务状态 */}
          <div className="card">
            <div className="text-sm font-medium mb-2">AI 模型 & 服务状态</div>
            <Row k="Agent 模式" v={c.ai_model.mode} />
            <Row k="LLM 已接入" v={c.ai_model.llm_ready ? "是" : "否(设 ANTHROPIC_API_KEY)"} />
            <Row k="数据隔离区间" v={c.quarantine_ranges} />
            <div className="mt-2 space-y-1">
              {c.services.map((s) => (
                <div key={s.name} className="flex items-center gap-2 text-[12px]">
                  <span className={`inline-block w-1.5 h-1.5 rounded-full ${s.status.includes("正常") || s.status.includes("接入") ? "bg-ok" : "bg-warn"}`} />
                  <span className="text-subink">{s.name}</span>
                  <span className="text-ink ml-auto">{s.status}</span>
                </div>
              ))}
            </div>
          </div>

          {/* 审计日志 */}
          <div className="card md:col-span-2">
            <div className="text-sm font-medium mb-2">审计日志(关键动作 · {audit?.total ?? 0} 条)</div>
            <table className="w-full text-[13px]">
              <thead>
                <tr className="text-subink text-left border-b border-cardline">
                  <th className="py-1 font-medium">类型</th>
                  <th className="py-1 font-medium">动作</th>
                  <th className="py-1 font-medium">详情</th>
                  <th className="py-1 font-medium">执行方</th>
                  <th className="py-1 font-medium">状态</th>
                </tr>
              </thead>
              <tbody>
                {audit?.entries.map((e, i) => (
                  <tr key={i} className="border-b border-cardline/60">
                    <td className="py-1"><span className="text-[11px] px-1.5 py-0.5 rounded bg-bg border border-cardline text-subink">{e.kind}</span></td>
                    <td className="py-1 text-ink">{e.summary}</td>
                    <td className="py-1 text-subink truncate max-w-[260px]">{e.detail}</td>
                    <td className="py-1 text-subink">{e.actor}</td>
                    <td className="py-1 text-subink">{e.status}</td>
                  </tr>
                ))}
                {!audit?.entries.length && <tr><td colSpan={5} className="py-2 text-subink">暂无审计记录</td></tr>}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
