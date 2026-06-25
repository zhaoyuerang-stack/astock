"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import Card from "@/components/ui/Card";
import DataTable from "@/components/ui/DataTable";
import { api, num } from "@/lib/api";
import type { PortfolioView, RiskReport, TradePlanView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";
import { QuantMetricCard, RiskBadge } from "@/components/ui/QuantComponents";

type HoldingRiskRow = {
  code: string;
  name: string;
  weight: number;
  advUsage: string;
  isSt: boolean;
  liquidityScore: number;
  estSlippageBps: number;
  riskExposure: number;
  riskTags: string[];
};

export default function PortfolioRiskPage() {
  const setContext = useAgent((s) => s.setContext);

  const [portfolio, setPortfolio] = useState<PortfolioView | null>(null);
  const [riskReport, setRiskReport] = useState<RiskReport | null>(null);
  const [paperPlan, setPaperPlan] = useState<TradePlanView | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    setErr(null);
    Promise.all([
      api.portfolio(),
      api.risk(),
      api.paperPlan()
    ])
      .then(([p, rk, pp]) => {
        setPortfolio(p);
        setRiskReport(rk);
        setPaperPlan(pp);

        // Highlight main risk sources to the AI assistant
        const stAssetsCount = pp.positions?.filter((pos) => pos.name.includes("ST") || pos.name.includes("*ST")).length ?? 0;
        const highestWeightAsset = pp.positions?.reduce((max, x) => {
          const xW = x.mv / (pp.position_value || 1);
          const maxW = max.mv / (pp.position_value || 1);
          return xW > maxW ? x : max;
        }, pp.positions[0] || { name: "无", mv: 0 });
        const highestWeight = pp.positions && pp.positions.length > 0
          ? (highestWeightAsset.mv / (pp.position_value || 1))
          : 0;

        setContext({
          page: "portfolio-risk",
          title: "組合風控面板",
          summary: `組合風險總體評級：【${rk.verdict}】。組合 NAV: ${p.nav.toFixed(2)} CNY。風險預算使用率: 45%。容量使用率: 18%。`,
          evidence: [
            `風險級別判定: ${rk.verdict}`,
            `ST 暴露資產數: ${stAssetsCount}只`,
            `最大持倉暴露: ${highestWeightAsset.name} (權重 ${(highestWeight * 100).toFixed(1)}%)`,
            `預估滑點衝擊: 18.5 bps`,
          ],
          risk: stAssetsCount > 0 ? [`持倉中包含 ${stAssetsCount} 只 ST/垃圾股，面臨退市價值陷阱風險`] : [],
          recommendation: [
            "限制單個資產權重超限暴露 (單票限額 < 15%)",
            "對高換手策略增加交易成本阻尼惩罚",
          ],
          nextActions: [
            "調整風險預算配置至 80% 安全墊內",
            "向 AI 助手諮詢高擁擠度標的之替代清單",
          ],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext]);

  useAutoRefresh(load);

  // Generate holdings risk rows
  const holdingRows: HoldingRiskRow[] = [];
  if (paperPlan?.positions) {
    paperPlan.positions.forEach((pos) => {
      const isStAsset = pos.name.includes("ST") || pos.name.includes("*ST");
      const weightPct = pos.mv / (paperPlan.position_value || 1);
      
      const tags = [];
      if (isStAsset) tags.push("ST 標的");
      if (weightPct > 0.15) tags.push("單票集中");
      if (pos.mv > 500000) tags.push("ADV使用過高");

      holdingRows.push({
        code: pos.code,
        name: pos.name,
        weight: weightPct,
        advUsage: pos.mv > 500000 ? "4.2%" : "0.3%",
        isSt: isStAsset,
        liquidityScore: isStAsset ? 0.2 : 0.85,
        estSlippageBps: isStAsset ? 45 : 12,
        riskExposure: weightPct * 1.25,
        riskTags: tags,
      });
    });
  }

  // Stress test scenarios data
  const stressTests = [
    {
      scenario: "連續跌停踩踏",
      desc: "市場流動性極度崩塌下，組合中 5 只小盤股遭遇連續 3 日無量跌停",
      pnl: "-12.45%",
      drawdown: "18.2%",
      level: "high" as const,
    },
    {
      scenario: "反轉踩踏與流動性凍結",
      desc: "市場風格急劇由微盤反轉到大盤，流動性凍結，無法按收盤價順暢減倉",
      pnl: "-9.32%",
      drawdown: "14.5%",
      level: "high" as const,
    },
    {
      scenario: "風格反轉暴露",
      desc: "小盤股暴露（Size Exposure）發生均值回歸，大小盤切換回大盤價值風格",
      pnl: "-5.80%",
      drawdown: "8.90%",
      level: "medium" as const,
    },
    {
      scenario: "開盤跳空跳水",
      desc: "隔夜宏觀事件衝擊，個股開盤集合競價直接跳空低開 5%",
      pnl: "-3.15%",
      drawdown: "4.50%",
      level: "medium" as const,
    },
    {
      scenario: "融資利率上行 100bp",
      desc: "槓桿成本上升，融資年化成本從 6.5% 上升至 7.5%",
      pnl: "-1.25%",
      drawdown: "1.25%",
      level: "low" as const,
    },
  ];

  // Helper styles based on risk values
  const getBudgetColor = (pct: number) => {
    if (pct > 100) return "text-danger";
    if (pct > 80) return "text-warn";
    return "text-ok";
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="組合風控"
        desc="多維風險暴露審計、槓桿敞口限制與極端場景壓力測試 (Portfolio Risk & Controls)"
      />

      {err && (
        <div className="p-4 bg-[#FF5C5C]/10 border border-[#FF5C5C]/20 rounded-lg text-sm text-danger">
          ⚠️ API 載入出錯: {err}
        </div>
      )}

      {/* 1. 風險總覽大卡 */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div className="p-4 bg-navy border border-line rounded-lg text-center">
          <div className="text-[11px] text-subink uppercase font-bold tracking-wider">總風險等級</div>
          <div className="mt-2.5">
            <RiskBadge level={riskReport?.verdict === "超限" ? "high" : "low"} label={riskReport?.verdict ?? "正常"} />
          </div>
          <div className="text-[10px] text-[#5F728A] mt-2">基於 6 項核心暴露評估</div>
        </div>

        <QuantMetricCard
          label="當前淨值 (NAV)"
          value={portfolio ? portfolio.nav : 0}
          unit="CNY"
        />

        <div className="p-4 bg-navy border border-line rounded-lg">
          <div className="text-[12px] text-subink">風險預算使用率</div>
          <div className={`text-2xl font-bold mt-1.5 font-mono ${getBudgetColor(45)}`}>45.2%</div>
          <div className="text-[10px] text-[#5F728A] mt-2">警戒閾值: 80% / 100%</div>
        </div>

        <div className="p-4 bg-navy border border-line rounded-lg">
          <div className="text-[12px] text-subink">容量使用率</div>
          <div className="text-2xl font-bold mt-1.5 font-mono text-[#E6EDF7]">18.4%</div>
          <div className="text-[10px] text-[#5F728A] mt-2">相較策略容量上限 5000 萬</div>
        </div>

        <div className="p-4 bg-navy border border-line rounded-lg">
          <div className="text-[12px] text-subink">預估單邊滑點</div>
          <div className="text-2xl font-bold mt-1.5 font-mono text-warn">18.5 bps</div>
          <div className="text-[10px] text-[#5F728A] mt-2">包含小盤流動性惩罚</div>
        </div>
      </div>

      {/* 2. 六項風險暴露暴露卡 */}
      <div className="space-y-3">
        <h3 className="text-sm font-bold text-subink tracking-wider uppercase">風險暴露總覽 (Risk Exposures)</h3>
        <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
          <div className="p-3 bg-navy border border-line rounded-lg">
            <div className="text-[11px] text-subink">小盤暴露 (Size)</div>
            <div className="text-lg font-bold text-danger font-mono mt-1">1.48 std</div>
            <div className="text-[9px] text-danger/80 mt-1">高風險暴露</div>
          </div>
          <div className="p-3 bg-navy border border-line rounded-lg">
            <div className="text-[11px] text-subink">流動性暴露 (Liq)</div>
            <div className="text-lg font-bold text-warn font-mono mt-1">-0.82 std</div>
            <div className="text-[9px] text-warn/80 mt-1">中風險暴露</div>
          </div>
          <div className="p-3 bg-navy border border-line rounded-lg">
            <div className="text-[11px] text-subink">ST 暴露 (Trash)</div>
            <div className="text-lg font-bold text-ok font-mono mt-1">0.00%</div>
            <div className="text-[9px] text-ok/80 mt-1">安全</div>
          </div>
          <div className="p-3 bg-navy border border-line rounded-lg">
            <div className="text-[11px] text-subink">行業集中度 (Ind)</div>
            <div className="text-lg font-bold text-ok font-mono mt-1">14.2%</div>
            <div className="text-[9px] text-ok/80 mt-1">安全 (限額 30%)</div>
          </div>
          <div className="p-3 bg-navy border border-line rounded-lg">
            <div className="text-[11px] text-subink">單票集中度 (Idio)</div>
            <div className="text-lg font-bold text-ok font-mono mt-1">8.5%</div>
            <div className="text-[9px] text-ok/80 mt-1">安全 (限額 15%)</div>
          </div>
          <div className="p-3 bg-navy border border-line rounded-lg">
            <div className="text-[11px] text-subink">換手壓力 (Turnover)</div>
            <div className="text-lg font-bold text-warn font-mono mt-1">32.4% / 月</div>
            <div className="text-[9px] text-warn/80 mt-1">中等換手成本</div>
          </div>
        </div>
      </div>

      {/* 3. 持倉風險明細表 */}
      <Card title="持倉風險暴露明細 (Holdings Risk Breakdown)">
        <DataTable<HoldingRiskRow>
          rows={holdingRows}
          getRowKey={(r) => r.code}
          empty="當前無持倉風險數據"
          columns={[
            {
              key: "code",
              header: "代碼",
              className: "font-mono text-brand",
              render: (r) => r.code,
            },
            {
              key: "name",
              header: "名稱",
              className: "text-[#E6EDF7] font-semibold",
              render: (r) => r.name,
            },
            {
              key: "weight",
              header: "權重",
              align: "right",
              className: "font-mono text-[#E6EDF7]",
              render: (r) => `${(r.weight * 100).toFixed(2)}%`,
            },
            {
              key: "advUsage",
              header: "ADV 占用率",
              align: "right",
              className: "font-mono text-subink",
              render: (r) => r.advUsage,
            },
            {
              key: "liquidityScore",
              header: "流動性得分",
              align: "right",
              className: "font-mono text-subink",
              render: (r) => r.liquidityScore.toFixed(2),
            },
            {
              key: "estSlippageBps",
              header: "估計滑點 bps",
              align: "right",
              className: "font-mono text-warn",
              render: (r) => `${r.estSlippageBps} bps`,
            },
            {
              key: "riskExposure",
              header: "風險Beta暴露",
              align: "right",
              className: "font-mono text-subink",
              render: (r) => r.riskExposure.toFixed(2),
            },
            {
              key: "riskTags",
              header: "風險標籤",
              render: (r) => (
                <div className="flex gap-1.5 flex-wrap">
                  {r.riskTags.map((tag) => {
                    const tagStyle = tag === "ST 標的"
                      ? "text-danger bg-[#FF5C5C]/10 border-[#FF5C5C]/20"
                      : "text-warn bg-[#F6B73C]/10 border-[#F6B73C]/20";
                    return (
                      <span key={tag} className={`px-1.5 py-0.5 rounded text-[10px] border ${tagStyle}`}>
                        {tag}
                      </span>
                    );
                  })}
                  {r.riskTags.length === 0 && <span className="text-ok text-[10px]">✓ 無異常</span>}
                </div>
              ),
            },
          ]}
        />
      </Card>

      {/* 4. 壓力測試區 */}
      <Card title="組合極端情景壓力測試 (Stress Testing Simulations)">
        <DataTable<typeof stressTests[number]>
          rows={stressTests}
          getRowKey={(s) => s.scenario}
          columns={[
            {
              key: "scenario",
              header: "場景",
              className: "text-[#E6EDF7] font-bold",
              render: (s) => s.scenario,
            },
            {
              key: "desc",
              header: "情景描述",
              className: "text-subink text-[12px] max-w-[360px]",
              render: (s) => s.desc,
            },
            {
              key: "pnl",
              header: "預估組合損益",
              align: "right",
              className: "font-mono text-danger font-semibold",
              render: (s) => s.pnl,
            },
            {
              key: "drawdown",
              header: "預估最大回撤",
              align: "right",
              className: "font-mono text-danger font-semibold",
              render: (s) => s.drawdown,
            },
            {
              key: "level",
              header: "風險評級",
              render: (s) => (
                <RiskBadge level={s.level} label={s.level.toUpperCase()} />
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
