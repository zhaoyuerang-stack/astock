"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import { api } from "@/lib/api";
import type { FactorView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

export default function FactorsPage() {
  const [factors, setFactors] = useState<FactorView[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const setContext = useAgent((s) => s.setContext);

  const load = useCallback(() => {
    api
      .factors()
      .then((f) => {
        setFactors(f);
        setContext({
          page: "factors",
          title: "因子分析助手",
          summary: `当前台账有 ${f.length} 个 alpha 家族。Phase 1 仅列出家族与假设;IC/分组/相关性分析将在因子页深化(Phase 2)。`,
          evidence: f.map((x) => `${x.display_name || x.name}:${x.n_versions} 个版本`),
          recommendation: ["逐个家族查看其假设与失效信号", "下一步:接入单因子 IC 时序与相关性热力图"],
          nextActions: ["运行一次策略回测验证家族有效性"],
        });
      })
      .catch((e) => setErr(String(e)))
      .finally(() => setLoading(false));
  }, [setContext]);
  useAutoRefresh(load);

  return (
    <div>
      <PageHeader title="因子研究" desc="alpha 家族与假设(数据来自 /factors 实时 API)" />
      {loading && <div className="card text-sm text-subink">加载中…</div>}
      {err && <div className="card text-sm text-danger">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}
      {!loading && !err && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {factors.map((f) => (
            <div key={f.name} className="card">
              <div className="flex items-center justify-between">
                <div className="font-medium text-ink">{f.display_name || f.name}</div>
                <span className="text-[11px] px-1.5 py-0.5 rounded bg-bg text-subink border border-cardline">
                  {f.status || "—"} · {f.n_versions} 版本
                </span>
              </div>
              <div className="text-[12px] text-subink mt-0.5">{f.name}</div>
              {f.hypothesis && <p className="text-[13px] text-ink mt-2 leading-snug">{f.hypothesis}</p>}
              {f.regime && <p className="text-[12px] text-subink mt-1">适用:{f.regime}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
