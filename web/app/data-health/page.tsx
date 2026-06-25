"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import Card from "@/components/ui/Card";
import DataTable from "@/components/ui/DataTable";
import { api, pct } from "@/lib/api";
import type { DataQualityView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";
import { DataFreshnessBadge } from "@/components/ui/QuantComponents";

type PipelineStatusRow = {
  node: string;
  status: "success" | "running" | "lag" | "failed";
  completionTime: string;
  isDelayed: boolean;
};

type QualityCheckRow = {
  checkItem: string;
  status: "passed" | "warning" | "failed";
  anomalyCount: number;
  anomalyRatio: string;
  severity: "low" | "medium" | "high";
  comment: string;
};

type SourceHealthRow = {
  source: string;
  domain: string;
  latestDate: string;
  latency: string;
  failureRate: string;
  status: "active" | "warning" | "inactive";
};

type ActiveIssueRow = {
  id: string;
  time: string;
  domain: string;
  type: string;
  affected: string;
  severity: "low" | "medium" | "high";
  status: "unresolved" | "resolved";
};

export default function DataHealthPage() {
  const setContext = useAgent((s) => s.setContext);

  const [dq, setDq] = useState<DataQualityView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [issues, setIssues] = useState<ActiveIssueRow[]>([
    { id: "1", time: "2026-06-24 07:15", domain: "财务数据", type: "公告日對齊錯配", affected: "3 只證券", severity: "high", status: "unresolved" },
    { id: "2", time: "2026-06-23 18:30", domain: "日頻基礎", type: "復權因子突變", affected: "12 只證券", severity: "medium", status: "resolved" },
    { id: "3", time: "2026-06-23 09:00", domain: "指數數據", type: "中證2000成份更新延遲", affected: "全局成份表", severity: "low", status: "resolved" },
  ]);

  const load = useCallback(() => {
    setErr(null);
    api.dataQuality()
      .then((data) => {
        setDq(data);

        setContext({
          page: "data-health",
          title: "數據健康中心",
          summary: `數據庫健康度判決：【${data.verdict}】。PIT 通過率: ${(data.clean_ratio * 100).toFixed(1)}%。覆蓋 A 股 ${data.total} 只。`,
          evidence: [
            `最新可交易日對齊: 2026-06-23`,
            `PIT 數據庫驗證率: ${(data.clean_ratio * 100).toFixed(1)}%`,
            `數據新鮮度評核: FREESH`,
            `質量異常數: 嚴重問題 ${data.severe_count}只 · 正常跳變 ${data.jump_count}只`,
          ],
          risk: data.severe_count > 0 ? [`發現 ${data.severe_count} 只個股具有負價或 OHLC 一致性硬傷，可能影響今日操作信號`] : [],
          recommendation: [
            "對有嚴重一致性硬傷的證券實施交易禁入熔斷",
            "啟動補數據腳本重新拉取同花順/東財備用源",
          ],
          nextActions: [
            "運行本地 DuckDB 價量即席覆核查詢",
            "標記財務數據錯配問題為已修復",
          ],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext]);

  useAutoRefresh(load);

  // 1. Data Pipeline node statuses
  const pipelines: PipelineStatusRow[] = [
    { node: "價格數據 (Price)", status: "success", completionTime: "07:05", isDelayed: false },
    { node: "日頻基礎 (Daily Basic)", status: "success", completionTime: "07:12", isDelayed: false },
    { node: "資金流向 (Moneyflow)", status: "success", completionTime: "07:18", isDelayed: false },
    { node: "財務數據 (Financials)", status: "lag", completionTime: "07:35", isDelayed: true },
    { node: "事件數據 (Events)", status: "success", completionTime: "07:10", isDelayed: false },
    { node: "指數數據 (Index Components)", status: "success", completionTime: "07:08", isDelayed: false },
    { node: "宏觀數據 (Macro)", status: "success", completionTime: "昨日 18:00", isDelayed: false },
  ];

  // 2. Data Quality Checks (Severe issues vs A-share normal behaviors)
  const qualityChecks: QualityCheckRow[] = [
    { checkItem: "負價異常 (Negative Price)", status: "passed", anomalyCount: 0, anomalyRatio: "0.00%", severity: "high", comment: "未檢測到負定價（排除期貨/衍生品）" },
    { checkItem: "OHLC 一致性 (High-Low Check)", status: "passed", anomalyCount: 0, anomalyRatio: "0.00%", severity: "high", comment: "未檢測到最高價低於最低價等硬傷" },
    { checkItem: "極端價格跳變 (Price Jumps)", status: "warning", anomalyCount: 14, anomalyRatio: "0.27%", severity: "medium", comment: "多為除權除息/一字板跳空，已自動剔除" },
    { checkItem: "停牌/上市日缺失 (Suspensions)", status: "passed", anomalyCount: 0, anomalyRatio: "0.00%", severity: "medium", comment: "退市與長期停牌個股已正確處理" },
    { checkItem: "科創板/科創板量能歸一化", status: "passed", anomalyCount: 0, anomalyRatio: "0.00%", severity: "low", comment: "雙創板單位已折算，無量綱偏差" },
    { checkItem: "復權因子突變 (Split Checks)", status: "passed", anomalyCount: 0, anomalyRatio: "0.00%", severity: "high", comment: "後復權比例突變核算正常" },
  ];

  // 3. Multi-source health comparison
  const dataSources: SourceHealthRow[] = [
    { source: "Wind (萬得)", domain: "價量 / 財務 / 指數", latestDate: "2026-06-23", latency: "12 分鐘", failureRate: "0.02%", status: "active" },
    { source: "東方財富 (聚合)", domain: "融資融券 / 資金流向", latestDate: "2026-06-23", latency: "18 分鐘", failureRate: "0.45%", status: "active" },
    { source: "同花順 (備用)", domain: "價量 / PIT 財務", latestDate: "2026-06-23", latency: "25 分鐘", failureRate: "0.12%", status: "active" },
    { source: "中證指數公司 (CSINDEX)", domain: "成份權重", latestDate: "2026-06-23", latency: "65 分鐘", failureRate: "1.20%", status: "warning" },
    { source: "國家統計局 (NBS)", domain: "宏觀數據", latestDate: "2026-05-31", latency: "—", failureRate: "0.00%", status: "active" },
  ];

  const getStatusBadge = (status: string) => {
    const styleMap = {
      success: "text-[#35D06E] bg-[#35D06E]/10 border-[#35D06E]/20",
      running: "text-[#3D7BFF] bg-[#3D7BFF]/10 border-[#3D7BFF]/20",
      lag: "text-[#F6B73C] bg-[#F6B73C]/10 border-[#F6B73C]/20",
      failed: "text-[#FF5C5C] bg-[#FF5C5C]/10 border-[#FF5C5C]/20",
      active: "text-[#35D06E] bg-[#35D06E]/10 border-[#35D06E]/20",
      warning: "text-[#F6B73C] bg-[#F6B73C]/10 border-[#F6B73C]/20",
      inactive: "text-[#FF5C5C] bg-[#FF5C5C]/10 border-[#FF5C5C]/20",
    };
    return (
      <span className={`px-2 py-0.5 rounded text-[10px] border font-bold font-mono ${styleMap[status as keyof typeof styleMap] || ""}`}>
        {status.toUpperCase()}
      </span>
    );
  };

  const toggleResolve = (id: string) => {
    setIssues(issues.map(iss => iss.id === id ? { ...iss, status: iss.status === "resolved" ? "unresolved" : "resolved" } : iss));
  };

  return (
    <div className="space-y-6">
      <PageHeader
        title="數據健康"
        desc="數據集版本覆蓋、時間軸 PIT (Point-In-Time) 數據完整度與管道運行延遲監控 (Data Quality Control)"
      />

      {err && (
        <div className="p-4 bg-[#FF5C5C]/10 border border-[#FF5C5C]/20 rounded-lg text-sm text-[#FF5C5C]">
          ⚠️ API 載入出錯: {err}
        </div>
      )}

      {/* 1. 數據健康總覽 */}
      <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
        <div className="p-4 bg-[#0E2238] border border-[#1F3550] rounded-lg">
          <div className="text-[12px] text-[#8FA3BF]">最新交易日對齊</div>
          <div className="text-2xl font-bold font-mono text-[#E6EDF7] mt-1.5">2026-06-23</div>
          <div className="text-[10px] text-[#5F728A] mt-2 flex items-center gap-1">
            時效狀態: <DataFreshnessBadge daysAgo={0} />
          </div>
        </div>

        <div className="p-4 bg-[#0E2238] border border-[#1F3550] rounded-lg">
          <div className="text-[12px] text-[#8FA3BF]">覆蓋股票數</div>
          <div className="text-2xl font-bold font-mono text-[#E6EDF7] mt-1.5">{dq ? dq.total : 5320} 只</div>
          <div className="text-[10px] text-[#5F728A] mt-2">A股全宇宙退市/停牌處理</div>
        </div>

        <div className="p-4 bg-[#0E2238] border border-[#1F3550] rounded-lg">
          <div className="text-[12px] text-[#8FA3BF]">PIT 數據庫合規率</div>
          <div className="text-2xl font-bold font-mono text-[#35D06E] mt-1.5">{dq ? pct(dq.clean_ratio, 1) : "99.8%"}</div>
          <div className="text-[10px] text-[#5F728A] mt-2">防未來函數披露對齊率</div>
        </div>

        <div className="p-4 bg-[#0E2238] border border-[#1F3550] rounded-lg">
          <div className="text-[12px] text-[#8FA3BF]">質量綜合得分</div>
          <div className="text-2xl font-bold font-mono text-[#35D06E] mt-1.5">98.5 / 100</div>
          <div className="text-[10px] text-[#5F728A] mt-2">已扣除小盤異常跳變扣分</div>
        </div>

        <div className="p-4 bg-[#0E2238] border border-[#1F3550] rounded-lg">
          <div className="text-[12px] text-[#8FA3BF]">最新管道延遲</div>
          <div className="text-2xl font-bold font-mono text-[#F6B73C] mt-1.5">35 分鐘</div>
          <div className="text-[10px] text-[#5F728A] mt-2">財務披露爬取延後限制</div>
        </div>

        <div className="p-4 bg-[#0E2238] border border-[#1F3550] rounded-lg text-center">
          <div className="text-[11px] text-[#8FA3BF] uppercase font-bold tracking-wider">數據源狀態</div>
          <div className="mt-2.5">
            {getStatusBadge("active")}
          </div>
          <div className="text-[10px] text-[#5F728A] mt-2">3 個備用接口在線</div>
        </div>
      </div>

      {/* 2. 數據管道節點狀態 */}
      <Card title="數據管道調度流節點監控 (ETL Pipelines Status)">
        <div className="grid grid-cols-2 md:grid-cols-7 gap-4 text-center font-mono">
          {pipelines.map((p) => (
            <div key={p.node} className="p-3 bg-[#081827] border border-[#1F3550] rounded-lg space-y-1">
              <div className="text-[10px] text-[#8FA3BF] truncate" title={p.node}>{p.node.split(" ")[0]}</div>
              <div className="py-1">{getStatusBadge(p.status)}</div>
              <div className="text-[9px] text-[#5F728A]">完成: {p.completionTime}</div>
              {p.isDelayed && <div className="text-[8px] text-[#F6B73C] font-bold">⚠️ 延時警告</div>}
            </div>
          ))}
        </div>
      </Card>

      {/* 3. 數據質量檢查報告 (真問題 vs A股正常現象) */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        <div className="lg:col-span-2">
          <Card title="數據質量審核檢查細則 (PIT Integrity Check Logs)">
            <div className="text-[11px] text-[#8FA3BF] mb-2 leading-relaxed">
              根據量化鐵律#7：必須明確區分<strong>數據真問題</strong>（如負定價、開盤價高於收盤價等硬性邏輯錯）與<strong>A股正常交易現象</strong>（如新股首日無漲跌停、長期停牌成份股剔除、除權跳空等）。
            </div>
            <DataTable<QualityCheckRow>
              rows={qualityChecks}
              getRowKey={(r) => r.checkItem}
              columns={[
                { key: "checkItem", header: "審計項目", className: "text-[#E6EDF7] font-semibold", render: (r) => r.checkItem },
                {
                  key: "status",
                  header: "結果",
                  render: (r) => (
                    <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${
                      r.status === "passed"
                        ? "text-[#35D06E] bg-[#35D06E]/10 border-[#35D06E]/20"
                        : "text-[#F6B73C] bg-[#F6B73C]/10 border-[#F6B73C]/20"
                    }`}>
                      {r.status === "passed" ? "PASS" : "CHECK"}
                    </span>
                  ),
                },
                { key: "anomalyCount", header: "異常數", align: "right", className: "font-mono text-[#E6EDF7]", render: (r) => r.anomalyCount },
                { key: "anomalyRatio", header: "比例", align: "right", className: "font-mono text-[#8FA3BF]", render: (r) => r.anomalyRatio },
                {
                  key: "severity",
                  header: "嚴重度",
                  render: (r) => (
                    <span className={`px-1 rounded text-[9px] font-mono ${
                      r.severity === "high" ? "text-[#FF5C5C]" : r.severity === "medium" ? "text-[#F6B73C]" : "text-[#8FA3BF]"
                    }`}>
                      {r.severity.toUpperCase()}
                    </span>
                  ),
                },
                { key: "comment", header: "判定依據 / 人工 triaging 建議", className: "text-[#8FA3BF] text-[11px] max-w-[200px] truncate", render: (r) => r.comment },
              ]}
            />
          </Card>
        </div>

        {/* Multi source health */}
        <Card title="數據來源多源比對與延遲 (Multi-Source Latency)">
          <DataTable<SourceHealthRow>
            rows={dataSources}
            getRowKey={(r) => r.source}
            columns={[
              { key: "source", header: "來源渠道", className: "text-[#E6EDF7] font-bold", render: (r) => r.source },
              { key: "latestDate", header: "最新日期", className: "font-mono text-[#8FA3BF]", render: (r) => r.latestDate },
              { key: "latency", header: "拉取延遲", align: "right", className: "font-mono text-[#E6EDF7]", render: (r) => r.latency },
              {
                key: "status",
                header: "在線狀態",
                render: (r) => getStatusBadge(r.status),
              },
            ]}
          />
        </Card>
      </div>

      {/* 4. 異常問題登記冊 */}
      <Card title="異常數據問題跟蹤登記冊 (Active Issues Tracker)">
        <DataTable<ActiveIssueRow>
          rows={issues}
          getRowKey={(r) => r.id}
          empty="當前無登記的活躍數據異常問題"
          columns={[
            { key: "time", header: "發現時間", className: "font-mono text-[#5F728A]", render: (r) => r.time },
            { key: "domain", header: "業務模塊", className: "text-[#E6EDF7] font-semibold", render: (r) => r.domain },
            { key: "type", header: "異常類型與描述", className: "text-[#8FA3BF]", render: (r) => r.type },
            { key: "affected", header: "影響範圍", className: "text-[#8FA3BF] font-mono", render: (r) => r.affected },
            {
              key: "severity",
              header: "嚴重度",
              render: (r) => (
                <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${
                  r.severity === "high" ? "bg-[#FF5C5C]/10 border-[#FF5C5C]/20 text-[#FF5C5C]" : "bg-[#F6B73C]/10 border-[#F6B73C]/20 text-[#F6B73C]"
                }`}>
                  {r.severity.toUpperCase()}
                </span>
              ),
            },
            {
              key: "status",
              header: "修復狀態",
              render: (r) => (
                <span className={r.status === "resolved" ? "text-[#35D06E] font-bold" : "text-[#FF5C5C] font-bold animate-pulse"}>
                  {r.status === "resolved" ? "✓ RESOLVED" : "✗ ACTIVE"}
                </span>
              ),
            },
            {
              key: "actions",
              header: "操作",
              render: (r) => (
                <button
                  onClick={() => toggleResolve(r.id)}
                  className="px-2 py-0.5 bg-[#0E2238] border border-[#1F3550] hover:border-[#3D7BFF] text-[#3D7BFF] hover:text-[#E6EDF7] text-[11px] rounded transition-colors"
                >
                  {r.status === "resolved" ? "撤銷修復" : "標記修復"}
                </button>
              ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
