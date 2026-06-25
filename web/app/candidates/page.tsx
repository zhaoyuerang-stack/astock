"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import Card from "@/components/ui/Card";
import StatusBanner from "@/components/ui/StatusBanner";
import { api } from "@/lib/api";
import type { TradePlanView, TradeReadinessView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

export default function CandidatesPage() {
  const [paperPlan, setPaperPlan] = useState<TradePlanView | null>(null);
  const [readiness, setReadiness] = useState<TradeReadinessView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const setContext = useAgent((s) => s.setContext);

  const load = useCallback(() => {
    setErr(null);
    Promise.all([api.paperPlan(), api.tradeReadiness()])
      .then(([pp, tr]) => {
        setPaperPlan(pp);
        setReadiness(tr);

        const count = pp.candidates?.length ?? 0;
        setContext({
          page: "candidates",
          title: "策略选股候选审查",
          summary: `今日策略最优候选池共选出 ${count} 只股票。当前择时状态为「${pp.action}」，当前实际持仓为防守债券资产。`,
          evidence: pp.candidates?.slice(0, 5).map((c, i) => `#${i + 1} ${c.name} (${c.code})`) || [],
          risk: pp.regime === "bear" ? ["当前市场处于 BEAR 状态，候选股票不执行买入，资金以国债ETF形式进行防御避险"] : [],
          recommendation: ["核对候选股在各版块中的资金容量与流动性偏离", "关注在册因子相对于基准的风格追踪误差"],
          nextActions: ["进入「研发实验室」对个股超额收益做IC归因", "进入「风险控制」查看组合风格敏感度"],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext]);

  useAutoRefresh(load);

  const bearMode = paperPlan?.regime === "bear";
  const isStale = !!paperPlan?.stale;
  const isDemoted = !!(readiness && readiness.model_version !== "approved");

  const status: "ready" | "attention" | "blocked" = 
    isStale || isDemoted
      ? "blocked"
      : bearMode
      ? "attention"
      : "ready";

  const bannerTitle = isStale
    ? "⚠️ 候选池: 数据已过期"
    : isDemoted
    ? `⚠️ 部署策略已被风控降级 (${readiness?.model_version})`
    : `今日因子候选池:${paperPlan?.candidates?.length ?? 0} 只标的`;

  const bannerDetail = isStale
    ? `信号日期为 ${paperPlan?.signal_date}，早于当前系统最新交易日。候选股票池数据已失效。`
    : isDemoted
    ? `主策略 [${readiness?.details?.model_admission_track || "未知"}] 状态为 ${readiness?.model_version}，未通过 DSR 显著性审计或安全阀门，已被拦截部署。候选股票池仅供审计参考。`
    : bearMode
    ? `BEAR 空仓防守 · 候选池仅供审计参考,今日不交易股票,资金已轮动至 ${paperPlan?.bond?.name || "国债ETF"} (${paperPlan?.bond?.code || "511010"}) 避险`
    : "BULL 多头入场 · 候选池为今日可交易标的";

  return (
    <div className="space-y-6">
      <PageHeader
        title="股票候选"
        desc="策略因子最优排名前 25 只标的 · illiquidity v3.1 (Amihud 非流动性 + Salience Veto 30%)"
      />

      {err && (
        <div className="card text-sm text-danger mb-4">
          API 错误: {err}
          <br />
          请确认后端已启动（uvicorn :8011）。
        </div>
      )}

      {!paperPlan && !err && <div className="card text-sm text-subink">加载候选数据中…</div>}

      {paperPlan && (
        <>
          {/* 候选池态势头条:一眼回答「这些候选今天可不可执行」——BEAR 下仅供参考 */}
          <StatusBanner
            status={status}
            title={bannerTitle}
            detail={bannerDetail}
          />

          {/* Summary metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label="候选股票数"
              value={String(paperPlan.candidates?.length ?? 0)}
              sub="illiquidity 优选 Top N"
            />
            <MetricCard
              label="当前市场择时"
              value={paperPlan.action}
              tone={bearMode ? "warn" : "ok"}
              sub={bearMode ? "BEAR (空仓避险)" : "BULL (多头入场)"}
            />
            <MetricCard
              label="策略杠杆比例"
              value={`${(paperPlan.band_exposure ?? 0).toFixed(2)}x`}
              sub="基于动量强度动态调整"
            />
            <MetricCard
              label="信号生成时间"
              value={paperPlan.signal_date || "—"}
              sub="每天交易日收盘后重算"
            />
          </div>

          {/* Grid Layout of Candidates */}
          <Card
            title="今日因子最优选股候选池 (Top 25 Candidates)"
            right={<span className="font-quant">因子基准: Amihud 换手率溢价 + 泡沫剔除</span>}
          >
            {paperPlan.candidates && paperPlan.candidates.length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3.5">
                {paperPlan.candidates.map((stock, idx) => (
                  <div
                    key={stock.code}
                    className={`p-3 rounded-[10px] bg-bg/50 border border-cardline/30 transition-all duration-300 group flex flex-col relative overflow-hidden ${
                      isStale || isDemoted
                        ? "opacity-40 grayscale"
                        : "hover:border-[#88ABDA]/40"
                    }`}
                  >
                    <div className="absolute right-0 top-0 w-8 h-8 bg-gradient-to-bl from-[#88ABDA]/5 to-transparent rounded-bl-xl opacity-0 group-hover:opacity-100 transition-opacity" />
                    <div className="text-[10px] text-subink font-quant mb-1 flex justify-between items-center">
                      <span className="font-mono tracking-wider">{stock.code}</span>
                      <span className="text-[9px] px-1.5 py-0.5 rounded bg-line/30 text-subink">
                        #{idx + 1}
                      </span>
                    </div>
                    <div className="text-[13px] font-bold text-ink truncate group-hover:text-brand transition-colors mt-0.5">
                      {stock.name}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-subink text-[13px]">
                暂无候选股信息（信号仍在计算或未完成落盘）
              </div>
            )}
          </Card>

          {/* Strategy Veto Explanation */}
          <Card title="💡 因子库筛选与泡沫过滤说明 (Salience Veto Model)">
            <p className="text-[12px] text-subink leading-relaxed">
              illiquidity 选股逻辑按每日「不复权收盘价/成交量」量化非流动性因子，优先挑选交易摩擦大、容易产生非流动性溢价的小微盘股。
              为了防止买入泡沫化的“妖股”，系统在前置阶段运行 <b>泡沫过滤器 (Salience Veto Filter)</b>：自动剔除 faded_st_cov 排名后 30%（即情绪热度极高、估值严重偏离的泡沫股）的标的。最终剩下的池子选取夏普比率最优的 25 只作为本日的最优股票候选集。
            </p>
          </Card>
        </>
      )}
    </div>
  );
}
