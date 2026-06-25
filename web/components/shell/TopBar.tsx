"use client";

import { useState } from "react";
import { useAppStore } from "@/lib/appStore";

export default function TopBar() {
  const {
    currentDate,
    latestDataDate,
    dataStatus,
    selectedStrategyId,
    selectedStrategyVersion,
    setSelectedStrategy,
    setDataStatus,
  } = useAppStore();

  const [stratOpen, setStratOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  // Strategies available for switching
  const strategyVersions = [
    { id: "illiquidity", version: "v3.1", name: "illiquidity v3.1" },
    { id: "illiquidity", version: "v3.0", name: "illiquidity v3.0" },
    { id: "size_earnings", version: "v1.0", name: "size_earnings v1.0" },
    { id: "roc_yc", version: "v1.0", name: "roc_yc v1.0" },
  ];

  const getStatusColor = () => {
    switch (dataStatus) {
      case "fresh":
        return "text-[#35D06E] bg-[#35D06E]/10 border-[#35D06E]/20";
      case "stale":
        return "text-[#F6B73C] bg-[#F6B73C]/10 border-[#F6B73C]/20";
      case "error":
        return "text-[#FF5C5C] bg-[#FF5C5C]/10 border-[#FF5C5C]/20";
      default:
        return "text-subink bg-bg border-line";
    }
  };

  const getStatusLabel = () => {
    switch (dataStatus) {
      case "fresh":
        return "已更新";
      case "stale":
        return "滯後";
      case "error":
        return "異常";
      default:
        return "未知";
    }
  };

  return (
    <header className="h-14 shrink-0 bg-[#161617] border-b border-line flex items-center justify-between px-6 select-none z-30 relative font-sans">
      {/* Left side: Date & Status Info */}
      <div className="flex items-center gap-6 text-[12px] text-subink">
        <div className="flex items-center gap-1.5">
          <span className="text-weak">今日：</span>
          <span className="font-bold text-ink font-mono">{currentDate}</span>
          <span className="text-[11px] text-weak">（星期三）</span>
        </div>

        <div className="h-3 w-[1px] bg-line" />

        <div className="flex items-center gap-1.5">
          <span className="text-weak">最新數據：</span>
          <span className="font-bold text-ink font-mono">{latestDataDate}</span>
          <span className={`px-2 py-0.5 rounded text-[10px] border font-bold ${getStatusColor()}`}>
            {getStatusLabel()}
          </span>
        </div>

        <div className="h-3 w-[1px] bg-line" />

        <div className="flex items-center gap-1.5">
          <span className="text-weak">下一次調倉：</span>
          <span className="font-bold text-brand font-mono">還有 12 個交易日</span>
        </div>
      </div>

      {/* Right side: Strategy Selector & More Actions */}
      <div className="flex items-center gap-3">
        {/* Strategy Selector Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setStratOpen(!stratOpen);
              setMoreOpen(false);
            }}
            className="flex items-center gap-2 px-3 py-1.5 text-[12px] bg-navy border border-line hover:border-brand text-ink rounded-md transition-all font-mono"
          >
            <span>🎯 策略: {selectedStrategyId} {selectedStrategyVersion}</span>
            <span className="text-[10px] text-weak">{stratOpen ? "▲" : "▼"}</span>
          </button>

          {stratOpen && (
            <div className="absolute right-0 mt-1.5 w-52 bg-navy border border-line rounded-md shadow-lg py-1 z-40">
              {strategyVersions.map((item) => (
                <button
                  key={item.name}
                  onClick={() => {
                    setSelectedStrategy(item.id, item.version);
                    setStratOpen(false);
                  }}
                  className={`w-full text-left px-4 py-2 text-[12px] font-mono hover:bg-line transition-colors ${
                    selectedStrategyId === item.id && selectedStrategyVersion === item.version
                      ? "text-brand font-bold"
                      : "text-ink"
                  }`}
                >
                  {item.name}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* More Actions Dropdown */}
        <div className="relative">
          <button
            onClick={() => {
              setMoreOpen(!moreOpen);
              setStratOpen(false);
            }}
            className="flex items-center justify-center p-1.5 bg-navy border border-line hover:border-brand text-subink hover:text-ink rounded-md transition-all"
            title="更多操作"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"
              />
            </svg>
          </button>

          {moreOpen && (
            <div className="absolute right-0 mt-1.5 w-44 bg-navy border border-line rounded-md shadow-lg py-1 z-40 text-[12px]">
              <button
                onClick={() => {
                  setDataStatus(dataStatus === "fresh" ? "stale" : "fresh");
                  setMoreOpen(false);
                }}
                className="w-full text-left px-4 py-2 text-ink hover:bg-line transition-colors"
              >
                🔄 模擬刷新數據狀態
              </button>
              <button
                onClick={() => {
                  window.location.reload();
                }}
                className="w-full text-left px-4 py-2 text-ink hover:bg-line transition-colors"
              >
                ⚡ 強制重新整理
              </button>
              <div className="border-t border-line my-1" />
              <div className="px-4 py-1 text-[10px] text-weak">部署ID: deploy_20260624_v1</div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
