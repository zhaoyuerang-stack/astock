"use client";

import { useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import { api, pct, signedPct, num } from "@/lib/api";
import type { BacktestResult } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";

const DEFAULTS = { start: "2018-01-01", top_n: 25, rebalance_days: 20, factor_window: 60, timing_ma: 16, leverage: 1.25 };

export default function BacktestPage() {
  const [params, setParams] = useState(DEFAULTS);
  const [res, setRes] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const setContext = useAgent((s) => s.setContext);

  async function run() {
    setLoading(true);
    setErr(null);
    try {
      const r = await api.runBacktest(params);
      setRes(r);
      // 规则式解读 push 给右侧 Agent(Phase 5 换成真 Agent)
      setContext({
        page: "backtest",
        title: "回测审查助手",
        summary: `回测完成:年化 ${signedPct(r.annual)},夏普 ${num(r.sharpe)},最大回撤 ${pct(r.maxdd)}。${r.hit ? "达到入册门槛 ✅" : "未达入册门槛 ❌"}`,
        evidence: [
          `样本:${r.n_stocks} 只 × ${r.n_days} 日(${r.start}~${r.end})`,
          `卡玛 ${num(r.calmar)} · 年均换手 ${num(r.turnover_annual, 1)}x · 年均成本拖累 ${pct(r.cost_annual)}`,
        ],
        risk: [
          Math.abs(r.maxdd) > 0.2 ? `回撤 ${pct(r.maxdd)} 超 20% 阈值` : `回撤 ${pct(r.maxdd)} 在 20% 阈内`,
          r.turnover_annual > 20 ? `换手 ${num(r.turnover_annual, 1)}x 偏高,成本敏感` : `换手 ${num(r.turnover_annual, 1)}x 可控`,
        ],
        recommendation: [
          r.sharpe >= 1.0 ? "夏普达标,可进样本外/压力测试复核" : "夏普偏低,先排查 regime 依赖",
          "成本敏感性:用 cost_sensitivity 复核扣费后稳健性",
        ],
        nextActions: ["跑 2010-2026 压力测试", "导出 markdown 报告"],
      });
    } catch (e) {
      setErr(String(e));
    } finally {
      setLoading(false);
    }
  }

  function exportReport() {
    if (!res) return;
    const md = `# 策略回测报告 — ${res.family}/${res.version}

- 区间: ${res.start} ~ ${res.end}  (${res.n_stocks} 只 × ${res.n_days} 日)
- 年化收益: ${signedPct(res.annual)}
- 夏普: ${num(res.sharpe)}   卡玛: ${num(res.calmar)}
- 最大回撤: ${pct(res.maxdd)}   达标: ${res.hit ? "✅" : "❌"}
- 年均换手: ${num(res.turnover_annual, 1)}x   年均成本拖累: ${pct(res.cost_annual)}

## 分年度收益
${Object.entries(res.yearly_returns).map(([y, r]) => `- ${y}: ${signedPct(r)}`).join("\n")}

> 口径 data_lake · 成本固化(买0.225%/卖0.275%/融资6.5%) · 研究辅助,不构成投资建议。
`;
    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `backtest_${res.family}_${res.start}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const years = res ? Object.entries(res.yearly_returns) : [];
  const maxAbs = Math.max(0.01, ...years.map(([, r]) => Math.abs(r)));

  return (
    <div>
      <PageHeader title="策略回测" desc="生产口径回测(走 core.engine 唯一权威路径;前端不重算)" />

      {/* 配置栏 */}
      <div className="card mb-5">
        <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
          {([
            ["start", "起始日", "text"],
            ["top_n", "持仓数", "number"],
            ["rebalance_days", "调仓周期", "number"],
            ["factor_window", "因子窗口", "number"],
            ["timing_ma", "择时MA", "number"],
            ["leverage", "杠杆", "number"],
          ] as const).map(([k, label, type]) => (
            <label key={k} className="text-[12px] text-subink">
              {label}
              <input
                type={type}
                step="any"
                value={(params as any)[k]}
                onChange={(e) =>
                  setParams((p) => ({ ...p, [k]: type === "number" ? Number(e.target.value) : e.target.value }))
                }
                className="mt-1 w-full text-sm border border-cardline rounded-lg px-2 py-1.5 outline-none focus:border-brand"
              />
            </label>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            onClick={run}
            disabled={loading}
            className="bg-brand text-white text-sm rounded-lg px-4 py-2 disabled:opacity-60"
          >
            {loading ? "回测运行中…(全市场加载需 ~30-60s)" : "运行回测"}
          </button>
          {res && (
            <button onClick={exportReport} className="text-sm rounded-lg px-4 py-2 border border-cardline text-ink">
              导出 markdown 报告
            </button>
          )}
        </div>
      </div>

      {err && <div className="card text-sm text-danger mb-4">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}

      {res && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-5">
            <MetricCard label="年化收益" value={signedPct(res.annual)} tone={res.annual > 0 ? "ok" : "danger"} />
            <MetricCard label="夏普比率" value={num(res.sharpe)} tone={res.sharpe >= 1 ? "ok" : "warn"} />
            <MetricCard label="最大回撤" value={pct(res.maxdd)} tone={Math.abs(res.maxdd) <= 0.2 ? "ok" : "danger"} />
            <MetricCard label="卡玛比率" value={num(res.calmar)} />
            <MetricCard label="入册达标" value={res.hit ? "达标 ✅" : "未达标 ❌"} tone={res.hit ? "ok" : "warn"} />
          </div>

          <div className="card mb-5">
            <div className="text-sm font-medium mb-1">分年度收益</div>
            <div className="text-[11px] text-subink mb-3">
              {res.n_stocks} 只 × {res.n_days} 日 · 年均换手 {num(res.turnover_annual, 1)}x · 成本拖累 {pct(res.cost_annual)}
            </div>
            <div className="flex items-end gap-3 h-40">
              {years.map(([y, r]) => (
                <div key={y} className="flex-1 flex flex-col items-center justify-end h-full">
                  <span className={`text-[11px] mb-1 ${r >= 0 ? "text-ok" : "text-danger"}`}>{signedPct(r, 0)}</span>
                  <div
                    className={`w-full rounded-t ${r >= 0 ? "bg-teal" : "bg-danger"}`}
                    style={{ height: `${(Math.abs(r) / maxAbs) * 100}%` }}
                  />
                  <span className="text-[11px] text-subink mt-1">{y}</span>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {!res && !loading && !err && (
        <div className="card text-sm text-subink">配置参数后点「运行回测」。默认即生产 small-cap-size 口径。</div>
      )}
    </div>
  );
}
