"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import StatusBanner from "@/components/ui/StatusBanner";
import ResearchNav from "@/components/research/ResearchNav";
import WorkItemBadge from "@/components/research/WorkItemBadge";
import { api } from "@/lib/api";
import { actionLabel, sourceLabel } from "@/lib/researchWorkspace.mjs";
import type { ResearchWorkItemListView, ResearchWorkItemView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";

const JOB_TIMEOUT_MS = 15 * 60 * 1000;

export default function ExperimentsPage() {
  const [data, setData] = useState<ResearchWorkItemListView | null>(null);
  const [selectedId, setSelectedId] = useState("");
  const [showArchive, setShowArchive] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const setContext = useAgent((s) => s.setContext);

  const load = useCallback(async () => {
    try {
      const next = await api.researchWorkItems(
        showArchive
          ? { limit: 2000 }
          : { status: "review,blocked,ready,running", limit: 200 },
      );
      setData(next);
      setSelectedId((current) => current || next.items.find((item) => !["completed", "archived"].includes(item.status))?.work_id || next.items[0]?.work_id || "");
      setError("");
      setContext({
        page: "experiments",
        title: "研究工作队列",
        summary: `待复核 ${next.counts.review ?? 0}，阻塞 ${next.counts.blocked ?? 0}，可执行 ${next.counts.ready ?? 0}，运行中 ${next.counts.running ?? 0}。`,
        evidence: next.items.slice(0, 5).map((item) => `${item.title}: ${actionLabel(item.next_action)}`),
        recommendation: ["先处理人工复核与阻塞项", "所有正式晋级必须留下批准记录"],
        nextActions: ["处理队列中的唯一下一步"],
      });
    } catch (e) {
      setError(String(e));
    }
  }, [setContext, showArchive]);

  useEffect(() => { load(); }, [load]);

  const visible = useMemo(
    () => (data?.items ?? []).filter((item) => showArchive || !["completed", "archived"].includes(item.status)),
    [data, showArchive],
  );
  const selected = (data?.items ?? []).find((item) => item.work_id === selectedId) ?? visible[0] ?? null;

  async function execute(item: ResearchWorkItemView) {
    if (!item.next_action || ["review", "complete_draft"].includes(item.next_action)) return;
    setBusy(item.work_id);
    setError("");
    try {
      const job = await api.runResearchAction(item.kind, item.item_id, item.next_action, {});
      await api.waitForExperimentJob(job.job_id, { timeoutMs: JOB_TIMEOUT_MS });
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy("");
    }
  }

  async function launch(mode: "seed" | "llm" | "island") {
    setBusy(`create:${mode}`);
    setError("");
    try {
      const job = mode === "seed"
        ? await api.runAutoresearchSeeds({ limit: 5, max_stage: "l1" })
        : mode === "llm"
          ? await api.runAutoresearchLLM({ n: 5, max_stage: "l1" })
          : await api.runIslandSearch({ islands: 4, generations: 3, population: 8 });
      await api.waitForExperimentJob(job.job_id, { timeoutMs: JOB_TIMEOUT_MS });
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy("");
    }
  }

  const counts = data?.counts;
  const review = counts?.review ?? 0;
  const blocked = counts?.blocked ?? 0;
  const ready = counts?.ready ?? 0;
  const running = counts?.running ?? 0;
  const queueStatus: "ready" | "attention" | "neutral" =
    review > 0 || blocked > 0 ? "attention" : ready > 0 || running > 0 ? "ready" : "neutral";
  const queueTitle =
    review > 0
      ? `研究队列:${review} 项待人工复核(最高优先)`
      : blocked > 0
      ? `研究队列:${blocked} 项阻塞待排查失败原因`
      : ready > 0
      ? `研究队列:${ready} 项可执行`
      : running > 0
      ? `研究队列:${running} 项运行中`
      : "研究队列:空闲,无待办";

  return (
    <div className="space-y-5">
      <PageHeader title="研究实验室" desc="登记前工作台：研究素材 → 草案/候选 → L0–L3 → 人工复核 → 正式晋级" />
      <ResearchNav />

      {error && <div className="card text-sm text-danger">{error}</div>}

      {/* 研究队列态势头条:不复述计数,给优先级裁决 + 工作流纪律(§0.A 顺序 / 晋级须留批准记录) */}
      {data && (
        <StatusBanner
          status={queueStatus}
          title={queueTitle}
          detail="处理顺序:待复核 → 阻塞 → 可执行 → 运行中 · 正式晋级须留人工批准记录"
        />
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard label="待人工复核" value={String(data?.counts.review ?? 0)} tone="warn" sub="需要明确批准或拒绝" />
        <MetricCard label="失败 / 阻塞" value={String(data?.counts.blocked ?? 0)} tone="danger" sub="优先处理失败原因" />
        <MetricCard label="可执行" value={String(data?.counts.ready ?? 0)} tone="ok" sub="已有唯一下一步" />
        <MetricCard label="运行中" value={String(data?.counts.running ?? 0)} sub="异步 Job 执行" />
      </div>

      <div className="flex items-center justify-between gap-3">
        <label className="text-[11px] text-subink flex items-center gap-2">
          <input type="checkbox" checked={showArchive} onChange={(e) => setShowArchive(e.target.checked)} />
          显示已登记 / 已归档
        </label>
        <details className="relative">
          <summary className="list-none cursor-pointer px-3 py-1.5 rounded-lg bg-brand text-white text-[12px] font-semibold">创建研究任务</summary>
          <div className="absolute right-0 mt-2 z-20 w-56 bg-white border border-line rounded-xl shadow-lg p-2 space-y-1">
            <Link href="/experiments/evidence" className="block px-3 py-2 rounded hover:bg-jilan text-[12px]">从研报证据创建草案</Link>
            <button onClick={() => launch("seed")} className="w-full text-left px-3 py-2 rounded hover:bg-jilan text-[12px]" disabled={!!busy}>运行确定性种子</button>
            <button onClick={() => launch("llm")} className="w-full text-left px-3 py-2 rounded hover:bg-jilan text-[12px]" disabled={!!busy}>LLM 生成候选</button>
            <button onClick={() => launch("island")} className="w-full text-left px-3 py-2 rounded hover:bg-jilan text-[12px]" disabled={!!busy}>岛屿搜索</button>
          </div>
        </details>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        <div className="lg:col-span-3 card overflow-hidden p-0">
          <div className="px-4 py-3 border-b border-line text-sm font-semibold">优先处理队列</div>
          <div className="overflow-x-auto max-h-[620px]">
            <table className="w-full text-[12px]">
              <thead className="sticky top-0 bg-jilan text-subink text-left">
                <tr><th className="px-3 py-2">研究对象</th><th className="px-3 py-2">来源</th><th className="px-3 py-2">阶段</th><th className="px-3 py-2">下一步</th></tr>
              </thead>
              <tbody>
                {visible.map((item) => (
                  <tr
                    key={item.work_id}
                    onClick={() => setSelectedId(item.work_id)}
                    className={`border-t border-line/50 cursor-pointer ${selected?.work_id === item.work_id ? "bg-brand/8" : "hover:bg-jilan/20"}`}
                  >
                    <td className="px-3 py-3">
                      <div className="font-semibold text-ink">{item.title}</div>
                      <div className="mt-1"><WorkItemBadge status={item.status} /></div>
                    </td>
                    <td className="px-3 py-3 text-subink">{sourceLabel(item.source)}</td>
                    <td className="px-3 py-3 font-mono text-subink">{item.stage.toUpperCase()}</td>
                    <td className="px-3 py-3 text-brand font-medium">{actionLabel(item.next_action)}</td>
                  </tr>
                ))}
                {visible.length === 0 && <tr><td colSpan={4} className="px-3 py-8 text-center text-subink">当前队列为空</td></tr>}
              </tbody>
            </table>
          </div>
        </div>

        <div className="lg:col-span-2 card h-fit lg:sticky lg:top-5">
          {selected ? (
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-bold text-ink">{selected.title}</h2>
                  <div className="text-[11px] text-subink mt-1">{selected.work_id}</div>
                </div>
                <WorkItemBadge status={selected.status} />
              </div>
              <div className="space-y-2 text-[12px]">
                <div><span className="text-subink">经济假设：</span>{selected.mechanism || "未填写"}</div>
                <div><span className="text-subink">证据来源：</span>{selected.citation || sourceLabel(selected.source)}</div>
                <div><span className="text-subink">当前阶段：</span>{selected.stage.toUpperCase()}</div>
                <div><span className="text-subink">当前风险：</span>{selected.blocked_reason || selected.latest_result?.reason || "暂无阻塞"}</div>
                <div><span className="text-subink">唯一下一步：</span><strong>{actionLabel(selected.next_action)}</strong></div>
              </div>
              {selected.next_action === "review" ? (
                <Link href="/experiments/reviews" className="block text-center px-4 py-2 rounded-lg bg-brand text-white text-sm font-semibold">进入人工复核</Link>
              ) : selected.next_action === "complete_draft" ? (
                <Link href={`/experiments/${selected.kind}/${selected.item_id}`} className="block text-center px-4 py-2 rounded-lg bg-brand text-white text-sm font-semibold">补全研究草案</Link>
              ) : selected.next_action ? (
                <button onClick={() => execute(selected)} disabled={busy === selected.work_id} className="w-full px-4 py-2 rounded-lg bg-brand text-white text-sm font-semibold disabled:opacity-50">
                  {busy === selected.work_id ? "执行中…" : actionLabel(selected.next_action)}
                </button>
              ) : null}
              <Link href={`/experiments/${selected.kind}/${selected.item_id}`} className="block text-center text-[12px] text-brand hover:underline">查看完整研究档案</Link>
            </div>
          ) : <div className="text-sm text-subink">选择一个研究对象查看详情。</div>}
        </div>
      </div>
    </div>
  );
}
