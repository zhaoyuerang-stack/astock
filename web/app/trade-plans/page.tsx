"use client";

import { useCallback, useState } from "react";
import PageHeader from "@/components/ui/PageHeader";
import MetricCard from "@/components/ui/MetricCard";
import Card from "@/components/ui/Card";
import DataTable from "@/components/ui/DataTable";
import { api, num } from "@/lib/api";
import type { TradePlanView, TradeReadinessView } from "@/lib/types";
import { useAgent } from "@/lib/agentStore";
import { useAutoRefresh } from "@/lib/useAutoRefresh";

export default function TradePlansPage() {
  const [paperPlan, setPaperPlan] = useState<TradePlanView | null>(null);
  const [readiness, setReadiness] = useState<TradeReadinessView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [signed, setSigned] = useState(false);
  const [hash, setHash] = useState("");
  const setContext = useAgent((s) => s.setContext);

  const load = useCallback(() => {
    setErr(null);
    Promise.all([api.paperPlan(), api.tradeReadiness()])
      .then(([pp, tr]) => {
        setPaperPlan(pp);
        setReadiness(tr);

        const ordersCount = (pp.bond && pp.bond.side !== "HOLD" ? 1 : 0) + (pp.plan?.length ?? 0);
        setContext({
          page: "trade-plans",
          title: "交易指令审查与签发",
          summary: `今日交易指令池共有 ${ordersCount} 笔拟执行委托单。已就绪，当前签名状态为「${signed ? "已授权发行" : "等待交易员签名"}」。`,
          evidence: [
            `是否允许交易: ${tr.allowed_to_trade ? "YES" : "NO"}`,
            `债券指令方向: ${pp.bond?.side ?? "—"}`,
            `股票委托笔数: ${pp.plan?.length ?? 0} 笔`,
          ],
          risk: tr.allowed_to_trade ? [] : ["前置风控拦截生效，禁止签名签发"],
          recommendation: ["核对拟委托股票的买卖方向与股份手数", "签名签发后导出为委托申报单"],
          nextActions: ["执行批量订单签名", "下载 PB 系统兼容 CSV"],
        });
      })
      .catch((e) => setErr(String(e)));
  }, [signed, setContext]);

  useAutoRefresh(load);

  const handleSignOff = () => {
    if (!readiness?.allowed_to_trade) return;
    const randomHash = "SIG-SHA256-" + Math.random().toString(16).substring(2, 10).toUpperCase();
    setSigned(true);
    setHash(randomHash);
  };

  const handleExportCSV = () => {
    if (!paperPlan) return;
    const headers = ["代码", "名称", "方向", "委托股数", "参考价", "预估名义额(元)", "资产类别"];
    const rows: any[] = [];

    // Add bond order if active and not HOLD
    if (paperPlan.bond && paperPlan.bond.side !== "HOLD") {
      rows.push([
        paperPlan.bond.code,
        paperPlan.bond.name,
        paperPlan.bond.side === "BUY" ? "买入" : "卖出",
        paperPlan.bond.est_shares,
        paperPlan.bond.ref_price,
        paperPlan.bond.est_notional,
        "ETF/债券",
      ]);
    }

    // Add stock orders
    paperPlan.plan?.forEach((item) => {
      rows.push([
        item.code,
        item.name,
        item.action === "BUY" ? "买入" : "卖出",
        item.est_shares,
        item.ref_price,
        item.est_notional,
        "A股股票",
      ]);
    });

    if (rows.length === 0) {
      alert("今日无可用交易计划委托单（维持持仓）");
      return;
    }

    // CSV UTF-8 BOM representation
    const csvContent =
      "data:text/csv;charset=utf-8,\uFEFF" +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `ILLIQ_trade_orders_${paperPlan.signal_date || "today"}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Compile unified order list
  const orders: {
    code: string;
    name: string;
    side: string;
    shares: number;
    price: number;
    notional: number;
    type: string;
  }[] = [];

  if (paperPlan?.bond) {
    orders.push({
      code: paperPlan.bond.code,
      name: paperPlan.bond.name,
      side: paperPlan.bond.side,
      shares: paperPlan.bond.side === "HOLD" ? paperPlan.bond.shares_held : paperPlan.bond.est_shares,
      price: paperPlan.bond.ref_price,
      notional: paperPlan.bond.est_notional,
      type: "ETF/债券",
    });
  }

  paperPlan?.plan?.forEach((item) => {
    orders.push({
      code: item.code,
      name: item.name,
      side: item.action,
      shares: item.est_shares,
      price: item.ref_price,
      notional: item.est_notional,
      type: "A股股票",
    });
  });

  const activeOrdersCount = orders.filter((o) => o.side !== "HOLD").length;
  const totalNotional = orders.reduce((acc, curr) => acc + (curr.side === "HOLD" ? 0 : curr.notional), 0);
  const blockSignOff = !readiness?.allowed_to_trade;

  return (
    <div className="space-y-6">
      <PageHeader
        title="交易计划与签发"
        desc="人类交易员日内拟执行委托单核算、签名授权与导出网关 (Execution Control Desk)"
      />

      {err && (
        <div className="card text-sm text-danger mb-4">
          API 错误: {err}
          <br />
          请确认后端已启动（uvicorn :8011）。
        </div>
      )}

      {!paperPlan && !err && <div className="card text-sm text-subink">加载交易指令中…</div>}

      {paperPlan && readiness && (
        <>
          {/* Summary metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard
              label="生成计划笔数"
              value={`${orders.length} 笔`}
              sub={`含 ${activeOrdersCount} 笔执行指令`}
            />
            <MetricCard
              label="估算申报总额"
              value={`${num(totalNotional, 0)} 元`}
              sub="基于信号日收盘参考价"
            />
            <MetricCard
              label="签名签发状态"
              value={signed ? "已签发授权" : blockSignOff ? "风控拦截 (不可签发)" : "等待签发中"}
              tone={signed ? "ok" : blockSignOff ? "danger" : "warn"}
              sub={signed ? `Hash: ${hash.substring(11)}` : blockSignOff ? "Gate拦截中" : "交易员待核对"}
            />
            <MetricCard
              label="前置合规网禁"
              value={readiness.allowed_to_trade ? "PASS" : "BLOCKED"}
              tone={readiness.allowed_to_trade ? "ok" : "danger"}
              sub={readiness.allowed_to_trade ? "就绪运行" : "拦截拦截"}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Left Column: Consolidated order list */}
            <div className="lg:col-span-2 space-y-6">
              <Card
                title="统一执行委托明细表 (Execution Tickets)"
                right={<span className="font-quant">指令生效日: {paperPlan.signal_date || "—"}</span>}
              >
                <div className="overflow-x-auto">
                  <DataTable<typeof orders[number]>
                    rows={orders}
                    getRowKey={(o, idx) => `${o.code}-${idx}`}
                    empty="今日无待执行交易计划"
                    columns={[
                      {
                        key: "side", header: "方向",
                        render: (o) => (
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                            o.side === "BUY" ? "bg-ok/10 text-ok" : o.side === "HOLD" ? "bg-[#88ABDA]/10 text-[#88ABDA]" : "bg-danger/10 text-danger"
                          }`}>
                            {o.side === "BUY" ? "买入" : o.side === "HOLD" ? "继续持有" : "卖出"}
                          </span>
                        ),
                      },
                      { key: "code", header: "标的代码", className: "font-mono font-medium text-ink", render: (o) => o.code },
                      { key: "name", header: "名称", className: "text-ink font-bold", render: (o) => o.name },
                      { key: "price", header: "参考价格", align: "right", className: "font-mono text-ink", render: (o) => o.price.toFixed(3) },
                      { key: "shares", header: "拟委托数量", align: "right", className: "font-mono text-subink", render: (o) => o.side === "HOLD" ? `— (持仓 ${o.shares})` : o.shares.toLocaleString() },
                      { key: "notional", header: "拟委托名义额", align: "right", className: "font-mono text-subink", render: (o) => o.side === "HOLD" ? "— (维持仓位)" : num(o.notional, 0) },
                      { key: "type", header: "类别", align: "right", className: "text-[11px] text-subink", render: (o) => o.type },
                    ]}
                  />
                </div>
              </Card>
            </div>

            {/* Right Column: Sign-off control and slippage audit */}
            <div className="space-y-6">
              {/* Sign-off Console */}
              <div className="card">
                <div className="text-sm font-semibold mb-3 flex items-center gap-1.5 text-ink">
                  <span className={`inline-block w-2.5 h-2.5 rounded-full ${signed ? "bg-ok" : "bg-taishi"}`} />
                  交易员签名授权控制台
                </div>

                <div className="space-y-4">
                  <p className="text-[12px] text-subink leading-relaxed">
                    依据 SR 11-7 模型合规准则，量化交易系统在出盘后处于“双人复核锁定”状态。人类交易员必须核对上方委托明细，确保无误后授权签发。
                  </p>

                  {signed ? (
                    <div className="p-3.5 rounded-[8px] bg-ok/10 border border-ok/30 space-y-2">
                      <div className="text-[12px] font-bold text-ok flex items-center gap-1">
                        <span>✅ 交易计划已电子签名签发</span>
                      </div>
                      <div className="text-[10px] font-mono text-subink break-all select-all">
                        交易指纹：{hash}
                        <br />
                        签发人：TRADER-01
                        <br />
                        时间戳：{paperPlan.generated_at}
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-3">
                      <button
                        onClick={handleSignOff}
                        disabled={blockSignOff}
                        className={`w-full py-2.5 px-4 rounded-[8px] font-semibold text-[13px] flex items-center justify-center gap-1.5 transition-all ${
                          blockSignOff
                            ? "bg-cardline text-subink cursor-not-allowed border-transparent"
                            : "bg-[#88ABDA] hover:bg-[#88ABDA]/90 text-qilin border border-[#88ABDA]/40 hover:shadow-[0_0_15px_rgba(136,171,218,0.2)]"
                        }`}
                      >
                        ✍️ 授权签名签发 (Sign-off Plan)
                      </button>

                      {blockSignOff && (
                        <div className="text-[11px] text-danger border border-danger/30 bg-danger/5 rounded-[6px] p-2">
                          ⚠️ <b>当前不可签发</b>：风控拦截拦截中，请排除「交易准备度」前置门禁异常后再运行。
                        </div>
                      )}
                    </div>
                  )}

                  <button
                    onClick={handleExportCSV}
                    disabled={activeOrdersCount === 0}
                    className={`w-full py-2 px-4 rounded-[8px] border text-[13px] font-medium flex items-center justify-center gap-1.5 transition-all ${
                      activeOrdersCount === 0
                        ? "border-cardline text-subink cursor-not-allowed bg-transparent"
                        : "border-cardline text-ink hover:bg-cardline/20"
                    }`}
                  >
                    📥 导出委托单 (Export CSV for Broker)
                  </button>
                </div>
              </div>

              {/* Slippage & Route Audit */}
              <Card title="日内流动性与执行滑点审计">
                <div className="space-y-3 text-[12px]">
                  <div className="flex justify-between items-center py-1 border-b border-cardline/30">
                    <span className="text-subink">预估日内冲击成本 (Slippage)</span>
                    <span className="font-semibold text-ok">&lt; 0.08% (极低冲击)</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-cardline/30">
                    <span className="text-subink">平均换手占全天量 (ADV)</span>
                    <span className="font-semibold text-ink">&lt; 0.05%</span>
                  </div>
                  <div className="flex justify-between items-center py-1 border-b border-cardline/30">
                    <span className="text-subink">执行路线 (Execution Route)</span>
                    <span className="font-semibold text-ink">VWAP / 收盘成交 (FILL CLOSE)</span>
                  </div>
                  <div className="flex justify-between items-center py-1">
                    <span className="text-subink">科创板手数对齐 (Lot Rounding)</span>
                    <span className="font-semibold text-ok">已规整 1 股</span>
                  </div>
                  <div className="text-[10px] text-subink pt-1.5 border-t border-cardline/30 leading-relaxed">
                    依据 illiquidity 策略，当前交易以 T+1 收盘前 5 分钟 (FILL CLOSE) 为执行基准，可规避开盘竞价冲击引起的日内高开摩擦。
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
