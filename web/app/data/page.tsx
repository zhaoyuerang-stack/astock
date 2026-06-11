"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import { api, pct } from "@/lib/api";
import type { DataQualityView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

export default function DataPage() {
  const [dq, setDq] = useState<DataQualityView | null>(null);
  const [err, setErr] = useState<string | null>(null);
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

  return (
    <div>
      <PageHeader title="数据中心" desc="数据质量状态 · 来自 validate_final + DuckDB 即席复核" />
      {err && <div className="card text-sm text-danger mb-4">API 错误:{err}<br />请确认后端已启动(uvicorn :8011)。</div>}
      {!dq && !err && <div className="card text-sm text-subink">加载中…</div>}

      {dq && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-5">
            <MetricCard label="全市场标的" value={String(dq.total)} sub="data_lake 全口径" />
            <MetricCard label="质量评分(clean)" value={pct(dq.clean_ratio, 1)} sub={`${dq.clean}/${dq.total} 干净`} />
            <MetricCard label="真问题标的" value={String(dq.severe_count)} tone={dq.severe_count > 0 ? "danger" : "ok"} sub="负价/OHLC错" />
            <MetricCard label="可用判定" value={dq.verdict} tone={tone as any} sub="据真问题数,非 clean_ratio" />
          </div>

          {dq.severe_count === 0 ? (
            <div className="card mb-5 text-sm text-ok">✅ 无负价/OHLC逻辑错;跳变标记多为除权/涨跌停,可正常回测。</div>
          ) : (
            <div className="card mb-5 text-sm text-warn">⚠️ {dq.severe_count} 只存在真问题(负价/OHLC),建议从票池剔除后再回测。</div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="card">
              <div className="text-sm font-medium mb-3">问题分布(issue_breakdown)</div>
              <table className="w-full text-[13px]">
                <tbody>
                  {Object.entries(dq.issue_breakdown).sort((a, b) => b[1] - a[1]).map(([k, v]) => {
                    const severe = k.includes("负价") || k.includes("OHLC");
                    return (
                      <tr key={k} className="border-b border-cardline/60">
                        <td className={`py-1.5 ${severe ? "text-danger" : "text-subink"}`}>{k}{severe ? " · 真问题" : ""}</td>
                        <td className="py-1.5 text-right text-ink">{v}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="card">
              <div className="text-sm font-medium mb-2">DuckDB 即席复核</div>
              {dq.duckdb?.available ? (
                <div className="text-[13px] space-y-1.5">
                  <div className="flex justify-between"><span className="text-subink">总行数</span><span className="text-ink">{dq.duckdb.rows?.toLocaleString()}</span></div>
                  <div className="flex justify-between"><span className="text-subink">标的数</span><span className="text-ink">{dq.duckdb.codes}</span></div>
                  <div className="flex justify-between"><span className="text-subink">日期范围</span><span className="text-ink">{dq.duckdb.date_range?.slice(0, 10)} ~ {dq.duckdb.date_range?.slice(-19, -9)}</span></div>
                  <div className="flex justify-between"><span className="text-subink">收盘价 ≤ 0 行数</span><span className={dq.duckdb.nonpositive_close ? "text-danger" : "text-ok"}>{dq.duckdb.nonpositive_close}</span></div>
                  <div className="flex justify-between"><span className="text-subink">已隔离区间(quarantine)</span><span className="text-ink">{dq.duckdb.quarantined_ranges ?? 0}</span></div>
                  <div className="text-[11px] text-subink pt-1">扫描已排除 quarantine 区间;负价行 = 服务视图中残留的真问题(应为 0)。</div>
                </div>
              ) : (
                <div className="text-[13px] text-subink">{dq.duckdb?.note ?? "未接入"}</div>
              )}
            </div>
          </div>

          {dq.flagged_sample.length > 0 && (
            <div className="card mt-4">
              <div className="text-sm font-medium mb-2">被标记标的(样例 {dq.flagged_sample.length} / 共 {dq.n_flagged})</div>
              <div className="flex flex-wrap gap-2">
                {dq.flagged_sample.map((f) => (
                  <span key={f.code} className="text-[12px] px-2 py-0.5 rounded bg-bg border border-cardline text-subink" title={f.issues.join(", ")}>
                    {f.code}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
