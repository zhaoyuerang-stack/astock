"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

export default function TopBar() {
  const [updateDate, setUpdateDate] = useState("加载中…");

  const load = useCallback(() => {
    api.marketState()
      .then((m) => {
        if (m.last_signal_date) {
          setUpdateDate(m.last_signal_date);
        } else {
          setUpdateDate("—");
        }
      })
      .catch(() => {
        setUpdateDate("离线");
      });
  }, []);
  useAutoRefresh(load);

  return (
    <header className="h-14 shrink-0 bg-bg border-b border-line/30 flex items-center justify-between px-6">
      <input
        placeholder="搜索因子 / 策略 / 数据集 / 实验…"
        className="w-80 max-w-[40vw] text-sm bg-white border border-line/50 rounded-lg px-3 py-1.5 outline-none focus:border-brand text-ink placeholder-subink/45"
      />
      <div className="flex items-center gap-4 text-sm text-subink">
        <span className="text-xs font-mono">数据更新: {updateDate}</span>
        <span className="w-7 h-7 rounded-full bg-brand text-white font-semibold grid place-items-center text-xs shadow-sm">
          K
        </span>
      </div>
    </header>
  );
}
