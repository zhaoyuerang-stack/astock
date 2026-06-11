"use client";

import { useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import { api } from "@/lib/api";
import type { AgentAskResponse } from "@/lib/types";

const QUICK = ["当前数据质量怎么样", "风控评估如何", "组合现在什么状态", "假设池漏斗", "帮我降仓调仓", "跑一下回测"];

interface Turn {
  q: string;
  r: AgentAskResponse;
}

export default function AgentWorkbench() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);

  async function send(text?: string) {
    const request = (text ?? q).trim();
    if (!request || loading) return;
    setLoading(true);
    try {
      const r = await api.agentAsk(request, { current_page: "agent" });
      setTurns((t) => [{ q: request, r }, ...t]);
      setQ("");
    } catch (e) {
      alert(`调用失败:${String(e)}`);
    } finally {
      setLoading(false);
    }
  }

  const llmReady = turns[0]?.r.llm_ready ?? false;

  return (
    <div>
      <PageHeader title="AI 研究助手" desc="Agent 主工作台 · 工具调用 + 不越权分级 + 结构化产出" />

      <div className="card mb-4">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium">研究对话</span>
          <span className="text-[11px] px-1.5 py-0.5 rounded border border-cardline text-subink">
            {llmReady ? "LLM 已接入" : "规则式(给 ANTHROPIC_API_KEY 即接真 LLM)"}
          </span>
        </div>
        <div className="flex gap-1.5">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send()}
            placeholder="问研究助手…"
            className="flex-1 text-sm bg-bg border border-cardline rounded-lg px-3 py-2 outline-none focus:border-brand"
          />
          <button onClick={() => send()} disabled={loading} className="text-sm bg-brand text-white rounded-lg px-4 disabled:opacity-50">
            {loading ? "…" : "发送"}
          </button>
        </div>
        <div className="flex flex-wrap gap-1.5 mt-2">
          {QUICK.map((c) => (
            <button key={c} onClick={() => send(c)} className="text-[12px] px-2 py-1 rounded bg-bg border border-cardline text-subink">
              {c}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        {turns.map((t, i) => {
          const o = t.r.output;
          return (
            <div key={i} className="card">
              <div className="flex items-center justify-between">
                <span className="text-[13px] text-ink font-medium">{t.q}</span>
                <span className="text-[11px] text-subink">
                  工具:{t.r.tool ?? "—"} · {t.r.risk ?? "readonly"} · 置信 {(o.confidence * 100).toFixed(0)}%
                </span>
              </div>
              <div className="text-[13px] text-ink mt-2 leading-relaxed">{o.summary}</div>
              {o.requires_human_confirmation && (
                <div className="mt-2 text-[12px] text-warn border border-cardline rounded p-2">
                  ⚠️ 该动作需人工二次确认 —— Agent 不自动执行(SPEC §9.2 不越权)。
                </div>
              )}
              {o.evidence.length > 0 && (
                <div className="mt-2 text-[12px] text-subink">证据:{o.evidence.join(" · ")}</div>
              )}
              {o.risk.length > 0 && (
                <div className="mt-1 text-[12px] text-danger">风险:{o.risk.join(" · ")}</div>
              )}
              {o.recommendation.length > 0 && (
                <div className="mt-1 text-[12px] text-ink">建议:{o.recommendation.join(" · ")}</div>
              )}
            </div>
          );
        })}
        {turns.length === 0 && <div className="card text-sm text-subink">点上方快捷指令试试。注意:回测/调仓会被标为需人工确认,不自动执行。</div>}
      </div>
    </div>
  );
}
