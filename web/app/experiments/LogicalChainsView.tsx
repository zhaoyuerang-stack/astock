"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import KnowledgeGraphView from "./KnowledgeGraphView";

interface TransmissionNode {
  name: string;
  category: string;
  change: string;
  evidence: string;
  numeric_value?: number | null;
}

interface LogicalChain {
  industry: string;
  mechanism_summary: string;
  target_hypothesis_name: string;
  nodes: TransmissionNode[];
}

export default function LogicalChainsView() {
  const [chains, setChains] = useState<LogicalChain[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"graph" | "pipeline">("graph");

  useEffect(() => {
    api
      .logicalChains()
      .then((data) => {
        setChains(data);
        setLoading(false);
      })
      .catch((e) => {
        setErr(String(e));
        setLoading(false);
      });
  }, []);

  const categoryLabels: Record<string, string> = {
    supply: "供给端",
    demand: "需求端",
    cost: "成本端",
    price: "价格端",
    capacity: "产能/效率",
    margin: "利润空间",
    earnings: "业绩释放",
    valuation: "估值中枢",
  };

  const categoryTones: Record<string, string> = {
    supply: "bg-blue-50 text-blue-700 border-blue-200",
    demand: "bg-indigo-50 text-indigo-700 border-indigo-200",
    cost: "bg-amber-50 text-amber-700 border-amber-200",
    price: "bg-cyan-50 text-cyan-700 border-cyan-200",
    capacity: "bg-purple-50 text-purple-700 border-purple-200",
    margin: "bg-rose-50 text-rose-700 border-rose-200",
    earnings: "bg-emerald-50 text-emerald-700 border-emerald-200",
    valuation: "bg-teal-50 text-teal-700 border-teal-200",
  };

  return (
    <div className="space-y-4">
      {/* View Mode Switcher Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3 mb-1">
        <div className="text-[14px] font-bold text-ink">研报逻辑传导分析 (Causal Analysis)</div>
        <div className="flex bg-jilan/45 border border-line p-0.5 rounded-lg">
          <button
            onClick={() => setViewMode("graph")}
            className={`text-[12px] px-3.5 py-1 rounded-md transition-all duration-150 ${
              viewMode === "graph"
                ? "bg-brand text-white font-medium shadow-sm"
                : "text-subink hover:text-ink"
            }`}
          >
            产业因果图谱 (Network Graph)
          </button>
          <button
            onClick={() => setViewMode("pipeline")}
            className={`text-[12px] px-3.5 py-1 rounded-md transition-all duration-150 ${
              viewMode === "pipeline"
                ? "bg-brand text-white font-medium shadow-sm"
                : "text-subink hover:text-ink"
            }`}
          >
            线性传导链条 (Linear Chains)
          </button>
        </div>
      </div>

      {viewMode === "graph" ? (
        <KnowledgeGraphView />
      ) : (
        <>
          {loading && <div className="card text-center py-8 text-subink">正在加载研报逻辑传导链条...</div>}
          {err && <div className="card text-danger py-4">加载失败: {err}</div>}
          
          {!loading && !err && (
            <div className="space-y-6">
              {chains.map((chain, index) => (
                <div key={index} className="card border border-line bg-white p-5 rounded-xl shadow-sm">
                  {/* Header */}
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line/60 pb-3 mb-4">
                    <div>
                      <span className="text-[11px] font-bold uppercase tracking-wider bg-brand/10 text-brand px-2.5 py-1 rounded border border-brand/20">
                        {chain.industry}
                      </span>
                      <h3 className="text-[15px] font-semibold text-ink mt-2">
                        {chain.mechanism_summary}
                      </h3>
                    </div>
                    <div className="text-right">
                      <span className="text-[12px] text-subink">映射因子假设：</span>
                      <code className="text-[12px] font-mono bg-bg px-2 py-0.5 rounded text-brand border border-line/65">
                        {chain.target_hypothesis_name}
                      </code>
                    </div>
                  </div>

                  {/* Visual Causal Flow */}
                  <div className="mb-4">
                    <div className="text-[12px] font-semibold text-subink mb-3">逻辑传导链图 (Causal Chain)</div>
                    <div className="grid grid-cols-1 lg:grid-cols-5 gap-3 items-stretch">
                      {chain.nodes.map((node, idx) => (
                        <div key={idx} className="flex flex-col h-full">
                          <div className="flex-1 card border border-line bg-[#FAF8F5]/80 p-3 rounded-lg flex flex-col justify-between relative hover:border-brand/40 transition-all duration-200">
                            {/* Badge */}
                            <div className="flex items-center justify-between mb-2">
                              <span className={`text-[10px] px-2 py-0.5 rounded-full border ${categoryTones[node.category] || "bg-bg text-subink"}`}>
                                {categoryLabels[node.category] || node.category}
                              </span>
                              <span
                                className={`text-[12px] font-bold ${
                                  node.change === "up" ? "text-songshi" : node.change === "down" ? "text-yinzhu" : "text-subink"
                                }`}
                              >
                                {node.change === "up" ? "▲ 上行" : node.change === "down" ? "▼ 下行" : "● 持平"}
                              </span>
                            </div>

                            {/* Node Name */}
                            <div className="font-semibold text-[13px] text-ink mb-2">
                              {node.name}
                            </div>

                            {/* Numeric value with progress bar */}
                            {node.numeric_value !== null && node.numeric_value !== undefined && (
                              <div className="text-[11px] mb-2 bg-bg/60 p-2 rounded border border-line/45">
                                <div className="flex justify-between items-center text-[10px] text-subink mb-1">
                                  <span>指标参考值</span>
                                  <span className="font-mono font-bold text-brand">{node.numeric_value.toFixed(2)}</span>
                                </div>
                                <div className="w-full bg-jilan/30 h-1 rounded-full overflow-hidden">
                                  <div 
                                    className="bg-brand h-full rounded-full" 
                                    style={{ width: `${Math.min(100, Math.max(0, node.numeric_value * 100))}%` }} 
                                  />
                                </div>
                              </div>
                            )}

                            {/* Evidence Quote */}
                            <div className="text-[11px] text-subink italic bg-bg/65 p-2 rounded border border-line/40 line-clamp-3 hover:line-clamp-none transition-all duration-300" title={node.evidence}>
                              “ {node.evidence} ”
                            </div>
                          </div>

                          {/* Flow Arrow (Mobile & Desktop) */}
                          {idx < chain.nodes.length - 1 && (
                            <div className="flex lg:hidden items-center justify-center py-2">
                              <span className="text-subink">▼</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
