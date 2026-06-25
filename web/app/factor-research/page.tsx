"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import Card from "@/components/ui/Card";
import DataTable from "@/components/ui/DataTable";
import { api, num } from "@/lib/api";
import type { FactorView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

type FactorDetail = {
  id: string;
  name: string;
  category: string;
  ic: number;
  icir: number;
  neutralizedIcir: number;
  coverage: number;
  author: string;
  createdAt: string;
  dataStart: string;
  universe: string;
};

type ExperimentRow = {
  priority: string;
  hypothesis: string;
  desc: string;
  universe: string;
  stage: string;
  status: string;
  creator: string;
  date: string;
  reason?: string;
};

export default function FactorResearchPage() {
  const setContext = useAgent((s) => s.setContext);

  const [factors, setFactors] = useState<FactorView[]>([]);
  const [selectedId, setSelectedId] = useState<string>("illiquidity_premium");
  const [err, setErr] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeTab, setActiveTab] = useState<"performance" | "group" | "turnover" | "style" | "queue">("performance");

  const load = useCallback(() => {
    setErr(null);
    api.factors()
      .then((data) => {
        setFactors(data);
        
        // Highlight active factor to AI Assistant
        setContext({
          page: "factor-research",
          title: "因子研究實驗室",
          summary: "當前審核因子：illiquidity_premium (非流動性溢價)。中性化 ICIR: 2.42。數據覆蓋率: 99.8%。",
          evidence: [
            "因子名稱: illiquidity_premium (流動性溢價家族)",
            "中性化後 ICIR: 2.42 (顯著大於 2.0)",
            "分組收益單調性: 良好，多空月均超額 1.25%",
            "高相關風格暴露: 市值 (Size) 相關性 0.72",
          ],
          risk: ["該因子與市值（Size）風格高度相關，可能存在風格偽裝風險，需進行強制市值中性化"],
          recommendation: [
            "對因子值進行正交化去噪",
            "在 BacktestLab 中加入中性化開關進行 OOS 檢驗",
          ],
          nextActions: [
            "運行市值與行業雙重中性化因子回測",
            "檢查 L3 階段的實驗隊列排隊狀態",
          ],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext]);

  useAutoRefresh(load);

  // Mock details of selected factor
  const factorDetails: Record<string, FactorDetail> = {
    illiquidity_premium: {
      id: "illiquidity_premium",
      name: "非流动性溢价因子 (Illiquidity Premium)",
      category: "流動性",
      ic: 0.052,
      icir: 2.15,
      neutralizedIcir: 2.42,
      coverage: 0.998,
      author: "researcher",
      createdAt: "2026-06-15",
      dataStart: "2018-01-01",
      universe: "A股全市場 (剔除ST)",
    },
    momentum_reversal: {
      id: "momentum_reversal",
      name: "动量反转因子 (Momentum Reversal)",
      category: "動量",
      ic: 0.041,
      icir: 1.85,
      neutralizedIcir: 1.92,
      coverage: 0.995,
      author: "researcher",
      createdAt: "2026-06-18",
      dataStart: "2018-01-01",
      universe: "A股全市場",
    },
    value_factor: {
      id: "value_factor",
      name: "价值因子 (Value Factor)",
      category: "價值",
      ic: 0.035,
      icir: 1.62,
      neutralizedIcir: 1.75,
      coverage: 0.999,
      author: "admin",
      createdAt: "2026-06-10",
      dataStart: "2018-01-01",
      universe: "中證800",
    },
  };

  const selectedFactor = factorDetails[selectedId] || factorDetails.illiquidity_premium;

  const filteredFactors = factors.filter((f) => {
    const q = searchQuery.toLowerCase();
    return (
      f.name.toLowerCase().includes(q) ||
      (f.display_name && f.display_name.toLowerCase().includes(q)) ||
      f.regime.toLowerCase().includes(q)
    );
  });

  // Mock style correlation data
  const styleCorrelation = [
    { style: "市值 (Size)", corr: 0.72 },
    { style: "波動率 (Volatility)", corr: 0.45 },
    { style: "動量 (Momentum)", corr: 0.12 },
    { style: "盈利 (Earnings)", corr: 0.08 },
    { style: "價值 (Value)", corr: -0.15 },
    { style: "槓桿率 (Leverage)", corr: -0.05 },
    { style: "流動性 (Liquidity)", corr: 0.85 },
  ];

  // Mock experiments queue
  const experimentQueue: ExperimentRow[] = [
    { priority: "P0", hypothesis: "size_earnings_v2.0", desc: "融合小盤特徵與扣非利潤增速的二階因子", universe: "A股全市場", stage: "L3", status: "運行中", creator: "researcher", date: "2026-06-24" },
    { priority: "P1", hypothesis: "amount_timing_opt", desc: "量價交易額择时均線參數自適應優化", universe: "全市場", stage: "L2", status: "隊列中", creator: "researcher", date: "2026-06-23" },
    { priority: "P2", hypothesis: "turnover_decay_test", desc: "換手率半衰期衰減測試", universe: "創業板", stage: "L1", status: "已通過", creator: "system", date: "2026-06-22" },
    { priority: "P0", hypothesis: "overfitting_test_fail", desc: "多因子融合過度擬合嫌疑審計", universe: "全市場", stage: "L0", status: "已拒絕", creator: "system", date: "2026-06-21", reason: "置換檢驗 DSR p-value = 0.42 未達顯著性門檻" },
  ];

  // SVG Chart sizing
  const cw = 600;
  const ch = 180;

  return (
    <div className="space-y-6">
      <PageHeader
        title="因子研究"
        desc="底層量化因子庫管理、IC / ICIR 歸因分析與因子風格相關性熱力圖 (Factor Research Lab)"
      />

      {err && (
        <div className="p-4 bg-[#FF5C5C]/10 border border-[#FF5C5C]/20 rounded-lg text-sm text-[#FF5C5C]">
          ⚠️ API 載入出錯: {err}
        </div>
      )}

      {/* 1. 因子總覽指標 */}
      <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
        <div className="p-4 bg-[#0E2238] border border-[#1F3550] rounded-lg">
          <div className="text-[12px] text-[#8FA3BF]">因子總數</div>
          <div className="text-2xl font-bold font-mono text-[#E6EDF7] mt-1.5">{factors.length || 12} 個</div>
          <div className="text-[10px] text-[#5F728A] mt-2">已註冊獨立 alpha 家族</div>
        </div>
        <div className="p-4 bg-[#0E2238] border border-[#1F3550] rounded-lg">
          <div className="text-[12px] text-[#8FA3BF]">今日實驗數</div>
          <div className="text-2xl font-bold font-mono text-[#3D7BFF] mt-1.5">6 個</div>
          <div className="text-[10px] text-[#5F728A] mt-2">運行中與待處理實驗</div>
        </div>
        <div className="p-4 bg-[#0E2238] border border-[#1F3550] rounded-lg">
          <div className="text-[12px] text-[#8FA3BF]">平均 IC</div>
          <div className="text-2xl font-bold font-mono text-[#35D06E] mt-1.5">0.052</div>
          <div className="text-[10px] text-[#5F728A] mt-2">市值與行業雙重中性化後</div>
        </div>
        <div className="p-4 bg-[#0E2238] border border-[#1F3550] rounded-lg">
          <div className="text-[12px] text-[#8FA3BF]">中性化 ICIR</div>
          <div className="text-2xl font-bold font-mono text-[#35D06E] mt-1.5">2.42</div>
          <div className="text-[10px] text-[#5F728A] mt-2">Newey-West 延遲修正</div>
        </div>
        <div className="p-4 bg-[#0E2238] border border-[#1F3550] rounded-lg">
          <div className="text-[12px] text-[#8FA3BF]">數據覆蓋率</div>
          <div className="text-2xl font-bold font-mono text-[#35D06E] mt-1.5">99.8%</div>
          <div className="text-[10px] text-[#5F728A] mt-2">若低於 95% 將觸發報警</div>
        </div>
      </div>

      {/* 2. 雙欄布局:左因子庫,右詳情 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Left Col: Factor Library list */}
        <div className="space-y-4">
          <Card title="因子庫 (Factor Library)">
            <div className="mb-3">
              <input
                type="text"
                placeholder="🔍 搜尋因子 (中/英)..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full text-xs px-2.5 py-1.5 bg-[#081827] border border-[#1F3550] text-[#E6EDF7] rounded"
              />
            </div>

            <div className="space-y-1.5 max-h-[480px] overflow-y-auto pr-1">
              {filteredFactors.map((f) => {
                const isSelected = selectedId === f.name || (selectedId === "illiquidity_premium" && f.name === "illiquidity");
                return (
                  <div
                    key={f.name}
                    onClick={() => {
                      const targetId = factorDetails[f.name] ? f.name : "illiquidity_premium";
                      setSelectedId(targetId);
                    }}
                    className={`p-2.5 rounded border border-[#1F3550] cursor-pointer transition-colors ${
                      isSelected
                        ? "bg-[#3D7BFF]/10 border-[#3D7BFF] text-[#E6EDF7]"
                        : "bg-[#081827] hover:bg-[#1F3550]/40 text-[#8FA3BF] hover:text-[#E6EDF7]"
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <span className="font-mono font-semibold text-xs truncate max-w-[150px]">
                        {f.display_name || f.name}
                      </span>
                      <span className="text-[10px] px-1 bg-[#0E2238] rounded text-[#8FA3BF] scale-95">{f.regime}</span>
                    </div>
                    <div className="flex justify-between text-[10px] mt-2 font-mono text-[#5F728A]">
                      <span>IC: 0.052</span>
                      <span>ICIR: 2.42</span>
                    </div>
                  </div>
                );
              })}
              {filteredFactors.length === 0 && (
                <div className="text-center text-xs text-[#5F728A] py-6">找不到匹配的因子</div>
              )}
            </div>
          </Card>
        </div>

        {/* Right Col: Factor details & Tabs */}
        <div className="lg:col-span-2 space-y-6">
          {/* Factor Profile */}
          <Card title={`Dossier: ${selectedFactor.name}`}>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-xs font-mono text-[#8FA3BF] py-2">
              <div>
                <div><span className="text-[#5F728A]">因子代碼:</span> {selectedFactor.id}</div>
                <div><span className="text-[#5F728A]">因子作者:</span> {selectedFactor.author}</div>
              </div>
              <div>
                <div><span className="text-[#5F728A]">創建時間:</span> {selectedFactor.createdAt}</div>
                <div><span className="text-[#5F728A]">數據起點:</span> {selectedFactor.dataStart}</div>
              </div>
              <div>
                <div><span className="text-[#5F728A]">覆蓋範圍:</span> {selectedFactor.universe}</div>
                <div><span className="text-[#5F728A]">因子類型:</span> {selectedFactor.category}</div>
              </div>
              <div>
                <div><span className="text-[#5F728A]">覆蓋比率:</span> {(selectedFactor.coverage * 100).toFixed(1)}%</div>
                <div><span className="text-[#5F728A]">有效性判定:</span> <span className="text-[#35D06E] font-bold">PASS</span></div>
              </div>
            </div>
          </Card>

          {/* Details tab menu */}
          <div className="space-y-4">
            <div className="flex border-b border-[#1F3550] gap-2 select-none">
              <button
                onClick={() => setActiveTab("performance")}
                className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 ${
                  activeTab === "performance" ? "border-[#3D7BFF] text-[#E6EDF7]" : "border-transparent text-[#8FA3BF]"
                }`}
              >
                因子表現 (IC 時序)
              </button>
              <button
                onClick={() => setActiveTab("group")}
                className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 ${
                  activeTab === "group" ? "border-[#3D7BFF] text-[#E6EDF7]" : "border-transparent text-[#8FA3BF]"
                }`}
              >
                分組收益 (Monotonicity)
              </button>
              <button
                onClick={() => setActiveTab("turnover")}
                className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 ${
                  activeTab === "turnover" ? "border-[#3D7BFF] text-[#E6EDF7]" : "border-transparent text-[#8FA3BF]"
                }`}
              >
                換手與成本敏感性
              </button>
              <button
                onClick={() => setActiveTab("style")}
                className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 ${
                  activeTab === "style" ? "border-[#3D7BFF] text-[#E6EDF7]" : "border-transparent text-[#8FA3BF]"
                }`}
              >
                風格相關性
              </button>
              <button
                onClick={() => setActiveTab("queue")}
                className={`px-3 py-1.5 text-xs font-bold transition-all border-b-2 ${
                  activeTab === "queue" ? "border-[#3D7BFF] text-[#E6EDF7]" : "border-transparent text-[#8FA3BF]"
                }`}
              >
                實驗隊列 (Funnel)
              </button>
            </div>

            <div className="bg-[#0E2238] border border-[#1F3550] rounded-lg p-4 text-xs">
              {activeTab === "performance" && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center font-bold text-[#E6EDF7]">
                    <span>IC 歷史滾動時序 (IC Time Series Curve)</span>
                    <span className="text-[11px] text-[#35D06E] font-mono">Newey-West 校正已啟用</span>
                  </div>
                  
                  {/* Mock IC line SVG chart */}
                  <div className="p-2 border border-[#1F3550]/40 rounded bg-[#06111F]/30">
                    <svg viewBox={`0 0 ${cw} ${ch}`} className="w-full">
                      {/* Zero axis line */}
                      <line x1="20" y1={ch / 2} x2={cw - 20} y2={ch / 2} stroke="#1F3550" strokeWidth="1.5" />
                      {/* IC line */}
                      <polyline
                        points="20,110 50,80 80,95 110,60 140,75 170,40 200,85 230,55 260,70 290,45 320,50 350,90 380,105 410,75 440,65 470,45 500,50 530,30 560,40 580,50"
                        fill="none"
                        stroke="#3D7BFF"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      {/* Annotations */}
                      <text x="20" y="20" fontSize="9" fill="#5F728A" fontFamily="monospace">IC +0.10</text>
                      <text x="20" y={ch / 2 + 4} fontSize="9" fill="#5F728A" fontFamily="monospace">IC  0.00</text>
                      <text x="20" y="165" fontSize="9" fill="#5F728A" fontFamily="monospace">IC -0.10</text>
                      <text x="20" y="176" fontSize="8" fill="#5F728A">2018</text>
                      <text x="300" y="176" fontSize="8" fill="#5F728A" textAnchor="middle">2022</text>
                      <text x="580" y="176" fontSize="8" fill="#5F728A" textAnchor="end">2026</text>
                    </svg>
                  </div>
                </div>
              )}

              {activeTab === "group" && (
                <div className="space-y-4">
                  <div className="font-bold text-[#E6EDF7]">等權分組累計超額收益 (Group Monotonicity)</div>
                  
                  {/* Mock bar chart SVG */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="p-2 border border-[#1F3550]/40 rounded bg-[#06111F]/30 flex justify-center">
                      <svg viewBox={`0 0 280 140`} className="w-full">
                        {/* Bars for Q1 - Q5 */}
                        {/* Q1: Top 10% */}
                        <rect x="20" y="20" width="30" height="90" fill="#35D06E" rx="3" />
                        <text x="35" y="125" textAnchor="middle" fontSize="9" fill="#8FA3BF">Top 10%</text>
                        <text x="35" y="15" textAnchor="middle" fontSize="9" fill="#35D06E" fontFamily="monospace">+22.4%</text>

                        {/* Q2: Top 30% */}
                        <rect x="70" y="45" width="30" height="65" fill="#35D06E" opacity="0.8" rx="3" />
                        <text x="85" y="125" textAnchor="middle" fontSize="9" fill="#8FA3BF">Top 30%</text>
                        <text x="85" y="40" textAnchor="middle" fontSize="9" fill="#35D06E" fontFamily="monospace">+14.2%</text>

                        {/* Q3: Neutral */}
                        <rect x="120" y="70" width="30" height="40" fill="#9AA8BD" rx="3" />
                        <text x="135" y="125" textAnchor="middle" fontSize="9" fill="#8FA3BF">Neutral</text>
                        <text x="135" y="65" textAnchor="middle" fontSize="9" fill="#9AA8BD" fontFamily="monospace">+5.1%</text>

                        {/* Q4: Bottom 30% */}
                        <rect x="170" y="90" width="30" height="20" fill="#FF5C5C" opacity="0.8" rx="3" />
                        <text x="185" y="125" textAnchor="middle" fontSize="9" fill="#8FA3BF">Bot 30%</text>
                        <text x="185" y="85" textAnchor="middle" fontSize="9" fill="#FF5C5C" fontFamily="monospace">-2.4%</text>

                        {/* Q5: Bottom 10% */}
                        <rect x="220" y="100" width="30" height="10" fill="#FF5C5C" rx="3" />
                        <text x="235" y="125" textAnchor="middle" fontSize="9" fill="#8FA3BF">Bot 10%</text>
                        <text x="235" y="95" textAnchor="middle" fontSize="9" fill="#FF5C5C" fontFamily="monospace">-8.6%</text>

                        {/* Base line */}
                        <line x1="10" y1="110" x2="270" y2="110" stroke="#1F3550" strokeWidth="1" />
                      </svg>
                    </div>

                    <div className="space-y-1">
                      <div className="text-[11px] font-bold text-[#E6EDF7] mb-1">分組年化指標</div>
                      <div className="border border-[#1F3550]/40 rounded overflow-hidden">
                        <table className="w-full text-left">
                          <thead>
                            <tr className="bg-[#10263D] border-b border-[#1F3550] text-[#8FA3BF]">
                              <th className="p-2 font-medium">組別</th>
                              <th className="p-2 font-medium text-right">年化收益</th>
                              <th className="p-2 font-medium text-right">勝率</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-[#1F3550]/30 font-mono text-[#E6EDF7]">
                            <tr>
                              <td className="p-2 text-[#35D06E]">Top 10% (首組)</td>
                              <td className="p-2 text-right">22.40%</td>
                              <td className="p-2 text-right">58.4%</td>
                            </tr>
                            <tr>
                              <td className="p-2 text-[#9AA8BD]">Neutral (中性)</td>
                              <td className="p-2 text-right">5.12%</td>
                              <td className="p-2 text-right">50.2%</td>
                            </tr>
                            <tr>
                              <td className="p-2 text-[#FF5C5C]">Bottom 10% (尾組)</td>
                              <td className="p-2 text-right">-8.65%</td>
                              <td className="p-2 text-right">42.1%</td>
                            </tr>
                          </tbody>
                        </table>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "turnover" && (
                <div className="space-y-4">
                  <div className="font-bold text-[#E6EDF7] mb-2">年化換手與扣除交易成本敏感性 (Cost Sensitivity Matrix)</div>
                  <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-2 font-mono text-center">
                    <div className="p-2 bg-[#081827] border border-[#1F3550] rounded">
                      <div className="text-[#8FA3BF] text-[10px]">年化換手率</div>
                      <div className="text-sm font-bold text-[#E6EDF7] mt-1">324.5%</div>
                    </div>
                    <div className="p-2 bg-[#081827] border border-[#1F3550] rounded">
                      <div className="text-[#8FA3BF] text-[10px]">持倉半衰期</div>
                      <div className="text-sm font-bold text-[#E6EDF7] mt-1">12.5 天</div>
                    </div>
                    <div className="p-2 bg-[#081827] border border-[#1F3550] rounded">
                      <div className="text-[#8FA3BF] text-[10px]">預計衝擊成本</div>
                      <div className="text-sm font-bold text-[#E6EDF7] mt-1">18.5 bps</div>
                    </div>
                    <div className="p-2 bg-[#081827] border border-[#1F3550] rounded">
                      <div className="text-[#8FA3BF] text-[10px]">成本前年化 IR</div>
                      <div className="text-sm font-bold text-[#35D06E] mt-1">2.42</div>
                    </div>
                  </div>

                  <div className="border border-[#1F3550]/40 rounded overflow-hidden">
                    <table className="w-full text-left font-mono">
                      <thead>
                        <tr className="bg-[#10263D] border-b border-[#1F3550] text-[#8FA3BF]">
                          <th className="p-2 font-medium">單邊交易成本 bps</th>
                          <th className="p-2 font-medium text-right">0 bps</th>
                          <th className="p-2 font-medium text-right">5 bps</th>
                          <th className="p-2 font-medium text-right">10 bps</th>
                          <th className="p-2 font-medium text-right">15 bps</th>
                          <th className="p-2 font-medium text-right">20 bps</th>
                          <th className="p-2 font-medium text-right">25 bps</th>
                          <th className="p-2 font-medium text-right">30 bps</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1F3550]/30 text-[#E6EDF7]">
                        <tr>
                          <td className="p-2 text-[#8FA3BF]">成本後年化 IR</td>
                          <td className="p-2 text-right text-[#35D06E]">2.42</td>
                          <td className="p-2 text-right text-[#35D06E]">2.31</td>
                          <td className="p-2 text-right text-[#35D06E]">2.14</td>
                          <td className="p-2 text-right text-[#35D06E]">1.98</td>
                          <td className="p-2 text-right text-[#F6B73C]">1.65</td>
                          <td className="p-2 text-right text-[#FF5C5C]">1.24</td>
                          <td className="p-2 text-right text-[#FF5C5C]">0.85</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                  <div className="text-[10px] text-[#FF5C5C] font-semibold">
                    ⚠️ 警示：單邊交易滑點成本超 20 bps 時，該因子成本後超額收益（IR）將衰減 30% 以上，高規模下有容量崩塌風險！
                  </div>
                </div>
              )}

              {activeTab === "style" && (
                <div className="space-y-4">
                  <div className="font-bold text-[#E6EDF7] mb-2">Barra 風格暴露相關性矩陣 (Style Beta Correlation Heatmap)</div>
                  <div className="border border-[#1F3550]/40 rounded overflow-hidden">
                    <table className="w-full text-left font-mono">
                      <thead>
                        <tr className="bg-[#10263D] border-b border-[#1F3550] text-[#8FA3BF]">
                          <th className="p-2 font-medium">風格特徵</th>
                          <th className="p-2 font-medium text-right">對應相關性</th>
                          <th className="p-2 font-medium">風險評級 / 中性化建議</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#1F3550]/30 text-[#E6EDF7]">
                        {styleCorrelation.map((item) => {
                          const isHigh = item.corr >= 0.7;
                          return (
                            <tr key={item.style}>
                              <td className="p-2">{item.style}</td>
                              <td className={`p-2 text-right font-bold ${isHigh ? "text-[#FF5C5C]" : "text-[#8FA3BF]"}`}>
                                {item.corr.toFixed(2)}
                              </td>
                              <td className="p-2">
                                {isHigh ? (
                                  <span className="text-[#FF5C5C] font-bold">⚠️ 風格污染 (相關 &gt; 0.70)，強制中性化</span>
                                ) : item.corr > 0.3 ? (
                                  <span className="text-[#F6B73C]">建议中性化</span>
                                ) : (
                                  <span className="text-[#5F728A]">暴露安全</span>
                                )}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {activeTab === "queue" && (
                <div className="space-y-4">
                  <div className="font-bold text-[#E6EDF7] mb-2">研發漏斗實驗隊列 (R&D Experiment Pipeline)</div>
                  <DataTable<ExperimentRow>
                    rows={experimentQueue}
                    getRowKey={(r) => r.hypothesis}
                    columns={[
                      { key: "priority", header: "級別", className: "font-mono font-bold text-[#FF5C5C] w-12", render: (r) => r.priority },
                      { key: "hypothesis", header: "實驗代碼", className: "font-mono text-[#3D7BFF] font-semibold", render: (r) => r.hypothesis },
                      { key: "desc", header: "假設描述", className: "text-[#8FA3BF] truncate max-w-[200px]", render: (r) => r.desc },
                      { key: "universe", header: "範圍", className: "text-[#8FA3BF]", render: (r) => r.universe },
                      {
                        key: "stage",
                        header: "階段",
                        className: "font-bold",
                        render: (r) => (
                          <span className={r.stage === "L3" ? "text-[#35D06E]" : "text-[#8FA3BF]"}>
                            {r.stage}
                          </span>
                        ),
                      },
                      {
                        key: "status",
                        header: "狀態",
                        render: (r) => (
                          <span className={r.status === "運行中" ? "text-[#3D7BFF] animate-pulse" : r.status === "已拒絕" ? "text-[#FF5C5C]" : "text-[#8FA3BF]"}>
                            {r.status}
                          </span>
                        ),
                      },
                      { key: "reason", header: "備註/拒絕原因", className: "text-[#FF5C5C] text-[11px] max-w-[200px] truncate", render: (r) => r.reason || "—" },
                      { key: "creator", header: "創建者", className: "text-[#5F728A] font-mono", render: (r) => r.creator },
                    ]}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
