"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import ResearchNav from "@/components/research/ResearchNav";
import WorkItemBadge from "@/components/research/WorkItemBadge";
import { api } from "@/lib/api";
import { actionLabel, sourceLabel } from "@/lib/researchWorkspace.mjs";
import type { ResearchWorkItemView } from "@/lib/types";

export default function ResearchReviewsPage() {
  const [items, setItems] = useState<ResearchWorkItemView[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(() => api.researchWorkItems({ action: "review,promote", limit: 500 })
    .then((data) => setItems(data.items))
    .catch((e) => setError(String(e))), []);
  useEffect(() => { load(); }, [load]);

  const reviewItems = useMemo(
    () => items.filter((item) => item.status === "review" || item.next_action === "promote"),
    [items],
  );

  async function review(item: ResearchWorkItemView, action: "approve" | "reject") {
    setBusy(item.work_id);
    setError("");
    try {
      await api.reviewResearchWorkItem(item.kind, item.item_id, action, notes[item.work_id] ?? "");
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy("");
    }
  }

  async function promote(item: ResearchWorkItemView) {
    setBusy(item.work_id);
    setError("");
    try {
      const job = await api.runResearchAction(item.kind, item.item_id, "promote", { target_status: "SHADOW" });
      await api.waitForExperimentJob(job.job_id, { timeoutMs: 15 * 60 * 1000 });
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader title="人工复核" desc="批准、拒绝与正式晋级统一留痕；未批准对象不能进入 workflow.promote" />
      <ResearchNav />
      {error && <div className="card text-sm text-danger">{error}</div>}
      <div className="space-y-4">
        {reviewItems.map((item) => (
          <div key={item.work_id} className="card grid grid-cols-1 lg:grid-cols-4 gap-4">
            <div className="lg:col-span-2">
              <div className="flex items-center gap-2"><h2 className="font-bold text-ink">{item.title}</h2><WorkItemBadge status={item.status} /></div>
              <div className="text-[11px] text-subink mt-1">{sourceLabel(item.source)} · {item.work_id}</div>
              <p className="text-[12px] mt-3">{item.mechanism || "未填写经济假设"}</p>
              <p className="text-[11px] text-subink mt-2">{item.citation || "无引用"}</p>
            </div>
            <div>
              <textarea
                value={notes[item.work_id] ?? ""}
                onChange={(e) => setNotes((prev) => ({ ...prev, [item.work_id]: e.target.value }))}
                placeholder="复核意见"
                className="w-full h-24 rounded-lg border border-line p-2 text-[12px]"
                disabled={item.next_action === "promote"}
              />
            </div>
            <div className="flex flex-col justify-center gap-2">
              {item.next_action === "promote" ? (
                <button onClick={() => promote(item)} disabled={busy === item.work_id} className="px-3 py-2 rounded-lg bg-brand text-white text-[12px] font-semibold disabled:opacity-50">{busy === item.work_id ? "晋级中…" : actionLabel("promote")}</button>
              ) : (
                <>
                  <button onClick={() => review(item, "approve")} disabled={busy === item.work_id} className="px-3 py-2 rounded-lg bg-songshi text-white text-[12px] font-semibold disabled:opacity-50">批准</button>
                  <button onClick={() => review(item, "reject")} disabled={busy === item.work_id} className="px-3 py-2 rounded-lg border border-danger/40 text-danger text-[12px] font-semibold disabled:opacity-50">拒绝</button>
                </>
              )}
            </div>
          </div>
        ))}
        {reviewItems.length === 0 && <div className="card text-sm text-subink">暂无待复核或待晋级对象。</div>}
      </div>
    </div>
  );
}
