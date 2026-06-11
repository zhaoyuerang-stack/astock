"use client";

import { useCallback, useEffect, useState } from "react";
import MetricCard from "@/components/ui/MetricCard";
import { api, num } from "@/lib/api";
import type {
  AutoResearchCandidateView,
  AutoResearchFunnelView,
  AutoResearchIslandSearchResponse,
  AutoResearchPromoteResponse,
  AutoResearchReviewItemView,
  AutoResearchRunResponse,
} from "@/lib/types";
import { useAgent } from "@/lib/agentStore";

const STATUS_LABEL: Record<string, string> = {
  generated: "生成",
  l0_passed: "L0",
  l1_passed: "L1",
  l2_passed: "L2",
  l3_passed: "L3",
  shelved: "搁置",
  discarded: "淘汰",
  promoted_to_review: "待复核",
  approved: "已批准",
  rejected_by_human: "人工拒绝",
  retired: "退役",
};

const MAIN_STAGES = ["generated", "l0_passed", "l1_passed", "l2_passed", "l3_passed", "promoted_to_review"];
const SIDE_STAGES = ["shelved", "discarded", "approved", "rejected_by_human", "retired"];
const RUN_STAGES = ["l0", "l1", "l2", "l3"] as const;

function statusTone(status: string): string {
  if (status === "discarded" || status === "rejected_by_human") return "text-danger";
  if (status === "shelved" || status === "retired") return "text-warn";
  if (status === "promoted_to_review" || status === "approved") return "text-ok";
  return "text-ink";
}

interface AstTerm {
  factor?: string;
  params?: Record<string, unknown>;
  weight?: number;
}

function astSummary(ast: Record<string, unknown>): string {
  const terms = (ast.terms as AstTerm[] | undefined) ?? [];
  const expr = terms
    .map((t) => {
      const w = t.params?.window;
      return `${t.factor ?? "?"}${w != null ? `(${w})` : ""}×${t.weight ?? 1}`;
    })
    .join(" + ");
  return ast.direction === "negative" ? `-(${expr})` : expr;
}

export default function AutoResearchLab() {
  const [funnel, setFunnel] = useState<AutoResearchFunnelView | null>(null);
  const [candidates, setCandidates] = useState<AutoResearchCandidateView[]>([]);
  const [queue, setQueue] = useState<AutoResearchReviewItemView[]>([]);
  const [err, setErr] = useState<string | null>(null);

  const [runLimit, setRunLimit] = useState(5);
  const [runStage, setRunStage] = useState<(typeof RUN_STAGES)[number]>("l1");
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<AutoResearchRunResponse | null>(null);
  const [runErr, setRunErr] = useState<string | null>(null);

  const [reviewTarget, setReviewTarget] = useState<{ fingerprint: string; action: "approve" | "reject" } | null>(null);
  const [reviewNotes, setReviewNotes] = useState("");
  const [reviewBusy, setReviewBusy] = useState(false);
  const [reviewErr, setReviewErr] = useState<string | null>(null);

  const [llmN, setLlmN] = useState(5);
  const [llmTheme, setLlmTheme] = useState("");
  const [llmBusy, setLlmBusy] = useState(false);
  const [llmInfo, setLlmInfo] = useState<{ model: string; accepted: number; rejected: string[] } | null>(null);
  const [islandBusy, setIslandBusy] = useState(false);
  const [islandResult, setIslandResult] = useState<AutoResearchIslandSearchResponse | null>(null);
  const [searchErr, setSearchErr] = useState<string | null>(null);
  const [promoteBusy, setPromoteBusy] = useState<string | null>(null);
  const [promoteResults, setPromoteResults] = useState<Record<string, AutoResearchPromoteResponse>>({});
  const [promoteErr, setPromoteErr] = useState<string | null>(null);
  const setContext = useAgent((s) => s.setContext);

  const reload = useCallback(() => {
    return Promise.all([api.autoresearchFunnel(), api.autoresearchCandidates(60), api.autoresearchReviewQueue(20)])
      .then(([f, c, q]) => {
        setFunnel(f);
        setCandidates(c);
        setQueue(q);
        setErr(null);
        return f;
      })
      .catch((e) => {
        setErr(String(e));
        return null;
      });
  }, []);

  useEffect(() => {
    reload().then((f) => {
      if (!f) return;
      const discarded = f.stages.find((s) => s.stage === "discarded")?.count ?? 0;
      const shelved = f.stages.find((s) => s.stage === "shelved")?.count ?? 0;
      setContext({
        page: "experiments",
        title: "AutoResearch 实验室",
        summary: `受控 DSL 候选 ${f.total} 个:淘汰 ${discarded}、搁置 ${shelved}、待人工复核 ${f.review_queue}。promote 只进复核队列,不写台账。`,
        evidence: f.stages.filter((s) => s.count > 0).map((s) => `${STATUS_LABEL[s.stage] ?? s.stage}: ${s.count}`),
        recommendation: ["候选走真实 L0-L3 数据湖闸门(真实成本口径)", "高淘汰率是闸门在证伪,属健康信号"],
        nextActions: ["运行种子候选验证", "复核队列等待 approve/reject 工作台"],
      });
    });
  }, [reload, setContext]);

  const runSeeds = () => {
    setRunning(true);
    setRunErr(null);
    setRunResult(null);
    api
      .runAutoresearchSeeds({ limit: runLimit, max_stage: runStage })
      .then((r) => {
        setRunResult(r);
        return reload();
      })
      .catch((e) => setRunErr(String(e)))
      .finally(() => setRunning(false));
  };

  const runLLM = () => {
    setLlmBusy(true);
    setSearchErr(null);
    setLlmInfo(null);
    api
      .runAutoresearchLLM({ n: llmN, theme: llmTheme, max_stage: runStage })
      .then((r) => {
        setLlmInfo({ model: r.model, accepted: r.accepted, rejected: r.rejected });
        setRunResult(r.run);
        return reload();
      })
      .catch((e) => setSearchErr(String(e)))
      .finally(() => setLlmBusy(false));
  };

  const runIslands = () => {
    setIslandBusy(true);
    setSearchErr(null);
    setIslandResult(null);
    api
      .runIslandSearch({ islands: 4, generations: 3, population: 8 })
      .then((r) => {
        setIslandResult(r);
        return reload();
      })
      .catch((e) => setSearchErr(String(e)))
      .finally(() => setIslandBusy(false));
  };

  const promoteCandidate = (fingerprint: string) => {
    setPromoteBusy(fingerprint);
    setPromoteErr(null);
    api
      .promoteAutoresearch(fingerprint)
      .then((r) => {
        setPromoteResults((prev) => ({ ...prev, [fingerprint]: r }));
        return reload();
      })
      .catch((e) => setPromoteErr(String(e)))
      .finally(() => setPromoteBusy(null));
  };

  const submitReview = () => {
    if (!reviewTarget) return;
    setReviewBusy(true);
    setReviewErr(null);
    api
      .reviewAutoresearch(reviewTarget.fingerprint, reviewTarget.action, reviewNotes)
      .then(() => {
        setReviewTarget(null);
        setReviewNotes("");
        return reload();
      })
      .catch((e) => setReviewErr(String(e)))
      .finally(() => setReviewBusy(false));
  };

  const maxCount = funnel ? Math.max(1, ...funnel.stages.map((s) => s.count)) : 1;
  const stageCount = (stage: string) => funnel?.stages.find((s) => s.stage === stage)?.count ?? 0;
  const pending = queue.filter((it) => !it.review_action);
  const decided = queue.filter((it) => it.review_action);

  return (
    <>
      {err && (
        <div className="card text-sm text-danger mb-4">
          API 错误:{err}
          <br />
          请确认后端已启动(uvicorn :8011)。
        </div>
      )}

      {funnel && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
            <MetricCard label="DSL 候选总数" value={String(funnel.total)} sub="受控 JSON AST · fingerprint 去重" />
            <MetricCard label="待人工复核" value={String(funnel.review_queue)} tone="ok" sub="promote 终点,不直接写台账" />
            <MetricCard label="已淘汰" value={String(stageCount("discarded"))} tone="danger" sub="真实 L0-L3 闸门证伪" />
            <MetricCard label="已搁置" value={String(stageCount("shelved"))} tone="warn" sub="L3 走样不稳 / 复杂度超预算" />
          </div>

          {/* 候选漏斗 */}
          <div className="card mb-5">
            <div className="text-sm font-medium mb-3">候选漏斗(生成 → 真实 L0~L3 → 人工复核)</div>
            <div className="flex items-end gap-2 h-32">
              {MAIN_STAGES.map((stage) => {
                const count = stageCount(stage);
                return (
                  <div key={stage} className="flex-1 flex flex-col items-center justify-end h-full">
                    <span className="text-[12px] text-ink mb-1">{count}</span>
                    <div
                      className="w-full rounded-t bg-brand"
                      style={{ height: `${(count / maxCount) * 100}%`, minHeight: count ? "4px" : "0" }}
                    />
                    <span className="text-[11px] text-subink mt-1">{STATUS_LABEL[stage]}</span>
                  </div>
                );
              })}
            </div>
            <div className="flex gap-4 mt-3 text-[12px] text-subink">
              {SIDE_STAGES.map((stage) => (
                <span key={stage}>
                  {STATUS_LABEL[stage]}:<span className="text-ink"> {stageCount(stage)}</span>
                </span>
              ))}
            </div>
          </div>

          {/* 运行种子候选 */}
          <div className="card mb-5">
            <div className="flex items-center justify-between mb-3">
              <div className="text-sm font-medium">运行种子候选(真实 data_lake 回测)</div>
              <div className="flex items-center gap-2 text-[12px]">
                <label className="text-subink">候选数</label>
                <input
                  type="number"
                  min={1}
                  max={36}
                  value={runLimit}
                  onChange={(e) => setRunLimit(Math.max(1, Math.min(36, Number(e.target.value) || 1)))}
                  className="w-14 px-1.5 py-1 rounded border border-cardline text-ink"
                  disabled={running}
                />
                <label className="text-subink ml-2">最深阶段</label>
                {RUN_STAGES.map((s) => (
                  <button
                    key={s}
                    onClick={() => setRunStage(s)}
                    disabled={running}
                    className={`px-2 py-1 rounded ${runStage === s ? "bg-brand text-white" : "bg-bg text-subink border border-cardline"}`}
                  >
                    {s.toUpperCase()}
                  </button>
                ))}
                <button
                  onClick={runSeeds}
                  disabled={running}
                  className="ml-3 px-3 py-1 rounded bg-brand text-white disabled:opacity-50"
                >
                  {running ? "运行中…" : "运行"}
                </button>
              </div>
            </div>
            <div className="text-[12px] text-subink mb-2">
              L0=IC 粗筛(秒级);L1~L3=真实成本回测,首次运行需加载数据湖(约 20s+,15 个候选全链路约 80s)。
            </div>
            <div className="flex items-center gap-2 text-[12px] mb-2 pt-2 border-t border-cardline/60">
              <label className="text-subink">LLM 生成</label>
              <input
                type="number" min={1} max={20} value={llmN}
                onChange={(e) => setLlmN(Math.max(1, Math.min(20, Number(e.target.value) || 1)))}
                className="w-14 px-1.5 py-1 rounded border border-cardline text-ink"
                disabled={llmBusy}
              />
              <input
                value={llmTheme} onChange={(e) => setLlmTheme(e.target.value)}
                placeholder="研究主题(可选,如:流动性溢价)"
                className="w-56 px-2 py-1 rounded border border-cardline text-ink"
                disabled={llmBusy}
              />
              <button onClick={runLLM} disabled={llmBusy || islandBusy || running}
                className="px-3 py-1 rounded bg-brand text-white disabled:opacity-50">
                {llmBusy ? "生成验证中…" : "LLM 生成并验证"}
              </button>
              <button onClick={runIslands} disabled={llmBusy || islandBusy || running}
                className="ml-2 px-3 py-1 rounded bg-navy text-white disabled:opacity-50"
                title="4 岛 × 3 代 × 8 个体,适应度=真实 L0 |ICIR|,LLM 可用时按主题播种">
                {islandBusy ? "岛屿搜索中…" : "岛屿搜索(分钟级)"}
              </button>
            </div>
            {searchErr && <div className="text-sm text-danger mb-2">失败:{searchErr}</div>}
            {llmInfo && (
              <div className="text-[12px] text-subink mb-2">
                LLM <span className="font-mono">{llmInfo.model}</span> · 通过白名单校验 <span className="text-ink">{llmInfo.accepted}</span> 个
                {llmInfo.rejected.length > 0 && (
                  <span> · 拒绝 {llmInfo.rejected.length} 个:<span className="text-warn">{llmInfo.rejected.join(";")}</span></span>
                )}
              </div>
            )}
            {islandResult && (
              <div className="mb-2">
                <div className="text-[12px] text-subink mb-1">
                  岛屿搜索:{islandResult.islands} 岛 × {islandResult.generations} 代,真实 L0 评估 {islandResult.evaluated} 次,
                  播种来源 {islandResult.seeded_by === "llm" ? "LLM" : "确定性种子"} · 冠军:
                </div>
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="text-subink text-left border-b border-cardline">
                      <th className="py-1 font-medium">岛</th>
                      <th className="py-1 font-medium text-right">|ICIR|</th>
                      <th className="py-1 font-medium">表达式</th>
                      <th className="py-1 font-medium">状态</th>
                      <th className="py-1 font-medium">原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {islandResult.champions.map((c) => (
                      <tr key={c.fingerprint} className="border-b border-cardline/60">
                        <td className="py-1 text-subink">#{c.island}</td>
                        <td className="py-1 text-right text-ink">{num(Math.abs(c.icir), 3)}</td>
                        <td className="py-1 text-ink">{c.expr}</td>
                        <td className={`py-1 ${statusTone(c.status)}`}>{STATUS_LABEL[c.status] ?? c.status}</td>
                        <td className="py-1 text-subink truncate max-w-[260px]" title={c.reason}>{c.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {runErr && <div className="text-sm text-danger">运行失败:{runErr}</div>}
            {runResult && (
              <div className="overflow-x-auto">
                <div className="text-[12px] text-subink mb-1">
                  vintage: <span className="font-mono">{runResult.vintage_id}</span> · max_stage: {runResult.max_stage.toUpperCase()}
                </div>
                <table className="w-full text-[13px]">
                  <thead>
                    <tr className="text-subink text-left border-b border-cardline">
                      <th className="py-1.5 font-medium">fingerprint</th>
                      <th className="py-1.5 font-medium">已跑阶段</th>
                      <th className="py-1.5 font-medium">状态</th>
                      <th className="py-1.5 font-medium">原因</th>
                    </tr>
                  </thead>
                  <tbody>
                    {runResult.results.map((r) => (
                      <tr key={r.fingerprint} className="border-b border-cardline/60">
                        <td className="py-1.5 font-mono text-[11px] text-subink">{r.fingerprint.slice(0, 10)}</td>
                        <td className="py-1.5 text-subink">{r.protocols.map((p) => p.replace(/_.*$/, "").toUpperCase()).join(" → ") || "—"}</td>
                        <td className={`py-1.5 ${statusTone(r.status)}`}>{STATUS_LABEL[r.status] ?? r.status}</td>
                        <td className="py-1.5 text-subink truncate max-w-[360px]" title={r.reason}>{r.reason}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* 人工复核工作台 */}
          <div className="card mb-5">
            <div className="text-sm font-medium mb-3">
              人工复核工作台(promote 终点 · approve 仍不写 LIVE 台账,入册走 workflow promote)
            </div>
            {reviewErr && <div className="text-sm text-danger mb-2">复核失败:{reviewErr}</div>}
            {reviewTarget && (
              <div className="flex items-center gap-2 mb-3 p-2 rounded bg-bg border border-cardline text-[13px]">
                <span className={reviewTarget.action === "approve" ? "text-ok" : "text-danger"}>
                  {reviewTarget.action === "approve" ? "批准" : "拒绝"}
                </span>
                <span className="font-mono text-[11px] text-subink">{reviewTarget.fingerprint.slice(0, 10)}</span>
                <input
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="复核意见(建议填写,进入审计)"
                  className="flex-1 px-2 py-1 rounded border border-cardline text-ink"
                  disabled={reviewBusy}
                />
                <button onClick={submitReview} disabled={reviewBusy}
                  className="px-3 py-1 rounded bg-brand text-white disabled:opacity-50">
                  {reviewBusy ? "提交中…" : "确认"}
                </button>
                <button onClick={() => { setReviewTarget(null); setReviewNotes(""); }} disabled={reviewBusy}
                  className="px-3 py-1 rounded bg-bg text-subink border border-cardline">
                  取消
                </button>
              </div>
            )}
            {pending.length === 0 ? (
              <div className="text-[13px] text-subink">
                待复核队列为空——尚无候选通过完整 L0~L3 闸门。高淘汰率是闸门在证伪,属健康信号。
              </div>
            ) : (
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="text-subink text-left border-b border-cardline">
                    <th className="py-1.5 font-medium">fingerprint</th>
                    <th className="py-1.5 font-medium">表达式</th>
                    <th className="py-1.5 font-medium">引擎理由</th>
                    <th className="py-1.5 font-medium text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {pending.map((it) => (
                    <tr key={it.fingerprint} className="border-b border-cardline/60">
                      <td className="py-1.5 font-mono text-[11px] text-subink">{it.fingerprint.slice(0, 10)}</td>
                      <td className="py-1.5 text-ink">{astSummary(it.candidate)}</td>
                      <td className="py-1.5 text-subink truncate max-w-[280px]" title={it.reason}>{it.reason}</td>
                      <td className="py-1.5 text-right whitespace-nowrap">
                        <button
                          onClick={() => { setReviewTarget({ fingerprint: it.fingerprint, action: "approve" }); setReviewNotes(""); }}
                          disabled={reviewBusy}
                          className="text-[12px] px-2 py-0.5 rounded bg-ok/10 text-ok border border-ok/30 mr-1"
                        >
                          批准
                        </button>
                        <button
                          onClick={() => { setReviewTarget({ fingerprint: it.fingerprint, action: "reject" }); setReviewNotes(""); }}
                          disabled={reviewBusy}
                          className="text-[12px] px-2 py-0.5 rounded bg-danger/10 text-danger border border-danger/30"
                        >
                          拒绝
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            {decided.length > 0 && (
              <div className="mt-4">
                <div className="text-[12px] text-subink mb-2">已决策({decided.length})</div>
                {promoteErr && <div className="text-sm text-danger mb-2">入册失败:{promoteErr}</div>}
                <table className="w-full text-[13px]">
                  <tbody>
                    {decided.map((it) => {
                      const promoted = promoteResults[it.fingerprint];
                      return (
                        <tr key={it.fingerprint} className="border-b border-cardline/60">
                          <td className="py-1 font-mono text-[11px] text-subink whitespace-nowrap pr-3">{it.fingerprint.slice(0, 10)}</td>
                          <td className="py-1 text-ink pr-3 whitespace-nowrap">{astSummary(it.candidate)}</td>
                          <td className={`py-1 pr-3 whitespace-nowrap ${it.review_action === "approve" ? "text-ok" : "text-danger"}`}>
                            {it.review_action === "approve" ? "已批准" : "已拒绝"}
                          </td>
                          <td className="py-1 text-subink truncate max-w-[240px]" title={it.reviewer_notes}>{it.reviewer_notes || "—"}</td>
                          <td className="py-1 text-subink whitespace-nowrap pr-3">{it.reviewed_at}</td>
                          <td className="py-1 text-right whitespace-nowrap">
                            {it.review_action === "approve" && !promoted && (
                              <button
                                onClick={() => promoteCandidate(it.fingerprint)}
                                disabled={promoteBusy !== null}
                                title="走 workflow phase1~4(合成防未来审计 → 三段回测 → walk-forward → 唯一台账登记),分钟级"
                                className="text-[12px] px-2 py-0.5 rounded bg-brand/10 text-brand border border-brand/30 disabled:opacity-50"
                              >
                                {promoteBusy === it.fingerprint ? "入册中(分钟级)…" : "正式入册"}
                              </button>
                            )}
                            {promoted && (
                              <span className={promoted.registered ? "text-ok" : "text-warn"} title={promoted.detail}>
                                {promoted.registered ? `已入册 ${promoted.version}` : "未达入册闸门"}
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* 候选台账 */}
          <div className="card">
            <div className="text-sm font-medium mb-3">候选列表(append-only · fingerprint 可复现)</div>
            <div className="max-h-80 overflow-y-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="text-subink text-left border-b border-cardline sticky top-0 bg-white">
                    <th className="py-1 font-medium">fingerprint</th>
                    <th className="py-1 font-medium">表达式</th>
                    <th className="py-1 font-medium text-right">复杂度</th>
                    <th className="py-1 font-medium">状态</th>
                    <th className="py-1 font-medium">备注</th>
                  </tr>
                </thead>
                <tbody>
                  {candidates.map((c) => (
                    <tr key={c.fingerprint} className="border-b border-cardline/60">
                      <td className="py-1 font-mono text-[11px] text-subink whitespace-nowrap pr-3">{c.fingerprint.slice(0, 10)}</td>
                      <td className="py-1 text-ink pr-3 whitespace-nowrap">{astSummary(c.ast)}</td>
                      <td className="py-1 text-right text-subink pr-3">{num(c.complexity_score, 1)}</td>
                      <td className={`py-1 pr-3 whitespace-nowrap ${statusTone(c.status)}`}>{STATUS_LABEL[c.status] ?? c.status}</td>
                      <td className="py-1 text-subink truncate max-w-[300px]" title={c.notes}>{c.notes || "—"}</td>
                    </tr>
                  ))}
                  {candidates.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-2 text-subink">暂无候选,点击上方「运行」生成种子候选。</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="text-[11px] text-subink mt-3">
              AI 生成内容仅供研究参考,不构成投资建议。回测结果不代表未来收益,实盘交易存在亏损风险。
            </div>
          </div>
        </>
      )}
    </>
  );
}
