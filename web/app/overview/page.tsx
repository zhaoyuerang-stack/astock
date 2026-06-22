"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import Card from "@/components/ui/Card";
import StatusBanner from "@/components/ui/StatusBanner";
import DataTable, { type Column } from "@/components/ui/DataTable";
import { api, pct, num } from "@/lib/api";
import type {
  StrategyView,
  MarketStateView,
  FactorHealthView,
  DataQualityView,
  TradeReadinessView,
  TradePlanView,
  RiskReport,
} from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useWorkspaceStore } from "@/lib/workspaceStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

const FLOW = ["假设发现", "因子构建", "状态识别", "策略构建", "回测验证", "执行监控", "复盘迭代"];

// 信号表归一化行:bond(side) 与 plan(action) 异构数据统一为一种结构
type SignalRow = {
  dir: string;
  name: string;
  code: string;
  refPrice: number;
  sharesText: string;
  notionalText: string;
};

export default function OverviewPage() {
  const { mode } = useWorkspaceStore();
  const setContext = useAgent((s) => s.setContext);

  // R&D mode states
  const [strategies, setStrategies] = useState<StrategyView[]>([]);
  const [health, setHealth] = useState<FactorHealthView[]>([]);
  const [dq, setDq] = useState<DataQualityView | null>(null);

  // Operations mode states
  const [readiness, setReadiness] = useState<TradeReadinessView | null>(null);
  const [paperPlan, setPaperPlan] = useState<TradePlanView | null>(null);
  const [riskReport, setRiskReport] = useState<RiskReport | null>(null);

  // Shared state
  const [market, setMarket] = useState<MarketStateView | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(() => {
    setErr(null);
    if (mode === "ops") {
      Promise.all([
        api.marketState(),
        api.tradeReadiness(),
        api.paperPlan(),
        api.risk()
      ])
        .then(([m, tr, pp, rk]) => {
          setMarket(m);
          setReadiness(tr);
          setPaperPlan(pp);
          setRiskReport(rk);

          const actionTip = pp.bond
            ? (pp.bond.side === "HOLD" ? `继续持有 ${pp.bond.name}` : `${pp.bond.side} ${pp.bond.name}`)
            : pp.plan?.length > 0
            ? `${pp.plan[0].action} ${pp.plan[0].name}`
            : "今日无交易信号";
          setContext({
            page: "overview",
            title: "交易执行自适应助航",
            summary: `今日交易门禁：${tr.allowed_to_trade ? "【已就绪】" : "【已拦截】"}。建议信号：${actionTip}。前置风控总体判定：${rk.verdict}。`,
            evidence: [
              `前置准备度允许交易 (allowed_to_trade): ${tr.allowed_to_trade ? "YES" : "NO"}`,
              `市场状态建议动作: ${m.last_action}`,
              `当前持仓市值: ${pp.position_value.toFixed(0)}元 · NAV: ${pp.nav.toFixed(2)}`,
            ],
            risk: tr.allowed_to_trade ? [] : ["前置风控校验拦截被触发，日内路由锁定"],
            recommendation: tr.allowed_to_trade
              ? ["核对拟交易ETF/债券代码无误后允许下单", "关注日内预估滑点冲击"]
              : ["排除拦截门禁对应的模块数据", "如属极端行情或模型特殊原因，可前往系统设置执行人工签名签发"],
            nextActions: tr.allowed_to_trade
              ? ["签名授权日内执行计划", "触发日内行情盯盘"]
              : ["查询 Gate 6 冲击成本阈值", "检查本地 DuckDB 是否最新"],
          });
        })
        .catch((e) => setErr(String(e)));
    } else {
      Promise.all([
        api.strategies(),
        api.marketState(),
        api.strategyHealth(),
        api.dataQuality(),
        api.paperPlan()
      ])
        .then(([s, m, h, d, pp]) => {
          setStrategies(s);
          setMarket(m);
          setHealth(h);
          setDq(d);
          setPaperPlan(pp);

          const live = s.filter((x) => x.status === "在册").length;
          setContext({
            page: "overview",
            title: "量化研发实验室助手",
            summary: `已在册 ${live} 个因子策略版本; 当前市场定位「${m.last_action}」; DuckDB 数据质量校验「${d.verdict}」。`,
            evidence: h.map((x) => `${x.name}:夏普比率 ${num(x.sharpe)}(状态: ${x.trend})`),
            risk: d.severe_count > 0 ? [`DuckDB 包含真问题证券数: ${d.severe_count}只`] : [],
            recommendation: ["运行策略回测进行样本外检验", "对动量减速因子重新跑IC衰减"],
            nextActions: ["进入「因子研究」查看三级标签矩阵", "在数据中心编写DuckDB analysis"],
          });
        })
        .catch((e) => setErr(String(e)));
    }
  }, [mode, setContext]);

  useAutoRefresh(load);

  const bondHoldings = paperPlan?.positions?.filter((p) => p.asset === "etf" || p.code === "511010") || [];
  const stockHoldings = paperPlan?.positions?.filter((p) => p.asset !== "etf" && p.code !== "511010") || [];

  const holdingSummaryText = (() => {
    if (!paperPlan) return "—";
    const parts = [];
    if (stockHoldings.length > 0) {
      parts.push(`股票: ${stockHoldings.length} 只`);
    } else {
      parts.push(`股票: 0 只 (空仓)`);
    }
    if (bondHoldings.length > 0) {
      const bNames = bondHoldings.map((b) => `${b.name}(${b.shares}股)`).join(", ");
      parts.push(`防御债: ${bNames}`);
    }
    return parts.join(" · ");
  })();

  // Operations Desk View Rendering
  if (mode === "ops") {
    // 信号表:归一化 bond + plan 为统一行结构,异构合并在数据准备阶段完成
    const signalRows: SignalRow[] = [];
    if (paperPlan?.bond) {
      const b = paperPlan.bond;
      signalRows.push({
        dir: b.side,
        name: b.name,
        code: b.code,
        refPrice: b.ref_price,
        sharesText: b.side === "HOLD" ? `— (持仓 ${b.shares_held})` : String(b.est_shares),
        notionalText: b.side === "HOLD" ? "— (维持仓位)" : num(b.est_notional, 0),
      });
    }
    paperPlan?.plan?.forEach((item) => {
      signalRows.push({
        dir: item.action,
        name: item.name,
        code: item.code,
        refPrice: item.ref_price,
        sharesText: String(item.est_shares),
        notionalText: num(item.est_notional, 0),
      });
    });

    const positionRows = paperPlan?.positions ?? [];

    return (
      <div className="space-y-6">
        <PageHeader title="今日行动桌面" desc="量化策略日常操作执行与前置风控拦截审计 (Operations Desk)" />

        {err && <div className="card text-sm text-danger mb-4">API 错误: {err}<br />请确认后端已启动（uvicorn :8011）。</div>}

        {/* 1. 门禁结论横幅:唯一权威呈现「能否交易」 */}
        <StatusBanner
          status={readiness?.allowed_to_trade ? "ready" : "blocked"}
          title={readiness
            ? (readiness.allowed_to_trade ? "今日交易门禁：已就绪，允许交易" : "今日交易门禁：已拦截 (BLOCKED)")
            : "今日交易门禁：加载中…"}
          detail={readiness && market
            ? `市场状态：${market.last_action} · 前置风控判定：${riskReport?.verdict ?? "—"} · 数据质量 ${readiness.data_status} · 模型版本 ${readiness.model_version.toUpperCase()}`
            : undefined}
        />

        {/* 2. 顶部 KPI 行:把被埋的账户数字上提到最显眼处 */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <MetricCard label="总净资产 (NAV)" value={paperPlan ? num(paperPlan.nav, 2) : "—"} sub="模拟盘净值" />
          <MetricCard
            label="累计收益率 (Total PnL)"
            value={paperPlan ? `${paperPlan.total_return >= 0 ? "+" : ""}${(paperPlan.total_return * 100).toFixed(2)}%` : "—"}
            tone={(paperPlan?.total_return ?? 0) >= 0 ? "ok" : "danger"}
            sub="自建仓以来"
          />
          <MetricCard label="持仓市值 (MV)" value={paperPlan ? num(paperPlan.position_value, 2) : "—"} sub={holdingSummaryText} />
          <MetricCard label="可用现金 (Cash)" value={paperPlan ? num(paperPlan.cash, 2) : "—"} sub="可调度资金" />
        </div>

        {/* 3. 今日执行清单:统一为标准卡,Step3 去重(结论已由横幅承担) */}
        <Card title={<span className="font-quant tracking-wider uppercase text-[#5AA4AE]">今日策略执行清单 (Checklist)</span>} tone="ok">
          <div className="space-y-6">
            {/* Step 1 */}
            <div className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className="w-6 h-6 rounded-full bg-[#5AA4AE]/20 border border-[#5AA4AE]/50 text-[#5AA4AE] text-xs font-semibold flex items-center justify-center">1</div>
                <div className="w-[1px] flex-1 bg-[#3C4654]/40 my-1" />
              </div>
              <div className="pb-4">
                <h4 className="text-[13px] font-bold text-[#EFEFEF]">第一步：市场状态研判 [Regime]</h4>
                <div className="mt-1 flex items-center gap-2">
                  <span className="text-[12px] px-2 py-0.5 rounded bg-[#5AA4AE]/15 text-[#5AA4AE] border border-[#5AA4AE]/25 font-quant">
                    {market?.last_action || "等待中"}
                  </span>
                  <span className="text-[12px] text-[#547689]">
                    当前仓位指示: {market?.current_position === "cash" && bondHoldings.length > 0 ? "空仓防守 (已轮动持债)" : market?.current_position ?? "—"} ({holdingSummaryText})
                  </span>
                </div>
              </div>
            </div>

            {/* Step 2 */}
            <div className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className="w-6 h-6 rounded-full bg-[#88ABDA]/20 border border-[#88ABDA]/50 text-[#88ABDA] text-xs font-semibold flex items-center justify-center">2</div>
                <div className="w-[1px] flex-1 bg-[#3C4654]/40 my-1" />
              </div>
              <div className="pb-4">
                <h4 className="text-[13px] font-bold text-[#EFEFEF]">第二步：日内执行信号 [Signal Actions]</h4>
                <div className="mt-1 text-[12px] text-[#547689]">
                  {signalRows.length > 0 ? (
                    <span>共 {signalRows.length} 条信号，明细见下方「今日交易与轮动信号」表</span>
                  ) : (
                    <span className="text-subink">✓ 今日无交易与轮动信号，维持当前持仓</span>
                  )}
                </div>
              </div>
            </div>

            {/* Step 3:仅留前置校验明细,不再重述总结论 */}
            <div className="flex gap-4">
              <div className="flex flex-col items-center">
                <div className="w-6 h-6 rounded-full bg-[#FAC03D]/20 border border-[#FAC03D]/50 text-[#FAC03D] text-xs font-semibold flex items-center justify-center">3</div>
              </div>
              <div>
                <h4 className="text-[13px] font-bold text-[#EFEFEF]">第三步：前置风控拦截审计 [Compliance Guardrails]</h4>
                <div className="mt-1 text-[12px] text-[#547689]">
                  准备度校验: 数据质量 {readiness?.data_status === "可用" ? "可用" : "异常"} · 模型版本 {readiness?.model_version.toUpperCase() ?? "—"} · 明细见右侧「前置合规校验」
                </div>
              </div>
            </div>
          </div>
        </Card>

        {/* 4. 信号表(2/3) + 合规明细(1/3) */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
          <div className="lg:col-span-2">
            <Card title="今日交易与轮动信号 (Today's Signals)" right={`信号时间: ${paperPlan?.signal_date || "—"}`}>
              <DataTable<SignalRow>
                rows={signalRows}
                getRowKey={(r, i) => `${r.code}-${i}`}
                empty="今日无交易与轮动信号"
                columns={[
                  {
                    key: "dir",
                    header: "方向",
                    render: (r) => (
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        r.dir === "BUY" ? "bg-ok/10 text-ok" : r.dir === "HOLD" ? "bg-[#88ABDA]/10 text-[#88ABDA]" : "bg-danger/10 text-danger"
                      }`}>{r.dir}</span>
                    ),
                  },
                  {
                    key: "name",
                    header: "标的",
                    className: "font-medium text-[#EFEFEF]",
                    render: (r) => (
                      <>{r.name} <span className="text-[11px] text-[#547689] font-mono">{r.code}</span></>
                    ),
                  },
                  { key: "refPrice", header: "参考价格", align: "right", className: "text-[#EFEFEF] font-mono", render: (r) => r.refPrice },
                  { key: "sharesText", header: "估算股数", align: "right", className: "text-subink font-mono", render: (r) => r.sharesText },
                  { key: "notionalText", header: "估算名义额", align: "right", className: "text-subink font-mono", render: (r) => r.notionalText },
                ]}
              />
            </Card>
          </div>

          <Card title={<span className="font-quant">前置合规校验 (Compliance)</span>}>
            <div className="space-y-2.5 text-[12px]">
              <div className="flex justify-between items-center py-1.5 border-b border-cardline/30">
                <span className="text-subink">数据前置拦截 (Data Integrity)</span>
                <span className={`font-semibold ${readiness?.data_status === "可用" ? "text-ok" : "text-danger"}`}>
                  {readiness?.data_status === "可用" ? "PASS" : "BLOCK"}
                </span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-cardline/30">
                <span className="text-subink">模型合规授权 (Model SR 11-7)</span>
                <span className={`font-semibold ${readiness?.model_version === "approved" ? "text-ok" : "text-danger"}`}>
                  {readiness?.model_version.toUpperCase() === "APPROVED" ? "APPROVED" : "NO AUTH"}
                </span>
              </div>
              <div className="flex justify-between items-center py-1.5 border-b border-cardline/30">
                <span className="text-subink">资金流动性预估 (Liquidity)</span>
                <span className="font-semibold text-[#EFEFEF]">{readiness?.liquidity_status.toUpperCase() ?? "—"}</span>
              </div>
              <div className="flex justify-between items-center py-1.5">
                <span className="text-subink">人工签名确认 (Signoff Needed)</span>
                <span className="font-semibold text-[#EFEFEF]">{readiness?.human_approval_required ? "YES" : "NO"}</span>
              </div>
            </div>
          </Card>
        </div>

        {/* 5. 持仓明细:整行宽,消灭左下空白 */}
        <Card title="当前运行仓位明细 (Current Positions)">
          <DataTable<typeof positionRows[number]>
            rows={positionRows}
            getRowKey={(p, i) => `${p.code}-${i}`}
            empty="当前无持仓记录"
            columns={[
              {
                key: "name",
                header: "标的",
                className: "font-medium text-[#EFEFEF]",
                render: (p) => (<>{p.name} <span className="text-[11px] text-[#547689] font-mono">{p.code}</span></>),
              },
              { key: "shares", header: "持有股数", align: "right", className: "font-mono text-subink", render: (p) => p.shares },
              { key: "cost", header: "持仓成本", align: "right", className: "font-mono text-subink", render: (p) => p.cost.toFixed(3) },
              { key: "price", header: "当前市价", align: "right", className: "font-mono text-[#EFEFEF]", render: (p) => p.price?.toFixed(3) ?? "—" },
              { key: "mv", header: "持仓市值", align: "right", className: "font-mono text-[#EFEFEF]", render: (p) => num(p.mv, 0) },
              {
                key: "pnl",
                header: "持仓盈亏",
                align: "right",
                render: (p) => (
                  <span className={`font-mono font-medium ${p.pnl >= 0 ? "text-ok" : "text-danger"}`}>
                    {p.pnl >= 0 ? "+" : ""}{num(p.pnl, 2)}
                  </span>
                ),
              },
            ]}
          />
        </Card>
      </div>
    );
  }

  // Classic Quant Researcher R&D View Rendering
  const families = new Set(strategies.map((s) => s.family));
  const live = strategies.filter((s) => s.status === "在册").length;
  const cand = strategies.filter((s) => s.status === "候选").length;
  const decaying = health.filter((h) => h.trend !== "加速").length;

  // 研发态势综合判定:纯聚合 dq/台账/因子健康,不引入新判断口径(镜像 ops 门禁横幅)
  const rdStatus: "ready" | "attention" | "blocked" | "neutral" = !dq
    ? "neutral"
    : dq.verdict === "异常"
    ? "blocked"
    : dq.verdict === "可用" && dq.severe_count === 0
    ? "ready"
    : "attention";

  return (
    <div className="space-y-5">
      <PageHeader title="研发实验室中心" desc="全天候因子流水线健康度与在册策略母表台账 (R&D Laboratory)" />

      {/* 研发态势头条:让 rd 入口和 ops 一样,一眼回答「实验室是否健康、什么要我关注」 */}
      <StatusBanner
        status={rdStatus}
        title={dq ? `研发实验室态势:数据质量【${dq.verdict}】` : "研发实验室态势:加载中…"}
        detail={
          // 只放卡片没有的「综合判断 + 待关注项」,不重复下方 KPI 的原始计数
          [
            dq?.severe_count ? `数据真问题 ${dq.severe_count} 只待修复` : "数据流水线无真问题",
            health.length ? `因子减速 ${decaying}/${health.length}` : null,
            cand ? `候选 ${cand} 个待复核晋级` : null,
          ]
            .filter(Boolean)
            .join(" · ")
        }
      />

      {/* 研究生命周期参考图(非进度条):标注这是系统的概念地图,不是实时进度 */}
      <div className="card">
        <div className="text-[11px] text-subink mb-2">研究生命周期 · 概念参考</div>
        <div className="flex items-center gap-2 overflow-x-auto">
          {FLOW.map((n, i) => (
            <div key={n} className="flex items-center gap-2 shrink-0">
              <span className="text-[12px] text-ink px-2 py-1 rounded bg-bg border border-cardline">{n}</span>
              {i < FLOW.length - 1 && <span className="text-subink">→</span>}
            </div>
          ))}
        </div>
      </div>

      {err && <div className="card text-sm text-danger">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
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

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* 市场/持仓状态:统一用 Card 组件,与右侧因子健康度同属一套形状家族 */}
        <Card title="当前状态识别">
          {market ? (
            <>
              <div className="text-2xl font-semibold text-ink">
                {market.last_action === "空仓观望" && bondHoldings.length > 0 ? "空仓观望 (已轮动持债)" : market.last_action || "—"}
              </div>
              <div className="text-[12px] text-subink mt-1">
                仓位: {market.current_position} · {holdingSummaryText}
              </div>
              <div className="text-[12px] text-subink">信号日: {market.last_signal_date ?? "—"}</div>
            </>
          ) : (
            <div className="text-sm text-subink">—</div>
          )}
        </Card>

        {/* 策略健康度 */}
        <div className="md:col-span-2">
          <Card title={
            <span>因子健康度{health[0]?.as_of ? <span className="ml-2 text-[11px] text-subink/70 font-normal">数据截至 {health[0].as_of}（周期生成，非实时）</span> : null}</span>
          }>
            <DataTable<FactorHealthView>
              rows={health}
              getRowKey={(h) => h.name}
              empty="暂无因子健康度数据"
              columns={[
                { key: "name", header: "因子", className: "text-ink", render: (h) => h.name },
                { key: "sharpe", header: "夏普", align: "right", render: (h) => num(h.sharpe) },
                { key: "momentum_6m", header: "6M动量", align: "right", className: "text-subink", render: (h) => num(h.momentum_6m, 1) },
                { key: "trend", header: "趋势", align: "right", render: (h) => <span className={h.trend === "加速" ? "text-ok" : "text-warn"}>{h.trend}</span> },
              ]}
            />
          </Card>
        </div>
      </div>

      <Card title="母策略台账">
        <DataTable<StrategyView>
          rows={strategies}
          getRowKey={(s) => s.strategy_id}
          empty="暂无母策略记录"
          columns={[
            { key: "strategy_id", header: "策略", className: "text-ink", render: (s) => s.strategy_id },
            { key: "family", header: "家族", className: "text-subink", render: (s) => s.family_name || s.family },
            {
              key: "status",
              header: "状态",
              render: (s) => (
                <span className={s.status === "在册" ? "text-ok" : s.status === "退役" ? "text-danger" : "text-warn"}>
                  {s.status || "—"}
                </span>
              ),
            },
            { key: "regime", header: "适用市场", className: "text-subink truncate max-w-[280px]", render: (s) => s.regime || "—" },
          ]}
        />
      </Card>
    </div>
  );
}
