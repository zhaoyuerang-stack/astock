"use client";

import { useEffect, useState } from "react";
import Card from "@/components/ui/Card";
import MetricCard from "@/components/ui/MetricCard";
import { api, pct, num } from "@/lib/api";

interface Metrics {
  annual: number | null;
  maxdd: number | null;
  sharpe: number | null;
  nw_sharpe: number | null;
  calmar: number | null;
  n: number;
}

interface ValidationData {
  updated_at: string;
  latest_signal: {
    date: string;
    in_market: boolean;
    small_nav_vs_ma16: number;
    holdings_all: string[];
    holdings_ex688: string[];
  } | null;
  all_market: Array<{ label: string; metrics: Metrics }>;
  ex688: Array<{ label: string; metrics: Metrics }>;
  cost_sensitivity: Array<{ label: string; metrics: Metrics }>;
  walk_forward: Array<{
    year: number;
    annual: number | null;
    maxdd: number | null;
    sharpe: number | null;
    nw_sharpe: number | null;
    holding: number | null;
    n: number;
  }>;
}

export default function AmountTimingValidationView() {
  const [data, setData] = useState<ValidationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .amountTimingValidation()
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        setError(String(err));
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="card text-subink text-sm">加载择时模型敏感度验证数据中…</div>;
  if (error) return <div className="card text-danger text-sm">数据加载失败: {error}</div>;
  if (!data || !data.latest_signal) {
    return (
      <div className="card text-subink text-sm">
        💡 暂无择时模型验证数据。请确认已在后端成功运行 <code>validate_amount_timing.py</code> 生成报告。
      </div>
    );
  }

  const { latest_signal, all_market, ex688, cost_sensitivity, walk_forward } = data;

  // Calculate deviation gauge width
  const deviationVal = latest_signal.small_nav_vs_ma16;
  const deviationAbs = Math.min(100, Math.abs(deviationVal) * 1000);

  return (
    <div className="space-y-6">
      {/* Latest signal summary metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="成交量择时决策 (Timing)"
          value={latest_signal.in_market ? "🟢 持仓 (IN MARKET)" : "🔴 空仓 (CASH)"}
          tone={latest_signal.in_market ? "ok" : "warn"}
          sub={`决策日: ${latest_signal.date}`}
        />
        <div className="card flex flex-col justify-between">
          <div>
            <div className="text-[12px] text-subink">趋势偏离度</div>
            <div className={`text-2xl font-bold mt-1 ${deviationVal < 0 ? "text-danger" : "text-ok"}`}>
              {(deviationVal * 100).toFixed(2)}%
            </div>
          </div>
          <div className="w-full bg-jilan/30 h-1.5 rounded-full mt-2 overflow-hidden" title="偏离阈值进度">
            <div 
              className={`h-full rounded-full ${deviationVal < 0 ? "bg-yinzhu" : "bg-songshi"}`} 
              style={{ width: `${deviationAbs}%` }} 
            />
          </div>
        </div>
        <MetricCard
          label="持仓组合大小 (All)"
          value={`${latest_signal.holdings_all.length} 只股票`}
          sub="量价非流动性溢价 Top 25"
        />
        <MetricCard
          label="持仓组合大小 (Ex 688)"
          value={`${latest_signal.holdings_ex688.length} 只股票`}
          sub="排除科创板股票后选股"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Scenario Comparison Table */}
          <Card title="择时策略场景敏感度审计 (Scenario Audits)">
            <div className="space-y-4">
              <div>
                <div className="text-[11.5px] text-brand font-semibold mb-1 uppercase tracking-wider">
                  A. 全市场交易池 (Full Universe)
                </div>
                <div className="overflow-x-auto border border-line rounded-lg shadow-sm">
                  <table className="w-full text-[12.5px]">
                    <thead>
                      <tr className="text-subink text-left bg-jilan border-b border-line">
                        <th className="py-2.5 px-3 font-semibold">场景 (Case)</th>
                        <th className="py-2.5 px-3 font-semibold text-right">年化收益</th>
                        <th className="py-2.5 px-3 font-semibold text-right">最大回撤</th>
                        <th className="py-2.5 px-3 font-semibold text-right">标准夏普</th>
                        <th className="py-2.5 px-3 font-semibold text-right">Newey-West夏普</th>
                        <th className="py-2.5 px-3 font-semibold text-right">卡玛比率</th>
                      </tr>
                    </thead>
                    <tbody>
                      {all_market.map((row) => (
                        <tr key={row.label} className="border-b border-line/60 hover:bg-jilan/10">
                          <td className="py-2.5 px-3 text-ink font-bold">{row.label}</td>
                          <td className="py-2.5 px-3 text-right font-mono text-songshi font-bold">
                            {row.metrics.annual != null ? pct(row.metrics.annual) : "—"}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-subink">
                            {row.metrics.maxdd != null ? pct(row.metrics.maxdd) : "—"}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-ink">
                            {row.metrics.sharpe != null ? num(row.metrics.sharpe) : "—"}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-brand font-semibold">
                            {row.metrics.nw_sharpe != null ? num(row.metrics.nw_sharpe) : "—"}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-ink">
                            {row.metrics.calmar != null ? num(row.metrics.calmar) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              <div>
                <div className="text-[11.5px] text-brand font-semibold mb-1 uppercase tracking-wider">
                  B. 排除科创板交易池 (Exclude STAR Board 688)
                </div>
                <div className="overflow-x-auto border border-line rounded-lg shadow-sm">
                  <table className="w-full text-[12.5px]">
                    <thead>
                      <tr className="text-subink text-left bg-jilan border-b border-line">
                        <th className="py-2.5 px-3 font-semibold">场景 (Case)</th>
                        <th className="py-2.5 px-3 font-semibold text-right">年化收益</th>
                        <th className="py-2.5 px-3 font-semibold text-right">最大回撤</th>
                        <th className="py-2.5 px-3 font-semibold text-right">标准夏普</th>
                        <th className="py-2.5 px-3 font-semibold text-right">Newey-West夏普</th>
                        <th className="py-2.5 px-3 font-semibold text-right">卡玛比率</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ex688.map((row) => (
                        <tr key={row.label} className="border-b border-line/60 hover:bg-jilan/10">
                          <td className="py-2.5 px-3 text-ink font-bold">{row.label}</td>
                          <td className="py-2.5 px-3 text-right font-mono text-songshi font-bold">
                            {row.metrics.annual != null ? pct(row.metrics.annual) : "—"}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-subink">
                            {row.metrics.maxdd != null ? pct(row.metrics.maxdd) : "—"}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-ink">
                            {row.metrics.sharpe != null ? num(row.metrics.sharpe) : "—"}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-brand font-semibold">
                            {row.metrics.nw_sharpe != null ? num(row.metrics.nw_sharpe) : "—"}
                          </td>
                          <td className="py-2.5 px-3 text-right font-mono text-ink">
                            {row.metrics.calmar != null ? num(row.metrics.calmar) : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </Card>

          {/* Walk-forward performance */}
          <Card title="年度滚动步进样本外验证 (Walk-Forward Out-of-Sample Performance)">
            <div className="overflow-x-auto border border-line rounded-lg shadow-sm">
              <table className="w-full text-[12.5px]">
                <thead>
                  <tr className="text-subink text-left bg-jilan border-b border-line">
                    <th className="py-2.5 px-3 font-semibold">年份 (Year)</th>
                    <th className="py-2.5 px-3 font-semibold text-right">年度收益</th>
                    <th className="py-2.5 px-3 font-semibold text-right">最大回撤</th>
                    <th className="py-2.5 px-3 font-semibold text-right">年度夏普</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Newey-West夏普</th>
                    <th className="py-2.5 px-3 font-semibold text-right">市场参与天数比</th>
                  </tr>
                </thead>
                <tbody>
                  {walk_forward.map((row) => (
                    <tr key={row.year} className="border-b border-line/60 hover:bg-jilan/10">
                      <td className="py-2.5 px-3 text-ink font-bold font-mono">{row.year}</td>
                      <td className={`py-2.5 px-3 text-right font-mono font-bold ${row.annual && row.annual > 0 ? "text-songshi" : "text-yinzhu"}`}>
                        {row.annual != null ? (row.annual >= 0 ? "+" : "") + pct(row.annual) : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-subink">
                        {row.maxdd != null ? pct(row.maxdd) : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-ink">
                        {row.sharpe != null ? num(row.sharpe) : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-brand font-semibold">
                        {row.nw_sharpe != null ? num(row.nw_sharpe) : "—"}
                      </td>
                      <td className="py-2.5 px-3 text-right font-mono text-ink">
                        {row.holding != null ? pct(row.holding, 1) : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          {/* Cost Sensitivity */}
          <Card title="交易磨损与摩擦敏感度分析">
            <div className="space-y-4">
              <div className="text-[12px] text-subink leading-relaxed">
                评估在不同买卖摩擦成本倍数下，二元择时策略的表现衰退路径（评估容量与换手阈值）：
              </div>
              <div className="space-y-3">
                {cost_sensitivity.map((row) => (
                  <div key={row.label} className="bg-[#FAF8F5]/85 border border-line p-3.5 rounded-xl space-y-1.5 shadow-sm hover:border-brand/40 transition-all">
                    <div className="flex justify-between items-center">
                      <span className="font-semibold text-ink font-mono">{row.label}</span>
                      <span className="text-[11px] text-subink font-medium">年化 {row.metrics.annual != null ? pct(row.metrics.annual) : "—"}</span>
                    </div>
                    <div className="flex justify-between text-[11px] text-subink border-t border-line/35 pt-1.5">
                      <span>夏普: <span className="text-ink font-mono font-medium">{row.metrics.sharpe != null ? num(row.metrics.sharpe) : "—"}</span></span>
                      <span>NW夏普: <span className="text-brand font-mono font-bold">{row.metrics.nw_sharpe != null ? num(row.metrics.nw_sharpe) : "—"}</span></span>
                      <span>回撤: <span className="text-ink font-mono font-medium">{row.metrics.maxdd != null ? pct(row.metrics.maxdd) : "—"}</span></span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          {/* Latest signals list */}
          <Card title="择时组合个股持仓 (Latest Signals)">
            <div className="space-y-4">
              <div>
                <div className="text-[11px] text-brand font-bold mb-1.5 uppercase tracking-wider">
                  全交易池 TOP 25 持仓:
                </div>
                <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto bg-bg/85 p-2.5 rounded-lg border border-line/60">
                  {latest_signal.holdings_all.map((c) => (
                    <code key={c} className="text-[11px] font-mono bg-white px-2 py-0.5 rounded border border-line text-subink hover:text-brand cursor-pointer">
                      {c}
                    </code>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-[11px] text-brand font-bold mb-1.5 uppercase tracking-wider">
                  排除科创板 (Ex 688) TOP 25 持仓:
                </div>
                <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto bg-bg/85 p-2.5 rounded-lg border border-line/60">
                  {latest_signal.holdings_ex688.map((c) => (
                    <code key={c} className="text-[11px] font-mono bg-white px-2 py-0.5 rounded border border-line text-subink hover:text-brand cursor-pointer">
                      {c}
                    </code>
                  ))}
                </div>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
