"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import Card from "@/components/ui/Card";
import StatusBanner from "@/components/ui/StatusBanner";
import { api, pct } from "@/lib/api";
import type { TradePlanView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

export default function SignalsPage() {
  const [paperPlan, setPaperPlan] = useState<TradePlanView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const setContext = useAgent((s) => s.setContext);

  const load = useCallback(() => {
    setErr(null);
    api
      .paperPlan()
      .then((pp) => {
        setPaperPlan(pp);

        setContext({
          page: "signals",
          title: "策略信号与择时指标",
          summary: `当前择时判定为「${pp.action}」，动态风险暴露为 ${pp.band_exposure.toFixed(2)}x。趋势偏离度为 ${(pp.small_index_vs_ma16 * 100).toFixed(2)}%。`,
          evidence: [
            `小盘 vs MA16 趋势偏离度: ${(pp.small_index_vs_ma16 * 100).toFixed(2)}%`,
            `大周期极性 (Regime Dist): ${(pp.regime_dist * 100).toFixed(2)}%`,
            `影子二元择时 (Binary): ${pp.binary_in_market_shadow ? "持仓" : "空仓"}`,
          ],
          risk: pp.regime === "bear" ? ["大周期处于 BEAR 熊市基调下，系统锁定股票买入权限"] : [],
          recommendation: ["核对小盘指数与 MA16 均线的交叉节点", "监控 Regime Dist 偏离方向是否发生根本转变"],
          nextActions: ["前往「策略回测」检验趋势偏离参数", "前往「组合管理」检查资产仓位比例"],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext]);

  useAutoRefresh(load);

  const bearMode = paperPlan?.regime === "bear";
  // 择时态势:LIVE 动态暴露 与 影子二元择时 是否分歧——这条审计信号原本
  // 只埋在右栏三根进度条里,提到头条揭示「系统内部判定是否一致」。
  const liveInMarket = (paperPlan?.band_exposure ?? 0) > 0;
  const shadowInMarket = paperPlan?.binary_in_market_shadow ?? false;
  const timingDiverge = !!paperPlan && liveInMarket !== shadowInMarket;
  const timingStatus: "ready" | "attention" = bearMode || timingDiverge ? "attention" : "ready";

  return (
    <div className="space-y-6">
      <PageHeader
        title="策略信号"
        desc="底层量化因子与趋势择时数学模型指标核算 (Strategy Timing Indicators)"
      />

      {err && (
        <div className="card text-sm text-danger mb-4">
          API 错误: {err}
          <br />
          请确认后端已启动（uvicorn :8011）。
        </div>
      )}

      {!paperPlan && !err && <div className="card text-sm text-subink">加载策略信号中…</div>}

      {paperPlan && (
        <>
          {/* 择时态势头条:一眼回答「今日为什么这么决策、系统内部判定有无矛盾」 */}
          <StatusBanner
            status={timingStatus}
            title={`今日择时判定:${paperPlan.action}`}
            detail={[
              bearMode ? "大周期 BEAR · 股票买入权限锁定,维持避险" : "大周期 BULL · 允许股票配置",
              timingDiverge
                ? `⚠ LIVE(${liveInMarket ? "持仓" : "空仓"}) 与影子二元(${shadowInMarket ? "持仓" : "空仓"})判定分歧`
                : "LIVE 与影子择时一致",
            ].join(" · ")}
          />

          {/* Summary metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label="大周期状态 (Regime)"
              value={paperPlan.regime === "bear" ? "🔴 BEAR (熊市)" : "🟢 BULL (牛市)"}
              tone={paperPlan.regime === "bear" ? "danger" : "ok"}
              sub={`信度偏离: ${(paperPlan.regime_dist * 100).toFixed(2)}%`}
            />
            <MetricCard
              label="均线趋势偏离度"
              value={`${(paperPlan.small_index_vs_ma16 * 100).toFixed(2)}%`}
              tone={paperPlan.small_index_vs_ma16 < 0 ? "danger" : "ok"}
              sub="小盘股指数 vs MA16 偏离"
            />
            <MetricCard
              label="动态暴露杠杆"
              value={`${(paperPlan.band_exposure ?? 0).toFixed(2)}x`}
              sub="Based on PureTrend Band"
            />
            <MetricCard
              label="择时决策"
              value={paperPlan.action}
              tone={bearMode ? "warn" : "ok"}
              sub={`信号生效日: ${paperPlan.signal_date || "—"}`}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column: Indicators & Thresholds Audit Table */}
            <div className="lg:col-span-2 space-y-6">
              <Card
                title="策略底层择时指标核算与阈值审计 (Indicators & Thresholds)"
                right={<span className="text-[#88ABDA]">策略版本: illiquidity v3.1</span>}
              >
                <div className="overflow-x-auto">
                  <table className="w-full text-[13px]">
                    <thead>
                      <tr className="text-subink text-left border-b border-cardline pb-2">
                        <th className="py-2 font-medium">指标名称</th>
                        <th className="py-2 font-medium">数学物理定义</th>
                        <th className="py-2 font-medium text-right">当前数值</th>
                        <th className="py-2 font-medium text-right">触发阈值</th>
                        <th className="py-2 text-center font-medium">判定结论</th>
                      </tr>
                    </thead>
                    <tbody>
                      {/* Indicator 1 */}
                      <tr className="border-b border-cardline/60 hover:bg-cardline/10 transition-colors">
                        <td className="py-3 font-semibold text-ink">小盘趋势偏离度</td>
                        <td className="py-3 text-subink text-[12px]">Small Cap Index vs MA16 Distance</td>
                        <td className={`py-3 text-right font-mono font-medium ${paperPlan.small_index_vs_ma16 < 0 ? "text-danger" : "text-ok"}`}>
                          {(paperPlan.small_index_vs_ma16 * 100).toFixed(2)}%
                        </td>
                        <td className="py-3 text-right font-mono text-subink">0.00%</td>
                        <td className="py-3 text-center">
                          <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            paperPlan.small_index_vs_ma16 < 0 ? "bg-danger/10 text-danger" : "bg-ok/10 text-ok"
                          }`}>
                            {paperPlan.small_index_vs_ma16 < 0 ? "🔴 空仓信号" : "🟢 多头信号"}
                          </span>
                        </td>
                      </tr>

                      {/* Indicator 2 */}
                      <tr className="border-b border-cardline/60 hover:bg-cardline/10 transition-colors">
                        <td className="py-3 font-semibold text-ink">大周期状态极性</td>
                        <td className="py-3 text-subink text-[12px]">Shifted Regime Polar Distance</td>
                        <td className={`py-3 text-right font-mono font-medium ${paperPlan.regime_dist < 0 ? "text-danger" : "text-ok"}`}>
                          {(paperPlan.regime_dist * 100).toFixed(2)}%
                        </td>
                        <td className="py-3 text-right font-mono text-subink">0.00%</td>
                        <td className="py-3 text-center">
                          <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            paperPlan.regime_dist < 0 ? "bg-[#88ABDA]/10 text-[#88ABDA]" : "bg-ok/10 text-ok"
                          }`}>
                            {paperPlan.regime_dist < 0 ? "🔵 债券轮动 (BEAR)" : "🟢 股票配置 (BULL)"}
                          </span>
                        </td>
                      </tr>

                      {/* Indicator 3 */}
                      <tr className="border-b border-cardline/60 hover:bg-cardline/10 transition-colors">
                        <td className="py-3 font-semibold text-ink">动态杠杆系数</td>
                        <td className="py-3 text-subink text-[12px]">PureTrend Band Exposure (Live)</td>
                        <td className="py-3 text-right font-mono font-medium text-ink">
                          {paperPlan.band_exposure.toFixed(2)}x
                        </td>
                        <td className="py-3 text-right font-mono text-subink">0.00x ~ 1.50x</td>
                        <td className="py-3 text-center">
                          <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            paperPlan.band_exposure === 0 ? "bg-cardline text-subink" : "bg-ok/10 text-ok"
                          }`}>
                            {paperPlan.band_exposure === 0 ? "⏸ 无杠杆暴露" : `⚡ 杠杆 ${(paperPlan.band_exposure).toFixed(2)}x`}
                          </span>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </Card>

              {/* Timing Diagnosis Card */}
              <Card title="🔄 日内择时调仓判定诊断书 (Rebalance Diagnosis)">
                <div className="p-3.5 rounded-[8px] bg-bg/50 border border-cardline/40 space-y-2 text-[12px]">
                  <div className="flex justify-between">
                    <span className="text-subink">调仓判定日</span>
                    <span className="text-ink">否 (is_rebalance_day = False)</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-subink">决策触发成因</span>
                    <span className="text-warn font-semibold">{paperPlan.action} (继续观望，空仓避险)</span>
                  </div>
                  <div className="pt-2 border-t border-cardline/20 text-subink leading-relaxed">
                    依据系统指令成因，策略检测到 **小盘趋势偏离度为 {(paperPlan.small_index_vs_ma16 * 100).toFixed(2)}%**，未突破 0% 多头临界阈值。
                    同时 **大周期极性依旧处于负值 (BEAR)**，此时策略触发安全阻尼，交易判定不触发调仓，继续保持国债ETF避险持有状态。
                  </div>
                </div>
              </Card>
            </div>

            {/* Right Column: Shadow Timing Comparisons */}
            <div className="space-y-6">
              {/* Shadow Timing Benchmarks */}
              <Card title="多级择时影子系统对照 (Shadow Timing Benchmarks)">
                <div className="space-y-4 text-[12px]">
                  <p className="text-subink leading-relaxed">
                    这里展示了系统在主决策机制（LIVE 动态暴露）与影子系统（经典二元对照）的判定输出差异，用于量化校验和回测偏离审计。
                  </p>

                  {/* Live Exposure */}
                  <div className="space-y-1.5">
                    <div className="flex justify-between">
                      <span className="font-semibold text-ink">LIVE 动态暴露 (Band Timing)</span>
                      <span className="font-mono text-ok">{paperPlan.band_exposure.toFixed(2)}x</span>
                    </div>
                    <div className="w-full h-2 rounded bg-cardline overflow-hidden">
                      <div
                        className="h-full bg-ok transition-all duration-500"
                        style={{ width: `${(paperPlan.band_exposure / 1.5) * 100}%` }}
                      />
                    </div>
                    <div className="text-[10px] text-subink flex justify-between"><span>0.0x (空仓)</span><span>1.5x (满杠杆)</span></div>
                  </div>

                  {/* Shadow Binary */}
                  <div className="space-y-1.5 pt-2 border-t border-cardline/20">
                    <div className="flex justify-between">
                      <span className="font-semibold text-ink">二元对照择时 (Binary Shadow)</span>
                      <span className={`font-mono ${paperPlan.binary_in_market_shadow ? "text-ok" : "text-danger"}`}>
                        {paperPlan.binary_in_market_shadow ? "100% (持仓)" : "0% (空仓)"}
                      </span>
                    </div>
                    <div className="w-full h-2 rounded bg-cardline overflow-hidden">
                      <div
                        className={`h-full transition-all duration-500 ${paperPlan.binary_in_market_shadow ? "bg-ok" : "bg-danger"}`}
                        style={{ width: paperPlan.binary_in_market_shadow ? "100%" : "0%" }}
                      />
                    </div>
                  </div>

                  {/* Base Binary */}
                  <div className="space-y-1.5 pt-2 border-t border-cardline/20">
                    <div className="flex justify-between">
                      <span className="font-semibold text-ink">原始择时基础线 (Base Binary)</span>
                      <span className={`font-mono ${paperPlan.base_in_market ? "text-ok" : "text-danger"}`}>
                        {paperPlan.base_in_market ? "100% (持仓)" : "0% (空仓)"}
                      </span>
                    </div>
                    <div className="w-full h-2 rounded bg-cardline overflow-hidden">
                      <div
                        className={`h-full transition-all duration-500 ${paperPlan.base_in_market ? "bg-ok" : "bg-danger"}`}
                        style={{ width: paperPlan.base_in_market ? "100%" : "0%" }}
                      />
                    </div>
                  </div>
                </div>
              </Card>

              {/* V3.1 Parameter Ledger */}
              <Card title="⚙️ 策略择时参数台账">
                <div className="space-y-2 text-[12px] text-subink">
                  <div className="flex justify-between py-1 border-b border-cardline/30">
                    <span>趋势择时均线周期 (MA)</span>
                    <span className="text-ink font-quant">16 交易日</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-cardline/30">
                    <span>杠杆动态乘数 (Multiplier)</span>
                    <span className="text-ink font-quant">1.25x / 1.50x</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-cardline/30">
                    <span>择时极性切换缓冲</span>
                    <span className="text-ink font-quant">Band 阻尼宽度 2.5%</span>
                  </div>
                  <div className="flex justify-between py-1">
                    <span>信号发生频率</span>
                    <span className="text-ink font-quant">日频 (盘后 15:30)</span>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
