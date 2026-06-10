"use client";

import { useAgent } from "@/lib/agentStore";

function Section({ title, items, tone }: { title: string; items: string[]; tone?: string }) {
  if (!items.length) return null;
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
  return (
    <aside className="w-[320px] shrink-0 border-l border-cardline bg-white h-screen sticky top-0 flex flex-col">
      <div className="px-4 py-4 border-b border-cardline">
        <div className="text-sm font-semibold">AI 研究副驾驶</div>
        <div className="text-[11px] text-subink mt-0.5">{ctx.title}</div>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3">
        <div className="text-[13px] text-ink leading-relaxed">{ctx.summary}</div>
        <Section title="证据" items={ctx.evidence} tone="text-subink" />
        <Section title="风险" items={ctx.risk} tone="text-danger" />
        <Section title="建议" items={ctx.recommendation} />
        <Section title="下一步" items={ctx.nextActions} tone="text-brand" />
      </div>
      <div className="px-4 py-3 border-t border-cardline">
        <div className="text-[10px] text-subink mb-1.5">
          研究辅助内容,不构成投资建议 · Phase 5 接入真 Agent
        </div>
        <input
          disabled
          placeholder="向 Agent 提问(Phase 5)…"
          className="w-full text-sm bg-bg border border-cardline rounded-lg px-3 py-1.5 outline-none disabled:opacity-60"
        />
      </div>
    </aside>
  );
}
