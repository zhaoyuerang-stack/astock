"use client";

import { useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import Card from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { GovernanceView } from "@/lib/types";

const TABS = ["模型卡目录 (Model Cards)", "独立验证报告 (Validation)", "实验全量台账 (Research Ledger)"] as const;
type Tab = (typeof TABS)[number];

function verdictClass(rep: Record<string, any>) {
  const code = rep.audit_status || rep.verdict;
  if (code === "PASSED" || rep.verdict === "PASS" || rep.verdict === "审计通过") return "text-ok";
  if (
    code === "FAILED" ||
    code === "RUN_FAILED" ||
    rep.verdict === "FAIL" ||
    rep.verdict === "审计失败" ||
    rep.verdict === "审计未通过"
  ) {
    return "text-danger";
  }
  return "text-warn";
}

function formatCheckValue(value: any) {
  if (typeof value === "number") return value.toFixed(2);
  if (value == null) return "—";
  return String(value);
}

export default function GovernancePage() {
  const [tab, setTab] = useState<Tab>("模型卡目录 (Model Cards)");
  const [data, setData] = useState<GovernanceView | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.governance()
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) {
    return (
      <div>
        <PageHeader title="模型风险治理" desc="美联储 SR 11-7 标准模型风险合规与实验全量追踪审计" />
        <div className="card text-sm text-danger mt-4">API 错误: {err}<br />请确认后端已启动（uvicorn :8011）。</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <PageHeader title="模型风险治理" desc="美联储 SR 11-7 标准模型风险合规与实验全量追踪审计" />
        <div className="card text-sm text-subink mt-4">加载中…</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="模型风险治理" desc="基于美联储 SR 11-7 等机构框架设计的模型生命周期审查与多重假设追踪" />

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-cardline">
        {TABS.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-3 py-1.5 text-[13px] rounded-t border-b-2 -mb-px transition-all duration-200 ${
              tab === t ? "border-brand text-brand font-medium" : "border-transparent text-subink hover:text-ink"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab contents */}
      {tab === "模型卡目录 (Model Cards)" && (
        <div className="space-y-4">
          {data.model_cards.map((card) => (
            <Card
              key={card.strategy_id}
              className="space-y-4"
              title={<span className="text-base font-bold font-quant">{card.strategy_id}</span>}
              subtitle={<span className="text-[13px]">{card.economic_hypothesis}</span>}
              right={
                <div className="flex items-center gap-2">
                  {card.admission_track && (
                    <span
                      className="px-2 py-0.5 text-xs font-medium rounded-[4px] border bg-brand/10 text-brand border-brand/20"
                      title={card.admission_track === "diversifier" ? "组合分流器:单体不达标但负相关/对组合有增量" : "单体达标准入"}
                    >
                      {card.admission_track === "standalone" ? "单体达标" : card.admission_track === "diversifier" ? "分流器" : card.admission_track}
                    </span>
                  )}
                  <span className={`px-2.5 py-0.5 text-xs font-semibold rounded-[4px] border ${
                    card.approval_status === "APPROVED"
                      ? "bg-ok/10 text-ok border-ok/20"
                      : card.approval_status === "PENDING"
                      ? "bg-warn/10 text-warn border-warn/20"
                      : "bg-danger/10 text-danger border-danger/20"
                  }`}>
                    {card.approval_status}
                  </span>
                </div>
              }
            >
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5 text-[13px]">
                <div>
                  <span className="text-subink block text-[11px] uppercase tracking-wide">数据来源</span>
                  <span className="text-ink">{card.data_sources?.join(", ")}</span>
                </div>
                <div>
                  <span className="text-subink block text-[11px] uppercase tracking-wide">容量上限</span>
                  <span className="text-ink">¥{(card.capacity_limit / 1000000).toFixed(1)}M CNY</span>
                </div>
                <div>
                  <span className="text-subink block text-[11px] uppercase tracking-wide">样本划分 (Train / OOS)</span>
                  <span className="text-ink">{card.train_period} / {card.oos_period}</span>
                </div>
                <div>
                  <span className="text-subink block text-[11px] uppercase tracking-wide">适用市场状态 (Regime)</span>
                  <span className="text-ink">{card.applicable_regimes?.join(", ")}</span>
                </div>
                <div>
                  <span className="text-subink block text-[11px] uppercase tracking-wide">风格暴露控制 (Style Exposures)</span>
                  <span className="text-ink">
                    {Object.entries(card.style_exposures || {}).map(([k, v]) => `${k}: ${v}`).join(", ")}
                  </span>
                </div>
                <div>
                  <span className="text-subink block text-[11px] uppercase tracking-wide">禁用条件</span>
                  <span className="text-danger">{card.forbidden_conditions?.join(", ")}</span>
                </div>
              </div>

              {card.signature && (
                <div className="pt-2.5 border-t border-cardline flex justify-between items-center text-xs text-subink">
                  <span>审批人: {card.approver} ({card.owner})</span>
                  <span className="font-mono text-ok/70 select-all">{card.signature}</span>
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {tab === "独立验证报告 (Validation)" && (
        <div className="space-y-4">
          {data.validation_reports.map((rep) => (
            <Card
              key={rep.strategy_id}
              className="space-y-4"
              title={<span className="font-quant">{rep.strategy_id} 独立验证报告</span>}
              right={<span className={`text-[13px] font-bold ${verdictClass(rep)}`}>{rep.verdict}</span>}
            >
              <div className="grid grid-cols-3 gap-4">
                <div className="p-3 bg-qilin/60 rounded-[8px] border border-cardline">
                  <span className="text-[11px] text-subink block">OOS 夏普比率</span>
                  <span className="text-base font-bold text-ink">{rep.metrics.oos_sharpe?.toFixed(2)}</span>
                </div>
                <div className="p-3 bg-qilin/60 rounded-[8px] border border-cardline">
                  <span className="text-[11px] text-subink block">OOS 最大回撤</span>
                  <span className="text-base font-bold text-ink">{(rep.metrics.oos_max_dd * 100).toFixed(1)}%</span>
                </div>
                <div className="p-3 bg-qilin/60 rounded-[8px] border border-cardline">
                  <span className="text-[11px] text-subink block">参数稳定信度</span>
                  <span className="text-base font-bold text-ink">{(rep.metrics.stability_ratio * 100).toFixed(0)}%</span>
                </div>
              </div>

              {/* 多重检验惩罚证据(DSR/PSR)—— 取代仅凭样本内 Sharpe 的判定 */}
              {rep.audited ? (
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-3 bg-qilin/60 rounded-[8px] border border-cardline">
                    <span className="text-[11px] text-subink block">DSR p值 (多重检验惩罚)</span>
                    <span className={`text-base font-bold ${rep.metrics.dsr_p != null && rep.metrics.dsr_p < 0.05 ? "text-ok" : "text-danger"}`}>
                      {rep.metrics.dsr_p != null ? rep.metrics.dsr_p.toFixed(3) : "—"}
                    </span>
                  </div>
                  <div className="p-3 bg-qilin/60 rounded-[8px] border border-cardline">
                    <span className="text-[11px] text-subink block">PSR (夏普&gt;0 概率)</span>
                    <span className="text-base font-bold text-ink">{rep.metrics.psr != null ? `${(rep.metrics.psr * 100).toFixed(1)}%` : "—"}</span>
                  </div>
                  <div className="p-3 bg-qilin/60 rounded-[8px] border border-cardline">
                    <span className="text-[11px] text-subink block">试验次数 (n_trials)</span>
                    <span className="text-base font-bold text-ink">{rep.metrics.n_trials ?? "—"}</span>
                  </div>
                </div>
              ) : rep.audit_status === "RUN_FAILED" ? (
                <div className="text-[12px] text-danger bg-danger/5 border border-danger/20 rounded-[8px] p-2.5">
                  9-Gate 审计执行失败: {rep.checks?.find((c: any) => c.name === "Nine-Gate 执行")?.value ?? "FAILED_TO_RUN"}
                </div>
              ) : (
                <div className="text-[12px] text-warn bg-warn/5 border border-warn/20 rounded-[8px] p-2.5">
                  ⚠ 尚未做多重检验审计(DSR/PSR)。运行 9-Gate 审计并 --persist 回填后,验证判定才纳入过拟合惩罚。
                </div>
              )}

              {/* 机构级风险画像(来自 Nine-Gate Gate5 回测) */}
              {rep.metrics.sortino != null && (
                <div className="grid grid-cols-4 gap-3">
                  <div className="p-2.5 bg-qilin/40 rounded-[8px] border border-cardline">
                    <span className="text-[10px] text-subink block">Sortino</span>
                    <span className="text-sm font-bold text-ink">{rep.metrics.sortino.toFixed(2)}</span>
                  </div>
                  <div className="p-2.5 bg-qilin/40 rounded-[8px] border border-cardline">
                    <span className="text-[10px] text-subink block">VaR 95% (日)</span>
                    <span className="text-sm font-bold text-ink">{rep.metrics.var_95 != null ? `${(rep.metrics.var_95 * 100).toFixed(2)}%` : "—"}</span>
                  </div>
                  <div className="p-2.5 bg-qilin/40 rounded-[8px] border border-cardline">
                    <span className="text-[10px] text-subink block">CVaR 95% (日)</span>
                    <span className="text-sm font-bold text-ink">{rep.metrics.cvar_95 != null ? `${(rep.metrics.cvar_95 * 100).toFixed(2)}%` : "—"}</span>
                  </div>
                  <div className="p-2.5 bg-qilin/40 rounded-[8px] border border-cardline">
                    <span className="text-[10px] text-subink block">尾比 (Tail Ratio)</span>
                    <span className="text-sm font-bold text-ink">{rep.metrics.tail_ratio != null ? rep.metrics.tail_ratio.toFixed(2) : "—"}</span>
                  </div>
                </div>
              )}

              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-subink uppercase tracking-wider">门禁测试详情 (Independent Checks)</h4>
                <div className="divide-y divide-cardline text-[12px]">
                  {rep.checks.map((c: any, i: number) => (
                    <div key={i} className="py-2.5 flex justify-between">
                      <span className="text-subink">{c.name}</span>
                      <span className={c.passed ? "text-ok" : "text-danger"}>
                        {formatCheckValue(c.value)} (阈值: {formatCheckValue(c.threshold)}) - {c.passed ? "通过" : "不通过"}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {tab === "实验全量台账 (Research Ledger)" && (
        <Card
          className="space-y-4"
          title={<span className="font-quant">全量试错实验台账 (Immutable Ledger)</span>}
          right={<span className="text-xs text-subink">已登记实验: {data.experiments_ledger.length} 笔</span>}
        >
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-[12px]">
              <thead>
                <tr className="border-b border-cardline text-subink uppercase tracking-wider font-semibold">
                  <th className="py-2 px-3">实验ID / 时间</th>
                  <th className="py-2 px-3">经济假说</th>
                  <th className="py-2 px-3">AST语义哈希</th>
                  <th className="py-2 px-3">已试参数</th>
                  <th className="py-2 px-3">绩效指标</th>
                  <th className="py-2 px-3">审核人/结论</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-cardline/60">
                {data.experiments_ledger.map((e) => (
                  <tr key={e.experiment_id} className="hover:bg-jilan/10">
                    <td className="py-3 px-3">
                      <span className="font-semibold text-ink block font-mono">{e.experiment_id}</span>
                      <span className="text-subink text-[10px]">{e.run_at}</span>
                    </td>
                    <td className="py-3 px-3 text-ink max-w-[200px] truncate" title={e.hypothesis_text}>
                      {e.hypothesis_text}
                    </td>
                    <td className="py-3 px-3 text-subink font-mono select-all">
                      {e.factor_ast_hash?.slice(0, 8)}...
                    </td>
                    <td className="py-3 px-3 font-mono text-subink">
                      {JSON.stringify(e.tried_parameters)}
                    </td>
                    <td className="py-3 px-3">
                      <span className="text-ok block font-semibold">SR: {e.result_metrics?.sharpe?.toFixed(2)}</span>
                      <span className="text-subink text-[10px]">DD: {(e.result_metrics?.maxdd * 100).toFixed(1)}%</span>
                    </td>
                    <td className="py-3 px-3">
                      <span className="text-ink block">{e.reviewer}</span>
                      <span className={`text-[10px] ${e.rejection_reason ? "text-danger" : "text-ok"}`}>
                        {e.rejection_reason ? `REJECTED: ${e.rejection_reason}` : "APPROVED"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
