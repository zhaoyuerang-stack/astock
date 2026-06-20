"use client";

import { useEffect, useState } from "react";
import Card from "@/components/ui/Card";
import { api, pct, num } from "@/lib/api";

interface ShadowData {
  incubation: {
    strategy_family: string;
    registered_version: string;
    status: string;
    incubation_start_date: string;
    current_incubation_days: number;
    target_incubation_days: number;
    audit_checklist: Record<string, string>;
  };
  predictions: {
    updated_at: string;
    rankings: Array<{
      rank: number;
      industry: string;
      earnings_prediction_score: number;
    }>;
    bom_shocks: Array<{
      product_name: string;
      downstream_industry: string;
      raw_cost_shock: number;
      margin_shock: number;
      pricing_power: number;
      details: Array<{
        material: string;
        weight: number;
        price_change: number;
        cost_contribution: number;
      }>;
    }>;
    framework_scores: Record<
      string,
      {
        quality_score: number;
        stage: string;
        profile: {
          penetration_rate: number;
          capex_growth_3y: number;
          cr3_concentration: number;
          days_of_inventory: number;
          historical_avg_doi: number;
          barrier_to_entry: number;
        };
      }
    >;
  };
  performance: {
    dates: string[];
    shadow_nav: number[];
    benchmark_nav: number[];
  };
}

export default function ShadowIncubationView() {
  const [data, setData] = useState<ShadowData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .shadowIncubation()
      .then((res) => {
        setData(res);
        setLoading(false);
      })
      .catch((err) => {
        setError(String(err));
        setLoading(false);
      });
  }, []);

  if (loading) return <div className="card text-subink text-sm">加载影子策略孵化与本体分析数据中…</div>;
  if (error) return <div className="card text-danger text-sm">数据加载失败: {error}</div>;
  if (!data || !data.incubation.strategy_family) {
    return (
      <div className="card text-subink text-sm">
        💡 暂无影子孵化策略。请确认已在后端成功运行 <code>run_ontology_shadow_pipeline.py</code> 生成数据。
      </div>
    );
  }

  const { incubation, predictions, performance } = data;

  // Render SVG NAV Curve in Light theme styles
  const renderNavChart = () => {
    if (!performance || !performance.dates || performance.dates.length === 0) {
      return <div className="text-center py-6 text-subink">暂无影子业绩表现曲线数据。</div>;
    }

    const { dates, shadow_nav, benchmark_nav } = performance;
    const width = 600;
    const height = 240;
    const padding = 40;

    const allValues = [...shadow_nav, ...benchmark_nav];
    const maxVal = Math.max(...allValues, 1.2);
    const minVal = Math.min(...allValues, 0.8);
    const range = maxVal - minVal || 1;

    const getX = (index: number) => padding + (index / (dates.length - 1)) * (width - padding * 2);
    const getY = (val: number) => height - padding - ((val - minVal) / range) * (height - padding * 2);

    const shadowPoints = shadow_nav.map((v, i) => `${getX(i)},${getY(v)}`).join(" ");
    const benchmarkPoints = benchmark_nav.map((v, i) => `${getX(i)},${getY(v)}`).join(" ");

    // Draw horizontal grid lines
    const yGridValues = [minVal, minVal + range * 0.25, minVal + range * 0.5, minVal + range * 0.75, maxVal];

    return (
      <div className="space-y-2">
        <div className="flex justify-between items-center text-[12px] text-subink">
          <div className="flex gap-4">
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-0.5 bg-brand" />
              影子本体策略 NAV (最新: {num(shadow_nav[shadow_nav.length - 1], 3)})
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-3 h-0.5 bg-subink" />
              行业等权 Benchmark NAV (最新: {num(benchmark_nav[benchmark_nav.length - 1], 3)})
            </span>
          </div>
          <div>样本期: {dates[0]} 至 {dates[dates.length - 1]}</div>
        </div>
        <div className="relative border border-line bg-[#FAF8F5] rounded-xl overflow-hidden p-2 shadow-inner">
          <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-auto">
            {/* Grid lines */}
            {yGridValues.map((v, i) => (
              <g key={i}>
                <line
                  x1={padding}
                  y1={getY(v)}
                  x2={width - padding}
                  y2={getY(v)}
                  stroke="#EFECE3"
                  strokeWidth="0.8"
                  strokeDasharray="4"
                />
                <text
                  x={padding - 5}
                  y={getY(v) + 3}
                  fill="#555147"
                  fontSize="9"
                  fontFamily="monospace"
                  textAnchor="end"
                >
                  {num(v, 2)}
                </text>
              </g>
            ))}

            {/* X-axis dates */}
            {[0, Math.floor(dates.length / 2), dates.length - 1].map((idx) => (
              <text
                key={idx}
                x={getX(idx)}
                y={height - 12}
                fill="#555147"
                fontSize="9"
                textAnchor={idx === 0 ? "start" : idx === dates.length - 1 ? "end" : "middle"}
              >
                {dates[idx]}
              </text>
            ))}

            {/* Paths */}
            <polyline fill="none" stroke="#A7AAA1" strokeWidth="1.5" points={benchmarkPoints} />
            <polyline fill="none" stroke="#CC5D20" strokeWidth="2.5" points={shadowPoints} />
          </svg>
        </div>
      </div>
    );
  };

  const passedGates = Object.values(incubation.audit_checklist).filter((v) => v === "PASS").length;
  const totalGates = Object.keys(incubation.audit_checklist).length;
  const readinessIndex = totalGates > 0 ? (passedGates / totalGates) * 100 : 0;

  return (
    <div className="space-y-6">
      {/* Strategy header info */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-[#FAF8F5] border border-line rounded-xl p-4 flex flex-col justify-between shadow-sm">
          <div>
            <div className="text-[11px] text-subink uppercase tracking-wider">孵化策略</div>
            <div className="text-md font-bold text-ink mt-1">基于本体与BOM产业链传导</div>
          </div>
          <div className="text-[12px] text-brand font-mono font-bold mt-2">
            ID: {incubation.strategy_family} {incubation.registered_version}
          </div>
        </div>

        <div className="bg-[#FAF8F5] border border-line rounded-xl p-4 flex flex-col justify-between shadow-sm">
          <div>
            <div className="text-[11px] text-subink uppercase tracking-wider">孵化进度</div>
            <div className="text-2xl font-mono font-bold text-warn mt-1">
              {incubation.current_incubation_days} / {incubation.target_incubation_days} 天
            </div>
          </div>
          <div className="text-[11px] text-subink mt-1">开始日: {incubation.incubation_start_date}</div>
        </div>

        <div className="bg-[#FAF8F5] border border-line rounded-xl p-4 flex flex-col justify-between shadow-sm">
          <div>
            <div className="text-[11px] text-subink uppercase tracking-wider">在册状态</div>
            <div className="text-md font-bold text-warn mt-2 flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full bg-warn animate-pulse" />
              {incubation.status} (影子观察期)
            </div>
          </div>
          <div className="text-[11px] text-subink mt-1">不计入主模拟盘选股权重</div>
        </div>

        <div className="bg-[#FAF8F5] border border-line rounded-xl p-4 flex flex-col justify-between shadow-sm">
          <div>
            <div className="text-[11px] text-subink uppercase tracking-wider">9-Gate 预备审计</div>
            <div className="text-2xl font-mono font-bold text-ok mt-1">
              {passedGates} / {totalGates} 通
            </div>
          </div>
          <div className="w-full bg-jilan/30 h-1.5 rounded-full mt-2 overflow-hidden" title={`就绪度: ${readinessIndex.toFixed(0)}%`}>
            <div className="bg-songshi h-full rounded-full" style={{ width: `${readinessIndex}%` }} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* NAV performance */}
          <Card title="影子策略回测/前瞻业绩表现 (Incubation Shadow Performance)">
            {renderNavChart()}
          </Card>

          {/* BOM chain cost propagation */}
          <Card title="BOM 驱动的产业链因果成本与毛利冲击 (BOM Cost Propagation Shocks)">
            <div className="bg-jilan/20 border border-line text-[11.5px] text-subink rounded-lg p-3 mb-4 leading-relaxed flex items-start gap-2">
              <span className="text-brand">💡</span>
              <div>
                <strong>设计申明（严谨性原则）：</strong> 本系统不含也无法获取单家上市公司的非公开商业机密 BOM 数据。本分析采用量化研究中通用的<strong>典型行业代表性产品 BOM 结构模板</strong>（来源于主流行业研报共识，如动力电池成本构成），结合上游资产的即期价格变化，用以测算<strong>行业层面的中下游综合毛利冲击（Margin Shock）</strong>，用作行业 Alpha 选股因子的风险修正。
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-[13px]">
                <thead>
                  <tr className="text-subink text-left border-b border-line">
                    <th className="py-2 px-3 font-semibold">制成品</th>
                    <th className="py-2 px-3 font-semibold">所属下游行业</th>
                    <th className="py-2 px-3 font-semibold text-right">定价权</th>
                    <th className="py-2 px-3 font-semibold text-right">上游BOM原料涨幅</th>
                    <th className="py-2 px-3 font-semibold text-right">下游毛利冲击 (Margin Shock)</th>
                  </tr>
                </thead>
                <tbody>
                  {predictions.bom_shocks.map((s, idx) => {
                    const hasHighRisk = s.margin_shock < -0.015 && s.pricing_power < 1.5;
                    return (
                      <tr key={idx} className="border-b border-line/60 hover:bg-jilan/10">
                        <td className="py-2.5 px-3 font-semibold text-ink">{s.product_name}</td>
                        <td className="py-2.5 px-3 text-subink">{s.downstream_industry}</td>
                        <td className="py-2.5 px-3 text-right font-mono text-brand font-bold">{num(s.pricing_power)}</td>
                        <td className="py-2.5 px-3 text-right font-mono text-yinzhu">+{pct(s.raw_cost_shock)}</td>
                        <td className="py-2.5 px-3 text-right font-mono text-yinzhu font-bold whitespace-nowrap">
                          {pct(s.margin_shock)}
                          {hasHighRisk && (
                            <span className="ml-1.5 px-1.5 py-0.5 rounded bg-yinzhu/10 text-yinzhu text-[9px] font-semibold border border-yinzhu/20">
                              高风险
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          {/* Industry quality profiles */}
          <Card title="分析师行业质地基本面画像 (Analyst Framework Profile Scores)">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(predictions.framework_scores).map(([name, scoreObj]) => {
                const doiWarning = scoreObj.profile.days_of_inventory > scoreObj.profile.historical_avg_doi;
                return (
                  <div key={name} className="bg-[#FAF8F5]/85 border border-line p-3.5 rounded-xl space-y-2 shadow-sm hover:border-brand/40 transition-colors">
                    <div className="flex justify-between items-center">
                      <span className="font-bold text-ink">{name}</span>
                      <span className="text-[10px] text-white px-2 py-0.5 rounded font-semibold bg-brand shadow-sm">
                        {scoreObj.stage.toUpperCase()}
                      </span>
                    </div>
                    <div className="flex justify-between items-baseline pt-1">
                      <span className="text-[11px] text-subink">行业质地综合得分:</span>
                      <span className="text-lg font-mono font-bold text-brand">{num(scoreObj.quality_score, 3)}</span>
                    </div>
                    <div className="border-t border-line/40 pt-2 space-y-1.5 text-[11px]">
                      <div className="space-y-0.5">
                        <div className="flex justify-between text-subink">
                          <span>终端渗透率:</span>
                          <span className="font-mono text-ink">{pct(scoreObj.profile.penetration_rate, 0)}</span>
                        </div>
                        <div className="w-full bg-jilan/20 h-1 rounded-full overflow-hidden">
                          <div className="bg-brand h-full rounded-full" style={{ width: `${scoreObj.profile.penetration_rate * 100}%` }} />
                        </div>
                      </div>

                      <div className="flex justify-between">
                        <span className="text-subink">3Y CapEx 资本开支:</span>
                        <span className={`font-mono font-bold ${scoreObj.profile.capex_growth_3y >= 0 ? "text-songshi" : "text-yinzhu"}`}>
                          {scoreObj.profile.capex_growth_3y >= 0 ? "+" : ""}
                          {pct(scoreObj.profile.capex_growth_3y, 0)}
                        </span>
                      </div>

                      <div className="space-y-0.5">
                        <div className="flex justify-between text-subink">
                          <span>行业集中度 CR3:</span>
                          <span className="font-mono text-ink">{pct(scoreObj.profile.cr3_concentration, 0)}</span>
                        </div>
                        <div className="w-full bg-jilan/20 h-1 rounded-full overflow-hidden">
                          <div className="bg-brand h-full rounded-full" style={{ width: `${scoreObj.profile.cr3_concentration * 100}%` }} />
                        </div>
                      </div>

                      <div className="flex justify-between">
                        <span className="text-subink">DOI 库销比天数:</span>
                        <span className={`font-mono ${doiWarning ? "text-yinzhu font-semibold" : "text-ink"}`}>
                          {scoreObj.profile.days_of_inventory}天 (均值{scoreObj.profile.historical_avg_doi}天)
                          {doiWarning && <span className="text-[9px] ml-0.5" title="库存偏高">↑</span>}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-subink">准入门槛与壁垒:</span>
                        <span className="font-mono text-ink font-semibold">{num(scoreObj.profile.barrier_to_entry, 2)}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>

        {/* Right Column: 9-Gate Checklist & Rankings */}
        <div className="space-y-6">
          <Card title="9-Gate 预备审计检查表">
            <div className="space-y-3">
              {Object.entries(incubation.audit_checklist).map(([gate, status]) => (
                <div key={gate} className="flex justify-between items-center text-[12.5px] border-b border-line/45 pb-2">
                  <span className="font-mono text-subink">{gate}</span>
                  <span
                    className={`text-[11px] px-2 py-0.5 rounded font-semibold border ${
                      status === "PASS"
                        ? "bg-songshi/10 text-songshi border-songshi/25"
                        : "bg-jilan/20 text-subink border-line/50"
                    }`}
                  >
                    {status === "PASS" ? "已过审计" : status}
                  </span>
                </div>
              ))}
            </div>
          </Card>

          <Card title="本体推理行业未来业绩景气度排名">
            <div className="space-y-3">
              {predictions.rankings.map((r) => (
                <div key={r.industry} className="flex items-center justify-between border-b border-line/45 pb-2.5">
                  <div className="flex items-center gap-3">
                    <span
                      className={`w-5 h-5 rounded-full flex items-center justify-center text-[11px] font-bold shadow-sm ${
                        r.rank === 1 ? "bg-brand text-white" : "bg-jilan/55 text-subink"
                      }`}
                    >
                      {r.rank}
                    </span>
                    <span className="font-semibold text-ink">{r.industry}</span>
                  </div>
                  <div className="text-right">
                    <div className="text-[13px] font-mono font-bold text-brand">
                      {r.earnings_prediction_score >= 0 ? "+" : ""}
                      {num(r.earnings_prediction_score, 4)}
                    </div>
                    <div className="text-[10px] text-subink">因果传导期望</div>
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
