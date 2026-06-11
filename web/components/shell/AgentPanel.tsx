"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { useAgent } from "@/lib/agentStore";
import { api } from "@/lib/api";

function Section({ title, items, tone }: { title: string; items: string[]; tone?: string }) {
  if (!items?.length) return null;
  return (
    <div className="mt-3">
      <div className="text-[11px] font-medium text-subink uppercase tracking-wide">{title}</div>
      <ul className="mt-1 space-y-1">
        {items.map((t, i) => (
          <li key={i} className={`text-[13px] leading-snug ${tone ?? "text-ink"}`}>• {t}</li>
        ))}
      </ul>
    </div>
  );
}

export default function AgentPanel() {
  const ctx = useAgent((s) => s.ctx);
  const setContext = useAgent((s) => s.setContext);
  const pathname = usePathname();
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [llmReady, setLlmReady] = useState(false);
  const [confirmTip, setConfirmTip] = useState<string | null>(null);

  async function ask() {
    const request = q.trim();
    if (!request || loading) return;
    setLoading(true);
    setConfirmTip(null);
    try {
      const page = pathname.replace(/^\//, "") || "overview";
      const r = await api.agentAsk(request, { current_page: page });
      setLlmReady(r.llm_ready);
      const o = r.output;
      setContext({
        page,
        title: "研究副驾驶",
        summary: o.summary,
        evidence: o.evidence,
        risk: o.risk,
        recommendation: o.recommendation,
        nextActions: o.next_actions,
      });
      if (o.requires_human_confirmation) {
        setConfirmTip(`「${r.tool}」为${r.risk}风险动作,Agent 不自动执行,需你在对应页面手动确认。`);
      }
      setQ("");
    } catch (e) {
      setContext({ page: "", title: "研究副驾驶", summary: `调用失败:${String(e)}(确认后端 :8011)` });
    } finally {
      setLoading(false);
    }
  }

  return (
    <aside className="w-[320px] shrink-0 border-l border-cardline bg-white h-screen sticky top-0 flex flex-col">
      <div className="px-4 py-4 border-b border-cardline">
        <div className="flex items-center justify-between">
          <div className="text-sm font-semibold">AI 研究副驾驶</div>
          <span className="text-[10px] px-1.5 py-0.5 rounded border border-cardline text-subink">
            {llmReady ? "LLM" : "规则式"}
          </span>
        </div>
        <div className="text-[11px] text-subink mt-0.5">{ctx.title}</div>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3">
        <div className="text-[13px] text-ink leading-relaxed whitespace-pre-wrap">{loading ? "思考中…" : ctx.summary}</div>
        <Section title="证据" items={ctx.evidence} tone="text-subink" />
        <Section title="风险" items={ctx.risk} tone="text-danger" />
        <Section title="建议" items={ctx.recommendation} />
        <Section title="下一步" items={ctx.nextActions} tone="text-brand" />
        {confirmTip && <div className="mt-3 text-[12px] text-warn border border-cardline rounded p-2">{confirmTip}</div>}
      </div>
      <div className="px-4 py-3 border-t border-cardline">
        <div className="text-[10px] text-subink mb-1.5">
          研究辅助内容,不构成投资建议 · 给 ANTHROPIC_API_KEY 即接真 LLM
        </div>
        <div className="flex gap-1.5">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ask()}
            placeholder="问:数据质量 / 风控 / 组合 / 实验…"
            className="flex-1 text-sm bg-bg border border-cardline rounded-lg px-3 py-1.5 outline-none focus:border-brand"
          />
          <button onClick={ask} disabled={loading} className="text-sm bg-brand text-white rounded-lg px-3 disabled:opacity-50">
            问
          </button>
        </div>
      </div>
    </aside>
  );
}
