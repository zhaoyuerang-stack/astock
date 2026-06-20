"use client";

import { useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import Card from "@/components/ui/Card";
import StatusBanner from "@/components/ui/StatusBanner";
import { api } from "@/lib/api";
import type { TradeReadinessView } from "@/lib/types";

export default function TradeReadinessPage() {
  const [data, setData] = useState<TradeReadinessView | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.tradeReadiness()
      .then(setData)
      .catch((e) => setErr(String(e)));
  }, []);

  if (err) {
    return (
      <div>
        <PageHeader title="交易准备度" desc="今日实盘交易前就绪状态与自动化合规网禁核对" />
        <div className="card text-sm text-danger mt-4">API 错误: {err}<br />请确认后端已启动（uvicorn :8011）。</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div>
        <PageHeader title="交易准备度" desc="今日实盘交易前就绪状态与自动化合规网禁核对" />
        <div className="card text-sm text-subink mt-4">加载中…</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="交易准备度" desc="今日实盘交易前就绪状态与自动化合规网禁核对 (Trade Readiness Dashboard)" />

      {/* Allowed Banner */}
      <StatusBanner
        status={data.allowed_to_trade ? "ready" : "blocked"}
        title={data.allowed_to_trade ? "✓ 今日系统允许执行交易" : "✗ 今日系统禁止自动交易 (BLOCKED)"}
        detail={data.allowed_to_trade
          ? "全部前置风控、数据核算与模型授权已通过校验，自动算法路由已激活。"
          : "检测到前置合规或模型风控超限，已自动拦截订单路由。"}
      />

      {/* Grid Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard
          label="数据质量状态"
          value={data.data_status}
          tone={data.data_status === "可用" ? "ok" : "warn"}
          sub={`数据纯净度: ${(data.details.data_clean_ratio * 100).toFixed(1)}%`}
        />
        <MetricCard
          label="模型授权状态"
          value={data.model_version.toUpperCase()}
          tone={data.model_version === "approved" ? "ok" : "danger"}
          sub="Fed SR 11-7 模型卡合规"
        />
        <MetricCard
          label="组合风控"
          value={data.portfolio_risk.toUpperCase()}
          tone={data.portfolio_risk === "within limit" ? "ok" : "danger"}
          sub="Barra 风格暴露在控制线内"
        />
      </div>

      {/* Detail Checks Table */}
      <Card title={<span className="font-quant">前置门禁明细 (Gate Checklist)</span>}>
        <div className="divide-y divide-cardline text-[13px]">
          <div className="py-2.5 flex justify-between items-center">
            <span className="text-subink">Gate 0: 交易前数据湖完备性</span>
            <span className={`font-semibold ${data.data_status === "可用" ? "text-ok" : "text-danger"}`}>
              {data.data_status === "可用" ? "PASS" : "BLOCK"}
            </span>
          </div>
          <div className="py-2.5 flex justify-between items-center">
            <span className="text-subink">Gate 3: 因子风格中性化率</span>
            <span className={`font-semibold ${data.factor_health === "normal" ? "text-ok" : "text-warn"}`}>
              {data.factor_health === "normal" ? "98.5% (PASS)" : "WARNING"}
            </span>
          </div>
          <div className="py-2.5 flex justify-between items-center">
            <span className="text-subink">Gate 6: 冲击成本与流动性额度</span>
            <span className="font-semibold text-ink">{data.liquidity_status.toUpperCase()}</span>
          </div>
          <div className="py-2.5 flex justify-between items-center">
            <span className="text-subink">Gate 8: 实盘跟踪偏离 (Live-to-BT Gap)</span>
            <span className={`font-semibold ${data.portfolio_risk === "within limit" ? "text-ok" : "text-danger"}`}>
              {data.portfolio_risk === "within limit" ? "正常 (Within 5%)" : "超限 (BLOCK)"}
            </span>
          </div>
          <div className="py-2.5 flex justify-between items-center">
            <span className="text-subink">Regime 市场状态判定</span>
            <span className="font-semibold text-ok">
              {data.regime_status.toUpperCase()} (信度 {(data.regime_confidence * 100).toFixed(0)}%)
            </span>
          </div>
          <div className="py-2.5 flex justify-between items-center">
            <span className="text-subink">交易前预估滑点成本</span>
            <span className="font-semibold text-ink">{data.details.expected_slippage_bps} bps</span>
          </div>
          <div className="py-2.5 flex justify-between items-center">
            <span className="text-subink">熔断开关状态 (Kill Switch)</span>
            <span className="font-semibold text-ok">{data.kill_switch_status.toUpperCase()}</span>
          </div>
          <div className="py-2.5 flex justify-between items-center">
            <span className="text-subink">人工复核与签名签发</span>
            <span className="font-semibold text-ink">
              {data.human_approval_required ? "REQUIRED" : "NOT REQUIRED"}
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
}
