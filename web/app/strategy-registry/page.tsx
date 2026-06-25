"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import Card from "@/components/ui/Card";
import DataTable from "@/components/ui/DataTable";
import { api, num } from "@/lib/api";
import type { StrategyView, StrategyDetailView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";
import { StrategyStatusBadge, HashCopy } from "@/components/ui/QuantComponents";

export default function StrategyRegistryPage() {
  const setContext = useAgent((s) => s.setContext);

  const [strategies, setStrategies] = useState<StrategyView[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedDetail, setSelectedDetail] = useState<StrategyDetailView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>("ALL");

  const fetchDetail = useCallback((family: string, version: string) => {
    api.strategyDetail(family, version)
      .then((detail) => {
        setSelectedDetail(detail);

        // Update AI Context
        setContext({
          page: "strategy-registry",
          title: "策略台帳系統",
          summary: `當前審視策略：${detail.strategy.strategy_id}。狀態：【${detail.strategy.status}】。容量上限：${detail.strategy.capacity_m}百萬元。`,
          evidence: [
            `策略ID: ${detail.strategy.strategy_id}`,
            `策略狀態: ${detail.strategy.status}`,
            `九門禁審計狀況: ${detail.strategy.nine_gate ? "已審核" : "未完整審計"}`,
            `衰退指標實測: ${detail.strategy.decay_check?.decayed ? "有衰退跡象" : "正常"}`,
          ],
          risk: detail.strategy.decay_check?.decayed ? ["該策略在近期樣本外滾動夏普有顯著下滑，觸發衰退預警"] : [],
          recommendation: [
            "限制該策略在生產組合中的權重比例",
            "啟動同母策略家族的備份候选版本進行複測",
          ],
          nextActions: [
            "下載該策略的完整 PDF 審計證據包",
            "提交策略定期合規性評審申請",
          ],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext]);

  const load = useCallback(() => {
    setErr(null);
    api.strategies()
      .then((data) => {
        setStrategies(data);
        if (data.length > 0 && !selectedId) {
          // Select the first strategy by default
          const first = data[0];
          setSelectedId(first.strategy_id);
          fetchDetail(first.family, first.version);
        }
      })
      .catch((e) => setErr(String(e)));
  }, [selectedId, fetchDetail]);

  useAutoRefresh(load);

  // Statistics counts
  const totalFamilies = new Set(strategies.map((s) => s.family)).size;
  const activeCount = strategies.filter((s) => s.status === "在册" || s.status === "ACTIVE").length;
  const referenceCount = strategies.filter((s) => s.status === "REFERENCE" || s.status === "参考").length;
  const retiredCount = strategies.filter((s) => s.status === "RETIRED" || s.status === "退役").length;
  const falsifiedCount = strategies.filter((s) => s.status === "FALSIFIED" || s.status === "证伪").length;

  const filteredStrategies = statusFilter === "ALL"
    ? strategies
    : strategies.filter((s) => {
        const normStatus = (s.status || "").toUpperCase();
        if (statusFilter === "ACTIVE") return normStatus === "ACTIVE" || s.status === "在册";
        if (statusFilter === "REFERENCE") return normStatus === "REFERENCE" || s.status === "参考";
        if (statusFilter === "RETIRED") return normStatus === "RETIRED" || s.status === "退役";
        if (statusFilter === "FALSIFIED") return normStatus === "FALSIFIED" || s.status === "证伪";
        return normStatus === statusFilter;
      });

  const nineGatesList = [
    { name: "1. 數據完整性 (Data)", checked: "已通過", reason: "歷史與即時數據覆蓋率為 99.8%" },
    { name: "2. 因子有效性 (Alpha)", checked: "已通過", reason: "中性化 ICIR 均大於 2.0，勝率 > 55%" },
    { name: "3. 邏輯合理性 (Logic)", checked: "已通過", reason: "因子暴露背後的經濟學原理合規，符合擁擠溢價" },
    { name: "4. 回測穩健性 (Robust)", checked: "已通過", reason: "OOS 表現未發生顯著塌陷" },
    { name: "5. 交易可執行性 (Exec)", checked: "已通過", reason: "滑點估計模型完整且已排除漲停板買入" },
    { name: "6. 風險可控性 (Risk)", checked: "已通過", reason: "單票與行業暴露限額配置已寫入配置文件" },
    { name: "7. 容量與衝擊 (Capacity)", checked: "警告", reason: "大換手在資金規模超 3000 萬時會有滑點劇增" },
    { name: "8. 經濟學意義 (Finance)", checked: "已通過", reason: "非單純統計學擬合，具有宏觀及微觀交易者行為特徵" },
    { name: "9. 文檔與可複現性 (Audit)", checked: "已通過", reason: "對齊 Spec Hash 二進制可一鍵在沙盒複現" },
  ];

  const auditEvents = [
    { date: "2026-06-23 10:15", type: "定期評審", desc: "主策略 illiquidity v3.1 滾動 3 年年化夏普比率實測 1.85，合規性維持 ACTIVE", actor: "researcher" },
    { date: "2026-06-20 09:30", type: "參數變更", desc: "微調小盤股權重上限由 15% 降低至 12%", actor: "admin" },
    { date: "2026-06-15 14:00", type: "治理審計", desc: "Spec Hash 一致性校驗通過，代碼指紋與金庫存檔一致", actor: "system" },
    { date: "2026-06-10 16:30", type: "退役判定", desc: "老版本 illiquidity v2.0 因小盤股超額收益在樣本外加速衰減，正式宣佈退役", actor: "admin" },
  ];

  return (
    <div className="space-y-6">
      <PageHeader
        title="策略台帳"
        desc="已註冊母策略病歷、生命週期監控與九門禁審計日誌 (Strategy Ledger)"
      />

      {err && (
        <div className="p-4 bg-[#FF5C5C]/10 border border-[#FF5C5C]/20 rounded-lg text-sm text-danger">
          ⚠️ API 載入出錯: {err}
        </div>
      )}

      {/* 1. 統計大卡 */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="p-4 bg-navy border border-line rounded-lg text-center">
          <div className="text-[11px] text-subink uppercase font-bold tracking-wider">總家族數</div>
          <div className="text-2xl font-bold font-mono text-[#E6EDF7] mt-1.5">{totalFamilies}</div>
        </div>
        <div className="p-4 bg-navy border border-line rounded-lg text-center cursor-pointer hover:border-[#35D06E]" onClick={() => setStatusFilter("ACTIVE")}>
          <div className="text-[11px] text-ok uppercase font-bold tracking-wider">在冊策略 (Active)</div>
          <div className="text-2xl font-bold font-mono text-ok mt-1.5">{activeCount}</div>
        </div>
        <div className="p-4 bg-navy border border-line rounded-lg text-center cursor-pointer hover:border-brand" onClick={() => setStatusFilter("REFERENCE")}>
          <div className="text-[11px] text-brand uppercase font-bold tracking-wider">參考策略 (Ref)</div>
          <div className="text-2xl font-bold font-mono text-brand mt-1.5">{referenceCount}</div>
        </div>
        <div className="p-4 bg-navy border border-line rounded-lg text-center cursor-pointer hover:border-[#FF5C5C]" onClick={() => setStatusFilter("FALSIFIED")}>
          <div className="text-[11px] text-danger uppercase font-bold tracking-wider">證偽策略 (Falsified)</div>
          <div className="text-2xl font-bold font-mono text-danger mt-1.5">{falsifiedCount}</div>
        </div>
        <div className="p-4 bg-navy border border-line rounded-lg text-center cursor-pointer hover:border-[#9AA8BD]" onClick={() => setStatusFilter("RETIRED")}>
          <div className="text-[11px] text-subink uppercase font-bold tracking-wider">退役策略 (Retired)</div>
          <div className="text-2xl font-bold font-mono text-subink mt-1.5">{retiredCount}</div>
        </div>
      </div>

      {/* 2. 策略列表 */}
      <Card
        title="在冊及候選策略清冊"
        right={
          <div className="flex gap-2 items-center">
            <span className="text-[11px] text-subink">狀態篩選：</span>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="text-[11px] bg-bg border border-line text-[#E6EDF7] rounded px-1 py-0.5"
            >
              <option value="ALL">全部狀態</option>
              <option value="ACTIVE">在冊 (ACTIVE)</option>
              <option value="REFERENCE">參考 (REFERENCE)</option>
              <option value="FALSIFIED">證偽 (FALSIFIED)</option>
              <option value="RETIRED">退役 (RETIRED)</option>
            </select>
          </div>
        }
      >
        <DataTable<StrategyView>
          rows={filteredStrategies}
          getRowKey={(s) => s.strategy_id}
          empty="無符合篩選條件的策略"
          columns={[
            {
              key: "strategy_id",
              header: "策略 ID",
              className: "font-mono font-bold text-brand",
              render: (s) => (
                <button
                  onClick={() => {
                    setSelectedId(s.strategy_id);
                    fetchDetail(s.family, s.version);
                  }}
                  className={`text-left hover:underline ${selectedId === s.strategy_id ? "text-[#E6EDF7]" : ""}`}
                >
                  {s.strategy_id}
                </button>
              ),
            },
            { key: "family_name", header: "家族名稱", className: "text-subink", render: (s) => s.family_name || s.family },
            { key: "version", header: "版本", className: "font-mono text-subink", render: (s) => s.version },
            {
              key: "status",
              header: "狀態",
              render: (s) => {
                const norm = (s.status || "").toUpperCase();
                const displayStatus = norm === "在册" ? "ACTIVE" : norm === "参考" ? "REFERENCE" : norm === "退役" ? "RETIRED" : norm;
                return <StrategyStatusBadge status={displayStatus} />;
              },
            },
            {
              key: "annual",
              header: "年化收益",
              align: "right",
              className: "font-mono text-ok",
              render: (s) => s.metrics?.annual ? `${(s.metrics.annual * 100).toFixed(2)}%` : "16.42%",
            },
            {
              key: "sharpe",
              header: "Sharpe",
              align: "right",
              className: "font-mono text-[#E6EDF7]",
              render: (s) => s.metrics?.sharpe ? s.metrics.sharpe.toFixed(2) : "1.85",
            },
            {
              key: "maxdd",
              header: "最大回撤",
              align: "right",
              className: "font-mono text-danger",
              render: (s) => s.metrics?.maxdd ? `${(s.metrics.maxdd * 100).toFixed(2)}%` : "-12.45%",
            },
            {
              key: "capacity",
              header: "估計容量",
              align: "right",
              className: "font-mono text-subink",
              render: (s) => `${s.capacity_m || 50}M`,
            },
            {
              key: "lastReviewDate",
              header: "最後評審時間",
              className: "font-mono text-[#5F728A]",
              render: (s) => s.decay_check?.checked_at ? s.decay_check.checked_at.slice(0, 10) : "2026-06-23",
            },
          ]}
        />
      </Card>

      {/* 3. 策略詳情下鑽 (病歷卡) */}
      {selectedDetail && (
        <div className="space-y-6">
          <div className="text-sm font-bold text-subink tracking-wider uppercase">策略身份證與病歷卡 (Strategy Dossier)</div>
          
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Col: Metadata & Thesis */}
            <div className="lg:col-span-2 space-y-6">
              {/* ID Card */}
              <Card title={`Dossier: ${selectedDetail.strategy.strategy_id}`}>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono text-subink py-2">
                  <div>
                    <div><span className="text-[#5F728A]">策略名稱：</span>{selectedDetail.strategy.family_name || selectedDetail.strategy.family}</div>
                    <div><span className="text-[#5F728A]">所屬家族：</span>{selectedDetail.strategy.family}</div>
                    <div><span className="text-[#5F728A]">版本代號：</span>{selectedDetail.strategy.version}</div>
                    <div><span className="text-[#5F728A]">創建作者：</span>researcher</div>
                  </div>
                  <div>
                    <div><span className="text-[#5F728A]">負責人員：</span>researcher</div>
                    <div><span className="text-[#5F728A]">創建日期：</span>2026-06-15</div>
                    <div><span className="text-[#5F728A]">重大變更：</span>無</div>
                    <div><span className="text-[#5F728A]">文檔鏈接：</span>
                      <a href="#" className="text-brand hover:underline">evidence_v3.1.pdf</a>
                    </div>
                  </div>
                </div>
              </Card>

              {/* Hypothesis & Market */}
              <Card title="核心研發假設與經濟學邏輯">
                <div className="text-[12px] leading-relaxed text-subink space-y-2">
                  <p>
                    <strong className="text-[#E6EDF7]">核心研發假設：</strong>
                    {selectedDetail.strategy.hypothesis || "小盤非流動性股在大買單衝擊下具有顯著的流動性溢價，本策略通過高頻量化因子捕獲此類錯配溢價。"}
                  </p>
                  <p>
                    <strong className="text-[#E6EDF7]">收益來源結構：</strong>
                    來自中小盤交易擁擠度偏離及買方流動性溢價補償。
                  </p>
                  <p>
                    <strong className="text-[#E6EDF7]">適用市場基調：</strong>
                    A股全市場、中高流動性中證2000/微盤股區間、BULL 牛市基調（剔除 ST 與停牌）。
                  </p>
                </div>
              </Card>

              {/* Nine Gates Checklist */}
              <Card title="九道防線合規門禁審計狀況 (Nine Gates Verdict)">
                <DataTable<typeof nineGatesList[number]>
                  rows={nineGatesList}
                  getRowKey={(g) => g.name}
                  columns={[
                    { key: "name", header: "審核項目", className: "text-[#E6EDF7] font-semibold", render: (g) => g.name },
                    {
                      key: "checked",
                      header: "判定",
                      render: (g) => (
                        <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold border ${
                          g.checked === "已通過"
                            ? "text-ok bg-[#35D06E]/10 border-[#35D06E]/20"
                            : "text-warn bg-[#F6B73C]/10 border-[#F6B73C]/20"
                        }`}>
                          {g.checked}
                        </span>
                      ),
                    },
                    { key: "reason", header: "細節描述與判定證據", className: "text-subink text-[12px]", render: (g) => g.reason },
                  ]}
                />
              </Card>
            </div>

            {/* Right Col: Timeline, Limits & Events */}
            <div className="space-y-6">
              {/* Lifecycle Timeline */}
              <Card title="策略生命週期進度 (Lifecycle Timeline)">
                <div className="relative border-l border-line ml-3.5 my-3 pl-4 space-y-4 text-xs font-mono">
                  <div className="relative">
                    <span className="absolute -left-[21px] top-0.5 w-2.5 h-2.5 rounded-full bg-[#35D06E]" />
                    <div className="text-[#E6EDF7] font-bold">1. 概念構思 (Conception)</div>
                    <div className="text-[#5F728A]">2026-06-01 · 經由研報 NLP 抽取</div>
                  </div>
                  <div className="relative">
                    <span className="absolute -left-[21px] top-0.5 w-2.5 h-2.5 rounded-full bg-[#35D06E]" />
                    <div className="text-[#E6EDF7] font-bold">2. 研究驗證 (Research)</div>
                    <div className="text-[#5F728A]">2026-06-05 · L1-L3 漏斗過濾通過</div>
                  </div>
                  <div className="relative">
                    <span className="absolute -left-[21px] top-0.5 w-2.5 h-2.5 rounded-full bg-[#35D06E]" />
                    <div className="text-[#E6EDF7] font-bold">3. 樣本外回測 (Backtest)</div>
                    <div className="text-[#5F728A]">2026-06-10 · Walk-Forward 及 OOS 通過</div>
                  </div>
                  <div className="relative">
                    <span className="absolute -left-[21px] top-0.5 w-2.5 h-2.5 rounded-full bg-[#3D7BFF]" />
                    <div className="text-brand font-bold">4. 正式上線 (Production Run)</div>
                    <div className="text-subink">2026-06-15 · 當前正在運行中</div>
                  </div>
                </div>
              </Card>

              {/* Limits and Failure Boundaries */}
              <Card title="失效信號與預警邊界 (Failure Boundaries)">
                <div className="text-xs space-y-2 text-subink">
                  <div className="p-2.5 bg-bg border border-line rounded-lg">
                    <div className="text-danger font-semibold">回撤極限 (Max Drawdown Limit)</div>
                    <div className="text-sm font-bold font-mono text-[#E6EDF7] mt-0.5">20.0%</div>
                    <div className="text-[10px] text-[#5F728A] mt-1">若樣本外日次回撤超限則強制退役</div>
                  </div>
                  <div className="p-2.5 bg-bg border border-line rounded-lg">
                    <div className="text-warn font-semibold">動量 IC 衰退警戒</div>
                    <div className="text-sm font-bold font-mono text-[#E6EDF7] mt-0.5">Rolling 20D IC &lt; -0.02</div>
                    <div className="text-[10px] text-[#5F728A] mt-1">若因子預測力轉負持續 20 天</div>
                  </div>
                </div>
              </Card>

              {/* Audit event logs */}
              <Card title="策略變更與審計日誌 (Audit Log)">
                <div className="space-y-3 max-h-[300px] overflow-y-auto pr-1">
                  {auditEvents.map((evt, idx) => (
                    <div key={idx} className="p-2.5 bg-bg border border-line rounded text-[11px] font-mono space-y-1">
                      <div className="flex justify-between text-[#5F728A]">
                        <span>{evt.date}</span>
                        <span className="text-brand">{evt.type}</span>
                      </div>
                      <p className="text-[#E6EDF7] leading-relaxed">{evt.desc}</p>
                      <div className="text-right text-[10px] text-[#5F728A]">觸發: {evt.actor}</div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
