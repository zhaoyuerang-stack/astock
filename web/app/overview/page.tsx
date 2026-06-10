"use client";

import { useEffect, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import { api } from "@/lib/api";
import type { StrategyView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";

const FLOW = ["假设发现", "因子构建", "状态识别", "策略构建", "回测验证", "执行监控", "复盘迭代"];

export default function OverviewPage() {
  const [strategies, setStrategies] = useState<StrategyView[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const setContext = useAgent((s) => s.setContext);

  useEffect(() => {
    api
      .strategies()
      .then((s) => {
        setStrategies(s);
        const live = s.filter((x) => x.status === "在册").length;
        const cand = s.filter((x) => x.status === "候选").length;
        setContext({
          page: "overview",
          title: "总览分析助手",
          summary: `台账共 ${s.length} 个版本,其中在册 ${live} / 候选 ${cand}。Phase 1 闭环:数据→因子→回测→报告→解读。`,
          recommendation: ["进入「策略回测」运行生产口径复测", "关注在册母策略的失效信号"],
          nextActions: ["运行 small-cap-size 回测", "查看因子家族"],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [setContext]);

  const families = new Set(strategies.map((s) => s.family));
  const live = strategies.filter((s) => s.status === "在册").length;
  const cand = strategies.filter((s) => s.status === "候选").length;

  return (
    <div>
      <PageHeader title="总览" desc="平台整体状态 · 数据来自 /strategies 实时 API" />

      {/* 研究流程条(WEB_DESIGN §4.3)*/}
      <div className="card mb-5 flex items-center gap-2 overflow-x-auto">
        {FLOW.map((n, i) => (
          <div key={n} className="flex items-center gap-2 shrink-0">
            <span className="text-[12px] text-ink px-2 py-1 rounded bg-bg border border-cardline">{n}</span>
            {i < FLOW.length - 1 && <span className="text-subink">→</span>}
          </div>
        ))}
      </div>

      {err && <div className="card text-sm text-danger mb-4">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
        <MetricCard label="母策略家族" value={String(families.size)} sub="独立 alpha 家族" />
        <MetricCard label="在册版本" value={String(live)} tone="ok" sub="入册门槛达标" />
        <MetricCard label="候选版本" value={String(cand)} tone="warn" sub="待证伪/晋级" />
        <MetricCard label="数据口径" value="data_lake" sub="全市场·防幸存者偏差" />
      </div>

      <div className="card">
        <div className="text-sm font-medium mb-3">母策略台账</div>
        <table className="w-full text-[13px]">
          <thead>
            <tr className="text-subink text-left border-b border-cardline">
              <th className="py-1.5 font-medium">策略</th>
              <th className="py-1.5 font-medium">家族</th>
              <th className="py-1.5 font-medium">状态</th>
              <th className="py-1.5 font-medium">适用市场</th>
            </tr>
          </thead>
          <tbody>
            {strategies.map((s) => (
              <tr key={s.strategy_id} className="border-b border-cardline/60">
                <td className="py-1.5 text-ink">{s.strategy_id}</td>
                <td className="py-1.5 text-subink">{s.family_name || s.family}</td>
                <td className="py-1.5">
                  <span className={s.status === "在册" ? "text-ok" : s.status === "退役" ? "text-danger" : "text-warn"}>
                    {s.status || "—"}
                  </span>
                </td>
                <td className="py-1.5 text-subink truncate max-w-[280px]">{s.regime || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
