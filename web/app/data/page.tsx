"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import Card from "@/components/ui/Card";
import StatusBanner from "@/components/ui/StatusBanner";
import DataTable from "@/components/ui/DataTable";
import { api, pct } from "@/lib/api";
import { latestDateFromRange } from "@/lib/freshness";
import type { DataQualityView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

interface DimensionItem {
  name: string;
  file: string;
  rows: string;
  coverage: string;
  span: string;
  update: string;
  status: "active" | "warning" | "error" | "meta";
}

interface DimensionCategory {
  category: string;
  icon: string;
  items: DimensionItem[];
}

const DIMENSIONS_CATALOG: DimensionCategory[] = [
  {
    category: "价量与衍生基础指标",
    icon: "📈",
    items: [
      { name: "后复权日线 OHLCV", file: "price/daily_all.parquet", rows: "1,307 万行", coverage: "5,207 只", span: "2010 年至今", update: "日增量 (T+1收盘价)", status: "active" },
      { name: "复权因子", file: "adj_factor/adj_factor_all.parquet", rows: "1,466 万行", coverage: "5,793 只", span: "2010 年至今", update: "日增量", status: "active" },
      { name: "每日基础指标 (PE/PB/换手)", file: "daily_basic/daily_basic_all.parquet", rows: "1,391 万行", coverage: "5,789 只", span: "2010 年至今", update: "日更 (Tushare每日价量基本指标)", status: "active" },
      { name: "个股资金流", file: "moneyflow/moneyflow_all.parquet", rows: "1,366 万行", coverage: "5,664 只", span: "2010 年至今", update: "日更", status: "active" },
      { name: "停/复牌与涨跌停记录", file: "market/stk_limit_all.parquet", rows: "1,648 万 / 46 万行", coverage: "全市场", span: "2010 年至今", update: "日更", status: "active" }
    ]
  },
  {
    category: "基本面与财务数据",
    icon: "📋",
    items: [
      { name: "利润表 (Income Sheet)", file: "financials/income_all.parquet", rows: "30.9 万行", coverage: "5,207 只", span: "1990 年至今", update: "季度自动补全", status: "active" },
      { name: "资产负债表 (Balance Sheet)", file: "financials/balancesheet_all.parquet", rows: "25.5 万行", coverage: "5,207 只", span: "2001 年至今", update: "季度自动补全", status: "active" },
      { name: "现金流量表 (Cashflow)", file: "financials/cashflow_all.parquet", rows: "27.9 万行", coverage: "5,207 只", span: "2001 年至今", update: "季度自动补全", status: "active" },
      { name: "财务分析指标 (派生)", file: "financials/fina_indicator_all.parquet", rows: "23.3 万行", coverage: "5,207 只", span: "2002 年至今", update: "季度自动补全", status: "active" }
    ]
  },
  {
    category: "资金与持仓变动",
    icon: "🤝",
    items: [
      { name: "融资融券余额 (两融)", file: "capital/margin_all.parquet", rows: "634 万行", coverage: "4,556 只", span: "2010 年至今", update: "交易所日更", status: "active" },
      { name: "股东人数", file: "holder/holdernumber_all.parquet", rows: "47.3 万行", coverage: "5,207 只", span: "1993 年至今", update: "季度更新", status: "active" },
      { name: "解禁股与公司高管持股变动", file: "holder/share_float_all.parquet", rows: "1,010 万行", coverage: "全市场", span: "2005 年至今", update: "定期更新", status: "active" },
      { name: "分红派息 / 业绩预告与快报", file: "corp_action/dividend_all.parquet", rows: "16.2 万 / 11.5 万行", coverage: "5,196 只", span: "1991 年至今", update: "自动拉取", status: "active" },
      { name: "北向持股明细", file: "capital/northbound_all.parquet", rows: "67.5 万行", coverage: "774 只", span: "2017-03-16 ~ 2024-08-16", update: "接口停用 (已停更)", status: "error" }
    ]
  },
  {
    category: "宏观、指数与元数据",
    icon: "🌐",
    items: [
      { name: "指数与 ETF 日线", file: "index/index_daily_all.parquet", rows: "8 条核心指数", coverage: "指数与跨资产ETF", span: "1993 年至今", update: "日更 (Tushare `fund_daily` 增量)", status: "active" },
      { name: "宏观指标 (CPI/PPI/M2/Shibor)", file: "macro/cn_cpi.parquet", rows: "CPI/PPI/M2/Shibor/港通净买", coverage: "宏观层面", span: "2001 年至今", update: "月更/日更 (Lag 1月防未来)", status: "active" },
      { name: "股票代码表 / 上市日期", file: "meta/codes.parquet", rows: "全市场基础表", coverage: "元数据", span: "当前状态", update: "定期拉取", status: "meta" },
      { name: "ST 历史 / 交易日历", file: "meta/st_history.parquet", rows: "ST记录与SSE交易日历", coverage: "元数据", span: "2010 ~ 2030", update: "静态快照/日更", status: "meta" },
      { name: "申万一级与二级行业成份股映射", file: "meta/industry.parquet", rows: "5,199 行", coverage: "全市场活跃个股", span: "申万2021标准", update: "定期拉取 / 静态快照", status: "meta" }
    ]
  },
  {
    category: "研报因果与替代数据",
    icon: "🔬",
    items: [
      { name: "研报 PDF 收件箱去重状态", file: "research_pdf/_inbox_state.json", rows: "Hash 去重库", coverage: "研报文件管理", span: "PDF 解析日志", update: "增量扫描更新", status: "active" },
      { name: "研报 NLP 定性逻辑传导链", file: "research_signals/logic_chains/*.json", rows: "因果传导节点", coverage: "周期品/大消费/科技", span: "因果关系图谱", update: "研报解析重建", status: "active" }
    ]
  }
];

const NODES_INFO: Record<string, { title: string; desc: string; type: "Source" | "Lake" | "Alignment" | "Production" }> = {
  tushare_api: { title: "Tushare API 数据源", desc: "全市场日频行情、上市元数据与申万行业分类的抓取接口，数据吞吐量在千万级。受 Tushare 积分限速与特色接口墙监控约束。", type: "Source" },
  pdf_reports: { title: "卖方研报 PDF 源", desc: "自动抓取的公开券商个股与行业研报 PDF 临时收件箱，用于提取行业传导因子及概念链条。", type: "Source" },
  daily_all_parquet: { title: "行情 Parquet 湖", desc: "存储全历史后复权 OHLCV 价量数据。每日盘后由 Tushare 日线接口增量更新并覆盖，支持 DuckDB 即席复核。", type: "Lake" },
  fundamental_batch: { title: "财务 Parquet 湖", desc: "存储上市公司的三表数据与比率特征（由 yjbb_em 自动合并整理），包含 5,200+ 股票的公告披露流。", type: "Lake" },
  industry_parquet: { title: "行业映射表", desc: "存储个股到申万一级/二级行业成分股映射表（共 5,199 行活跃对齐数据），为景气度因子合并与组合行业中性化提供基础元数据。", type: "Lake" },
  pdf_inbox: { title: "研报 Inbox 与哈希库", desc: "存放已下载 PDF 和 _inbox_state.json。去重记录确保每篇研报的 API NLP 逻辑链提取仅处理一次，失败则进入 failures 队列。", type: "Lake" },
  price_align: { title: "行情 T+1 对齐", desc: "价量特征计算时，强制使用 T 日盘后已收盘收盘价。行情信号在 T+1 日开盘/收盘生效，防范任何盘中未来函数。", type: "Alignment" },
  fina_align: { title: "财务防未来公告对齐", desc: "系统核心数据不变量守卫。不采用财报的自然季度日期，而是基于实际披露日期（avail_date）进行向后横截面 ffill，杜绝财报时间穿越。", type: "Alignment" },
  nlp_align: { title: "NLP 因果聚合", desc: "将各券商研报因果传导节点聚合为行业级状态（如飞天茅台批价、晶圆开工率），计算分析师共识度并汇入知识图谱。", type: "Alignment" },
  alpha_dev: { title: "因子研发池 (factors/alpha)", desc: "供回测引擎及 AutoResearch 工厂使用的多因子研发池。利用 data_lake 行情与财务特征合成时序/横截面 Alpha。", type: "Production" },
  causal_pred: { title: "因果本体预测 (Predictor)", desc: "贝叶斯因果推理。从上游供需、库存、价格传导状态，推算下游行业业绩释放概率，直接驱动行业影子孵化（SHADOW）。", type: "Production" },
  run_daily_prod: { title: "日更生产 (run_daily.py)", desc: "生产信号日更执行模块。消费对齐层数据，计算 LIVE 策略的最新股票调仓信号，若数据健康度 triage block 则自动降级为草稿并警告。", type: "Production" }
};

export default function DataPage() {
  const [dq, setDq] = useState<DataQualityView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [selectedCat, setSelectedCat] = useState(0);
  const [selectedNode, setSelectedNode] = useState<string | null>("fina_align");
  const setContext = useAgent((s) => s.setContext);

  const load = useCallback(() => {
    api
      .dataQuality()
      .then((d) => {
        setDq(d);
        setContext({
          page: "data",
          title: "数据 QA 助手",
          summary: `全市场 ${d.total} 只,干净 ${d.clean}(${pct(d.clean_ratio)})。判定:${d.verdict}。`,
          evidence: [
            `真问题(负价/OHLC错):${d.severe_count} 只`,
            `跳变标记:${d.jump_count} 处(多为除权/涨跌停,A股正常现象)`,
            d.duckdb?.available ? `DuckDB 即席复核:${d.duckdb.rows?.toLocaleString()} 行 / ${d.duckdb.codes} 只 / 负价 ${d.duckdb.nonpositive_close} 行` : "DuckDB 未接入",
          ],
          risk: d.severe_count > 0 ? [`${d.severe_count} 只存在负价/OHLC逻辑错,需修复`] : [],
          recommendation: ["跳变标记不等于脏数据,勿据 clean_ratio 误判", "回测前确认 severe=0 的标的不在票池"],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext]);
  useAutoRefresh(load);

  const tone = dq ? (dq.verdict === "可用" ? "ok" : dq.verdict === "关注" ? "warn" : "danger") : "default";
  const latestDataDate = latestDateFromRange(dq?.duckdb?.date_range);

  const renderNodeButton = (id: string, label: string) => {
    const isSelected = selectedNode === id;
    const type = NODES_INFO[id].type;
    let typeColor = "border-cardline text-subink hover:border-ink hover:text-ink";
    if (type === "Source") {
      typeColor = isSelected ? "bg-amber-500/10 border-amber-500/50 text-amber-600 font-semibold" : "border-amber-500/20 text-subink hover:border-amber-500/60";
    } else if (type === "Lake") {
      typeColor = isSelected ? "bg-emerald-500/10 border-emerald-500/50 text-emerald-600 font-semibold" : "border-emerald-500/20 text-subink hover:border-emerald-500/60";
    } else if (type === "Alignment") {
      typeColor = isSelected ? "bg-indigo-500/10 border-indigo-500/50 text-indigo-600 font-semibold" : "border-indigo-500/20 text-subink hover:border-indigo-500/60";
    } else if (type === "Production") {
      typeColor = isSelected ? "bg-[#88ABDA]/25 border-[#88ABDA]/60 text-[#88ABDA] font-semibold" : "border-[#88ABDA]/30 text-subink hover:border-[#88ABDA]/70";
    }

    return (
      <button
        onClick={() => setSelectedNode(id)}
        className={`w-full text-left px-3 py-2 rounded-[8px] text-[11px] font-mono transition-all duration-200 border shadow-sm ${typeColor}`}
      >
        {label}
      </button>
    );
  };

  return (
    <div>
      <PageHeader title="数据中心" desc="数据基础设施、质量分诊与数据流动血缘图 ( validate_final + DuckDB 即席复核)" />
      {err && <div className="card text-sm text-danger mb-4">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}
      {!dq && !err && <div className="card text-sm text-subink">加载中…</div>}

      {dq && (
        <>
          {/* 数据中心态势头条:一眼回答「数据能不能流向生产/回测」——rd 流水线第一道闸门 */}
          <div className="mb-5">
            <StatusBanner
              status={dq.production_blocked ? "blocked" : dq.backtest_blocked ? "attention" : "ready"}
              title={
                dq.production_blocked
                  ? "数据中心:生产信号已阻断"
                  : dq.backtest_blocked
                  ? "数据中心:因子回测已阻断"
                  : "数据中心:生产与回测通路双绿灯"
              }
              detail={
                dq.production_blocked
                  ? `数据时效或质量触发防线,今日正式调仓信号已降级为草稿 · 质量判定【${dq.verdict}】· 真问题 ${dq.severe_count} 只`
                  : dq.backtest_blocked
                  ? `数据质量降至临界线以下,回测引擎禁止运行以防前瞻/过拟合 · 质量判定【${dq.verdict}】`
                  : `生产日更与回测引擎通路双绿灯 · 质量判定【${dq.verdict}】`
              }
            />
          </div>

          {/* 状态徽章网格 */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-5">
            <MetricCard label="全市场标的" value={String(dq.total)} sub="data_lake 全口径" />
            <MetricCard label="质量评分(clean)" value={pct(dq.clean_ratio, 1)} sub={`${dq.clean}/${dq.total} 干净`} />
            <MetricCard label="真问题标的" value={String(dq.severe_count)} tone={dq.severe_count > 0 ? "danger" : "ok"} sub="负价/OHLC错" />
            <MetricCard label="最新数据日" value={latestDataDate} tone="ok" sub={dq.duckdb?.available ? "daily_all.parquet" : "等待 DuckDB 复核"} />
            <MetricCard label="可用判定" value={dq.verdict} tone={tone as any} sub="根据严重度分诊" />
          </div>

          {/* 故障分诊推荐修复 */}
          {dq.triage_summary?.suggested_commands && dq.triage_summary.suggested_commands.length > 0 && (
            <Card title="🛠️ 自动数据修复推荐命令 (Suggested Auto-Repairs)" className="mb-5">
              <div className="space-y-2">
                <p className="text-[12px] text-subink">系统根据最新的质量分诊日志，检测到可由后台命令行自动恢复的问题，建议运行：</p>
                {dq.triage_summary.suggested_commands.map((cmd: string, idx: number) => (
                  <div key={idx} className="flex items-center justify-between bg-bg border border-cardline rounded-lg p-2.5 font-mono text-[11px] text-subink select-all">
                    <span>{cmd}</span>
                    <button
                      onClick={() => navigator.clipboard.writeText(cmd)}
                      className="ml-4 px-2 py-1 rounded bg-[#88ABDA]/15 text-[#88ABDA] hover:bg-[#88ABDA]/25 transition text-[10px] font-sans"
                    >
                      复制
                    </button>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* 人工审计清单 */}
          {dq.triage_summary?.manual_review && dq.triage_summary.manual_review.length > 0 && (
            <Card title="🔍 人工核审计清单 (Manual Audit Required)" className="mb-5">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[12px] border-collapse">
                  <thead>
                    <tr className="border-b border-cardline text-subink">
                      <th className="py-2 pr-4">故障分类</th>
                      <th className="py-2 pr-4">股票代码</th>
                      <th className="py-2 pr-4">问题详情</th>
                      <th className="py-2">审计与排查指南</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dq.triage_summary.manual_review.map((item: any, idx: number) => (
                      <tr key={idx} className="border-b border-cardline/60 text-ink">
                        <td className="py-2 text-danger font-semibold pr-4">{item.category}</td>
                        <td className="py-2 font-mono pr-4">{item.code || "全市场"}</td>
                        <td className="py-2 text-subink pr-4">{item.detail}</td>
                        <td className="py-2 text-subink font-medium">{item.instruction}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          )}

          {/* 数据流动血缘图 Card */}
          <Card
            title="🔗 数据流动血缘与消费机制图 (Data Lineage Flow)"
            right="点击节点展示防未来函数对齐契约与消费方式"
            className="mb-5"
          >
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 items-stretch relative">
              {/* Column 1: Sources */}
              <div className="space-y-3 flex flex-col justify-center">
                <div className="text-[11px] font-bold text-subink text-center mb-1">1. 原始数据源 (Sources)</div>
                {renderNodeButton("tushare_api", "📡 Tushare REST API")}
                {renderNodeButton("pdf_reports", "📄 卖方研报 PDF")}
              </div>

              {/* Column 2: Data Lake */}
              <div className="space-y-3 flex flex-col justify-center bg-bg/40 border border-cardline/30 p-3 rounded-[12px]">
                <div className="text-[11px] font-bold text-subink text-center mb-1">2. 存储湖层 (Data Lake)</div>
                {renderNodeButton("daily_all_parquet", "💾 行情 Parquet 湖")}
                {renderNodeButton("fundamental_batch", "💾 财务 Parquet 湖")}
                {renderNodeButton("industry_parquet", "💾 行业映射 (industry)")}
                {renderNodeButton("pdf_inbox", "💾 研报 Inbox 哈希库")}
              </div>

              {/* Column 3: Alignment */}
              <div className="space-y-3 flex flex-col justify-center">
                <div className="text-[11px] font-bold text-subink text-center mb-1">3. 消费对齐层 (Alignment)</div>
                {renderNodeButton("price_align", "⏳ 行情 T+1 对齐")}
                {renderNodeButton("fina_align", "🛡️ 财务防未来公告对齐")}
                {renderNodeButton("nlp_align", "🧠 NLP 因果聚合")}
              </div>

              {/* Column 4: Production */}
              <div className="space-y-3 flex flex-col justify-center bg-[#88ABDA]/5 border border-[#88ABDA]/15 p-3 rounded-[12px]">
                <div className="text-[11px] font-bold text-[#88ABDA] text-center mb-1">4. 应用与日更生产 (Production)</div>
                {renderNodeButton("alpha_dev", "⚙️ 因子研发 Alpha")}
                {renderNodeButton("causal_pred", "⚙️ 因果预测 (Predictor)")}
                {renderNodeButton("run_daily_prod", "🚀 每日生产信号 (run)")}
              </div>
            </div>

            {selectedNode && (
              <div className="mt-5 p-4 rounded-[8px] bg-bg border border-[#88ABDA]/30">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                    NODES_INFO[selectedNode].type === "Source" ? "bg-amber-500/10 text-amber-600"
                    : NODES_INFO[selectedNode].type === "Lake" ? "bg-emerald-500/10 text-emerald-600"
                    : NODES_INFO[selectedNode].type === "Alignment" ? "bg-indigo-500/10 text-indigo-600"
                    : "bg-[#88ABDA]/15 text-[#88ABDA]"
                  }`}>
                    {NODES_INFO[selectedNode].type.toUpperCase()}
                  </span>
                  <h4 className="text-[13px] font-bold text-ink">{NODES_INFO[selectedNode].title}</h4>
                </div>
                <p className="text-[12px] leading-relaxed text-subink">{NODES_INFO[selectedNode].desc}</p>
              </div>
            )}
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card title="故障分布及跳变统计 (issue_breakdown)">
              <table className="w-full text-[13px]">
                <tbody>
                  {Object.entries(dq.issue_breakdown).sort((a, b) => b[1] - a[1]).map(([k, v]) => {
                    const severe = k.includes("负价") || k.includes("OHLC");
                    return (
                      <tr key={k} className="border-b border-cardline/60">
                        <td className={`py-1.5 ${severe ? "text-danger" : "text-subink"}`}>{k}{severe ? " · 阻断真问题" : ""}</td>
                        <td className="py-1.5 text-right text-ink font-quant">{v}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Card>

            <Card title="DuckDB 即席复核 (Ad-hoc Verification)">
              {dq.duckdb?.available ? (
                <div className="text-[13px] space-y-1.5">
                  <div className="flex justify-between"><span className="text-subink">总行数</span><span className="text-ink font-quant">{dq.duckdb.rows?.toLocaleString()}</span></div>
                  <div className="flex justify-between"><span className="text-subink">标的数</span><span className="text-ink font-quant">{dq.duckdb.codes}</span></div>
                  <div className="flex justify-between"><span className="text-subink">日期范围</span><span className="text-ink font-quant">{dq.duckdb.date_range?.slice(0, 10)} ~ {dq.duckdb.date_range?.slice(-19, -9)}</span></div>
                  <div className="flex justify-between"><span className="text-subink">收盘价 ≤ 0 行数</span><span className={dq.duckdb.nonpositive_close ? "text-danger" : "text-ok"}>{dq.duckdb.nonpositive_close}</span></div>
                  <div className="flex justify-between"><span className="text-subink">已隔离区间(quarantine)</span><span className="text-ink font-quant">{dq.duckdb.quarantined_ranges ?? 0}</span></div>
                  <div className="text-[11px] text-subink pt-1">扫描已排除 quarantine 区间;负价行 = 服务视图中残留的真问题(应为 0)。</div>
                </div>
              ) : (
                <div className="text-[13px] text-subink">{dq.duckdb?.note ?? "未接入"}</div>
              )}
            </Card>
          </div>

          {dq.flagged_sample.length > 0 && (
            <Card title={`被标记标的(样例 ${dq.flagged_sample.length} / 共 ${dq.n_flagged})`} className="mt-4">
              <div className="flex flex-wrap gap-2">
                {dq.flagged_sample.map((f) => (
                  <span key={f.code} className="text-[12px] px-2 py-0.5 rounded bg-bg border border-cardline text-subink" title={f.issues.join(", ")}>
                    {f.code}
                  </span>
                ))}
              </div>
            </Card>
          )}

          {/* 数据维度目录 */}
          <Card
            title="数据湖已入库维度目录 (Data Lake Ingested Dimensions)"
            right={`统一真相源 · 基准更新时间: ${latestDataDate}`}
            className="mt-6"
          >
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              {/* Category tabs */}
              <div className="space-y-1.5 md:col-span-1">
                {DIMENSIONS_CATALOG.map((cat, idx) => (
                  <button
                    key={idx}
                    onClick={() => setSelectedCat(idx)}
                    className={`w-full text-left px-3 py-2.5 rounded-[8px] text-[13px] font-medium transition-all duration-200 flex items-center gap-2 border ${
                      selectedCat === idx
                        ? "bg-[#88ABDA]/15 text-[#88ABDA] border-[#88ABDA]/30 shadow-[0_0_12px_rgba(136,171,218,0.1)]"
                        : "bg-transparent text-subink border-transparent hover:bg-cardline/20 hover:text-ink"
                    }`}
                  >
                    <span className="text-base">{cat.icon}</span>
                    <span>{cat.category}</span>
                  </button>
                ))}
              </div>

              {/* Items Table */}
              <div className="md:col-span-3 overflow-x-auto">
                <DataTable<DimensionItem>
                  rows={DIMENSIONS_CATALOG[selectedCat].items}
                  getRowKey={(item, idx) => `${item.file}-${idx}`}
                  columns={[
                    { key: "name", header: "维度名称", className: "font-medium text-ink", render: (item) => item.name },
                    { key: "file", header: "Parquet 物理路径", className: "font-mono text-[11px] text-subink select-all", render: (item) => item.file },
                    {
                      key: "rows", header: "估算行数 / 范围", align: "right", className: "text-ink font-quant",
                      render: (item) => (<>{item.rows}<div className="text-[10px] text-subink font-sans mt-0.5">{item.coverage} · {item.span}</div></>),
                    },
                    { key: "update", header: "更新机制", align: "right", className: "text-subink", render: (item) => item.update },
                    {
                      key: "status", header: "状态", align: "right",
                      render: (item) => (
                        <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          item.status === "active" ? "bg-[#88ABDA]/10 text-[#88ABDA]"
                            : item.status === "warning" ? "bg-warn/10 text-warn"
                            : item.status === "error" ? "bg-danger/10 text-danger"
                            : "bg-cardline text-subink"
                        }`}>
                          {item.status === "active" ? "ACTIVE" : item.status === "warning" ? "WARNING" : item.status === "error" ? "DEPRECATED" : "SYSTEM"}
                        </span>
                      ),
                    },
                  ]}
                />
              </div>
            </div>

            {/* Planned Dimensions */}
            <div className="mt-6 pt-4 border-t border-cardline/60">
              <div className="text-[11px] font-medium text-subink mb-2">📋 因子研发流水线计划接入维度 (Roadmap & Planned Access)</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="p-2.5 rounded-[8px] bg-bg/50 border border-cardline/30 text-[11px]">
                  <div className="font-semibold text-ink mb-1 flex items-center gap-1">🚀 机构与异动 (第一优先级)</div>
                  <div className="text-subink">大宗交易 (block_trade) · 龙虎榜明细 (top_list) · 回购记录 (repurchase) · 股权质押率</div>
                </div>
                <div className="p-2.5 rounded-[8px] bg-bg/50 border border-cardline/30 text-[11px]">
                  <div className="font-semibold text-ink mb-1 flex items-center gap-1">🛡️ 风控与基本面 (第二优先级)</div>
                  <div className="text-subink">审计意见 (fina_audit) · 主营业务构成 (fina_mainbz) · 宏观景气度 (GDP/PMI/LPR)</div>
                </div>
                <div className="p-2.5 rounded-[8px] bg-bg/50 border border-cardline/30 text-[11px]">
                  <div className="font-semibold text-ink mb-1 flex items-center gap-1">💎 增值筹码 (第三优先级/需积分)</div>
                  <div className="text-subink">筹码胜率/获利盘 (cyq_perf) · 分析师盈利预测修正 (report_rc) · 连板追踪</div>
                </div>
              </div>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}

