"use client";

import { useCallback, useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import { api, pct } from "@/lib/api";
import type { SystemConfigView, AuditView, LLMConfigView, LLMTestResult } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

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

  // LLM 配置表单
  const [llm, setLlm] = useState<LLMConfigView | null>(null);
  const [form, setForm] = useState({ provider: "none", model: "", base_url: "", api_key: "" });
  const [saving, setSaving] = useState(false);
  const [test, setTest] = useState<LLMTestResult | null>(null);

  function loadLlm() {
    api.getLlmConfig().then((l) => {
      setLlm(l);
      setForm({ provider: l.provider, model: l.model, base_url: l.base_url, api_key: "" });
    }).catch(() => {});
  }

  async function saveLlm() {
    setSaving(true); setTest(null);
    try {
      // api_key 留空 = 保留原 key(不覆盖)
      const body = { ...form, api_key: form.api_key ? form.api_key : null };
      const l = await api.setLlmConfig(body);
      setLlm(l); setForm({ provider: l.provider, model: l.model, base_url: l.base_url, api_key: "" });
      api.systemConfig().then(setC);
    } finally { setSaving(false); }
  }

  async function testLlm() {
    setTest(null);
    try { setTest(await api.testLlm()); } catch (e) { setTest({ ok: false, message: String(e) }); }
  }

  // LLM 配置只在挂载时拉一次:轮询会重置表单,覆盖正在编辑的输入
  useEffect(() => {
    loadLlm();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const load = useCallback(() => {
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
  useAutoRefresh(load);

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
            <Row k="Provider" v={c.ai_model.provider || "none"} />
            {c.ai_model.model && <Row k="模型" v={c.ai_model.model} />}
            <Row k="LLM 已接入" v={c.ai_model.llm_ready ? "是" : "否(settings.yaml::ai_model 配 provider+key)"} />
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

          {/* LLM 模型配置(可填 Key / 接入点)*/}
          <div className="card md:col-span-2">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium">AI 模型配置(填 Provider / 接入点 / API Key)</span>
              <span className="text-[11px] px-1.5 py-0.5 rounded border border-cardline text-subink">
                {llm?.llm_ready ? "已接入 LLM" : "规则式"}
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <label className="text-[12px] text-subink">Provider
                <select value={form.provider} onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value }))}
                  className="mt-1 w-full text-sm border border-cardline rounded-lg px-2 py-1.5 outline-none focus:border-brand bg-white">
                  <option value="none">none(规则式)</option>
                  <option value="openai_compatible">openai_compatible(DeepSeek/Qwen/Kimi/GLM/Ollama/OpenAI)</option>
                  <option value="anthropic">anthropic(Claude)</option>
                </select>
              </label>
              <label className="text-[12px] text-subink">模型
                <input value={form.model} onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))} placeholder="deepseek-chat / claude-opus-4-8"
                  className="mt-1 w-full text-sm border border-cardline rounded-lg px-2 py-1.5 outline-none focus:border-brand" />
              </label>
              <label className="text-[12px] text-subink">接入点 base_url
                <input value={form.base_url} onChange={(e) => setForm((f) => ({ ...f, base_url: e.target.value }))} placeholder="https://api.deepseek.com/v1"
                  className="mt-1 w-full text-sm border border-cardline rounded-lg px-2 py-1.5 outline-none focus:border-brand" />
              </label>
              <label className="text-[12px] text-subink">API Key {llm?.has_key && <span className="text-ok">(已设置 {llm.key_hint})</span>}
                <input type="password" value={form.api_key} onChange={(e) => setForm((f) => ({ ...f, api_key: e.target.value }))}
                  placeholder={llm?.has_key ? "留空=保留原 key" : "粘贴 key"}
                  className="mt-1 w-full text-sm border border-cardline rounded-lg px-2 py-1.5 outline-none focus:border-brand" />
              </label>
            </div>
            <div className="mt-3 flex items-center gap-2 flex-wrap">
              <button onClick={saveLlm} disabled={saving} className="text-sm bg-brand text-white rounded-lg px-4 py-1.5 disabled:opacity-50">{saving ? "保存中…" : "保存"}</button>
              <button onClick={testLlm} className="text-sm border border-cardline rounded-lg px-4 py-1.5 text-ink">测试连接</button>
              {test && <span className={`text-[12px] ${test.ok ? "text-ok" : "text-danger"}`}>{test.ok ? "✓ " : "✗ "}{test.message}</span>}
            </div>
            <div className="text-[11px] text-subink mt-2">Key 存本地 gitignored 文件(不进 git、不回传明文);LLM 只做路由/解读,永不执行下单(不越权门照常)。</div>
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
