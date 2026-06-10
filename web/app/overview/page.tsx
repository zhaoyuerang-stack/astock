"use client";

import { useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import { api, pct, num } from "@/lib/api";
import type { StrategyView, MarketStateView, FactorHealthView, DataQualityView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";

const FLOW = ["假设发现", "因子构建", "状态识别", "策略构建", "回测验证", "执行监控", "复盘迭代"];

export default function OverviewPage() {
  const [strategies, setStrategies] = useState<StrategyView[]>([]);
  const [market, setMarket] = useState<MarketStateView | null>(null);
  const [health, setHealth] = useState<FactorHealthView[]>([]);
  const [dq, setDq] = useState<DataQualityView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const setContext = useAgent((s) => s.setContext);

  useEffect(() => {
    Promise.all([api.strategies(), api.marketState(), api.strategyHealth(), api.dataQuality()])
      .then(([s, m, h, d]) => {
        setStrategies(s);
        setMarket(m);
        setHealth(h);
        setDq(d);
        const live = s.filter((x) => x.status === "在册").length;
        setContext({
          page: "overview",
          title: "总览分析助手",
          summary: `在册 ${live} 个策略;当前 ${m.last_action};数据质量「${d.verdict}」(真问题 ${d.severe_count} 只)。`,
          evidence: h.map((x) => `${x.name}:夏普 ${num(x.sharpe)}(${x.trend})`),
          risk: d.severe_count > 0 ? [`数据真问题 ${d.severe_count} 只`] : [],
          recommendation: ["进入策略回测运行生产口径复测", "关注健康度「减速」的因子"],
          nextActions: ["跑 small-cap-size 回测", "查看数据中心质量明细"],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext]);

  const families = new Set(strategies.map((s) => s.family));
  const live = strategies.filter((s) => s.status === "在册").length;
  const cand = strategies.filter((s) => s.status === "候选").length;

  return (
    <div>
      <PageHeader title="总览" desc="平台整体状态 · 实时聚合 strategies / state / 数据质量" />

      <div className="card mb-5 flex items-center gap-2 overflow-x-auto">
        {FLOW.map((n, i) => (
          <div key={n} className="flex items-center gap-2 shrink-0">
            <span className="text-[12px] text-ink px-2 py-1 rounded bg-bg border border-cardline">{n}</span>
            {i < FLOW.length - 1 && <span className="text-subink">→</span>}
          </div>
        ))}
      </div>

      {err && <div className="card text-sm text-danger mb-4">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <MetricCard label="母策略家族" value={String(families.size)} sub="独立 alpha 家族" />
        <MetricCard label="在册版本" value={String(live)} tone="ok" sub="入册门槛达标" />
        <MetricCard label="候选版本" value={String(cand)} tone="warn" sub="待证伪/晋级" />
        <MetricCard
          label="数据质量"
          value={dq?.verdict ?? "—"}
          tone={dq ? (dq.verdict === "可用" ? "ok" : dq.verdict === "关注" ? "warn" : "danger") : "default"}
          sub={dq ? `真问题 ${dq.severe_count} · clean ${pct(dq.clean_ratio, 0)}` : ""}
        />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
        {/* 市场/持仓状态(WEB_DESIGN §4.6)*/}
        <div className="card">
          <div className="text-sm font-medium mb-2">当前状态识别</div>
          {market ? (
            <>
              <div className="text-2xl font-semibold text-ink">{market.last_action || "—"}</div>
              <div className="text-[12px] text-subink mt-1">
                仓位:{market.current_position} · 持仓 {market.n_holdings} 只
              </div>
              <div className="text-[12px] text-subink">信号日:{market.last_signal_date ?? "—"}</div>
            </>
          ) : (
            <div className="text-sm text-subink">—</div>
          )}
        </div>

        {/* 策略健康度(WEB_DESIGN §4.7)*/}
        <div className="card md:col-span-2">
          <div className="text-sm font-medium mb-2">因子健康度</div>
          <table className="w-full text-[13px]">
            <thead>
              <tr className="text-subink text-left border-b border-cardline">
                <th className="py-1 font-medium">因子</th>
                <th className="py-1 font-medium text-right">夏普</th>
                <th className="py-1 font-medium text-right">6M动量</th>
                <th className="py-1 font-medium text-right">趋势</th>
              </tr>
            </thead>
            <tbody>
              {health.map((h) => (
                <tr key={h.name} className="border-b border-cardline/60">
                  <td className="py-1 text-ink">{h.name}</td>
                  <td className="py-1 text-right">{num(h.sharpe)}</td>
                  <td className="py-1 text-right text-subink">{num(h.momentum_6m, 1)}</td>
                  <td className={`py-1 text-right ${h.trend === "加速" ? "text-ok" : "text-warn"}`}>{h.trend}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card">
        <div className="text-sm font-medium mb-3">母策略台账</div>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-subink text-left border-b border-cardline">
              <th className="py-1.5 font-medium">策略</th>
              <th className="py-1.5 font-medium">家族</th>
              <th className="py-1.5 font-medium">状态</th>
              <th className="py-1.5 font-medium">适用市场</th>
            </tr>
          </thead>
          <tbody>
            {strategies.map((s) => (
              <tr key={s.strategy_id} className="border-b border-cardline/60">
                <td className="py-1.5 text-ink">{s.strategy_id}</td>
                <td className="py-1.5 text-subink">{s.family_name || s.family}</td>
                <td className="py-1.5">
                  <span className={s.status === "在册" ? "text-ok" : s.status === "退役" ? "text-danger" : "text-warn"}>
                    {s.status || "—"}
                  </span>
                </td>
                <td className="py-1.5 text-subink truncate max-w-[280px]">{s.regime || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
