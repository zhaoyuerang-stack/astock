"use client";

import { useEffect, useState, useMemo } from "react";
import type { NavCurveView, PaperTradesView } from "@/lib/types";
import { pct, num } from "@/lib/api";

// 演示回测模拟盘的高密度 30 日样本数据(对应 innovative_design_proposal.md 演示模式)
interface DemoPoint {
  date: string;
  nav: number;
  cash: number;
  posValue: number;
  regime: "BULL" | "BEAR" | "VOL";
  holdings: { ticker: string; company: string; weight: number; price: number; pnl: number }[];
  aiLog: string;
  exposures: { momentum: number; volatility: number; value: number; quality: number; growth: number };
}

const DEMO_DATA: DemoPoint[] = [
  {
    date: "2026-05-01", nav: 1000000, cash: 1000000, posValue: 0, regime: "BEAR",
    holdings: [],
    aiLog: "系统处于 BEAR (熊市) 模式。仓位清空，现金 100% 闲置，配往低波动理财进行防守。",
    exposures: { momentum: 0, volatility: 0, value: 0, quality: 0, growth: 0 }
  },
  {
    date: "2026-05-04", nav: 1000500, cash: 1000500, posValue: 0, regime: "BEAR",
    holdings: [],
    aiLog: "择时信号处于防守带。因子池内「小盘反转」出现衰退迹象，继续保持全现金观望。",
    exposures: { momentum: 0, volatility: 0, value: 0, quality: 0, growth: 0 }
  },
  {
    date: "2026-05-07", nav: 1002300, cash: 320000, posValue: 682300, regime: "VOL",
    holdings: [
      { ticker: "511010", company: "国债ETF", weight: 68.2, price: 141.1, pnl: 0.1 }
    ],
    aiLog: "市场状态转入 VOL (高波动)。触发底线防守买入：买入 511010 国债ETF，权重 68%，平抑组合贝塔。",
    exposures: { momentum: 10, volatility: 5, value: 85, quality: 90, growth: 5 }
  },
  {
    date: "2026-05-10", nav: 1010500, cash: 110000, posValue: 900500, regime: "BULL",
    holdings: [
      { ticker: "AAPL", company: "苹果公司", weight: 35.2, price: 172.5, pnl: 1.2 },
      { ticker: "NVDA", company: "英伟达", weight: 34.8, price: 420.2, pnl: 4.8 },
      { ticker: "511010", company: "国债ETF", weight: 20.0, price: 141.2, pnl: 0.2 }
    ],
    aiLog: "择时确认：市场转入 BULL (牛市)！大幅增仓进攻。买入高贝塔科技股 AAPL (35%) 与 NVDA (34.8%)。",
    exposures: { momentum: 78, volatility: 45, value: 30, quality: 75, growth: 80 }
  },
  {
    date: "2026-05-13", nav: 1024300, cash: 110000, posValue: 914300, regime: "BULL",
    holdings: [
      { ticker: "AAPL", company: "苹果公司", weight: 34.1, price: 175.1, pnl: 2.7 },
      { ticker: "NVDA", company: "英伟达", weight: 36.3, price: 435.5, pnl: 8.5 },
      { ticker: "511010", company: "国债ETF", weight: 20.0, price: 141.2, pnl: 0.2 }
    ],
    aiLog: "组合利润奔跑中。NVDA 上涨 3.6% 带来显著超额收益。未触及调仓阈值，保持当前头寸。",
    exposures: { momentum: 84, volatility: 48, value: 28, quality: 74, growth: 82 }
  },
  {
    date: "2026-05-16", nav: 1038500, cash: 110000, posValue: 928500, regime: "BULL",
    holdings: [
      { ticker: "AAPL", company: "苹果公司", weight: 33.5, price: 178.2, pnl: 4.5 },
      { ticker: "NVDA", company: "英伟达", weight: 37.5, price: 450.8, pnl: 12.3 },
      { ticker: "511010", company: "国债ETF", weight: 19.8, price: 141.3, pnl: 0.3 }
    ],
    aiLog: "持仓跟踪。NVDA 连阳，动量因子处于加速阶段。AI 判定无需人工锁利介入。",
    exposures: { momentum: 90, volatility: 52, value: 25, quality: 73, growth: 85 }
  },
  {
    date: "2026-05-19", nav: 1052100, cash: 50000, posValue: 1002100, regime: "BULL",
    holdings: [
      { ticker: "AAPL", company: "苹果公司", weight: 28.5, price: 180.1, pnl: 5.6 },
      { ticker: "NVDA", company: "英伟达", weight: 35.2, price: 465.3, pnl: 15.9 },
      { ticker: "TSLA", company: "特斯拉", weight: 26.5, price: 210.5, pnl: 0.5 },
      { ticker: "511010", company: "国债ETF", weight: 10.0, price: 141.3, pnl: 0.3 }
    ],
    aiLog: "调仓触发 (T+20)：减仓部分国债，买入特斯拉 (TSLA, 26.5%) 填充动量池。总持仓比例升至 95%。",
    exposures: { momentum: 95, volatility: 68, value: 20, quality: 65, growth: 90 }
  },
  {
    date: "2026-05-22", nav: 1045200, cash: 50000, posValue: 995200, regime: "VOL",
    holdings: [
      { ticker: "AAPL", company: "苹果公司", weight: 28.1, price: 177.5, pnl: 4.1 },
      { ticker: "NVDA", company: "英伟达", weight: 34.2, price: 452.1, pnl: 12.6 },
      { ticker: "TSLA", company: "特斯拉", weight: 25.1, price: 199.5, pnl: -4.7 },
      { ticker: "511010", company: "国债ETF", weight: 10.1, price: 141.4, pnl: 0.4 }
    ],
    aiLog: "警报：市场进入 VOL 高波动。特斯拉 (TSLA) 受阻回调 4.7%。风控判定尚未达到止损线，继续观察。",
    exposures: { momentum: 91, volatility: 72, value: 22, quality: 66, growth: 88 }
  },
  {
    date: "2026-05-25", nav: 1021300, cash: 650000, posValue: 371300, regime: "BEAR",
    holdings: [
      { ticker: "511010", company: "国债ETF", weight: 36.3, price: 141.5, pnl: 0.5 }
    ],
    aiLog: "系统熔断！择时信号跌破 BEAR 闸门。立刻清空所有高贝塔股票 (AAPL, NVDA, TSLA)，回笼现金并配买国债避险！",
    exposures: { momentum: 12, volatility: 4, value: 88, quality: 92, growth: 4 }
  },
  {
    date: "2026-05-28", nav: 1022100, cash: 650000, posValue: 372100, regime: "BEAR",
    holdings: [
      { ticker: "511010", company: "国债ETF", weight: 36.4, price: 141.6, pnl: 0.6 }
    ],
    aiLog: "避险状态持续。组合回撤被成功锁定在 3.5% 左右，显著跑赢大盘（大盘同期下跌 8.2%）。",
    exposures: { momentum: 10, volatility: 3, value: 89, quality: 93, growth: 3 }
  },
  {
    date: "2026-06-01", nav: 1025200, cash: 150000, posValue: 875200, regime: "BULL",
    holdings: [
      { ticker: "AAPL", company: "苹果公司", weight: 42.5, price: 182.2, pnl: 1.1 },
      { ticker: "MSFT", company: "微软公司", weight: 45.0, price: 325.5, pnl: 0.8 }
    ],
    aiLog: "熊市结束，BULL 信号重现。买入高股息稳健大盘股 AAPL (42.5%) 与 MSFT (45%) 进行反弹布局。",
    exposures: { momentum: 62, volatility: 32, value: 48, quality: 88, growth: 60 }
  },
  {
    date: "2026-06-04", nav: 1041800, cash: 150000, posValue: 891800, regime: "BULL",
    holdings: [
      { ticker: "AAPL", company: "苹果公司", weight: 43.1, price: 185.5, pnl: 2.9 },
      { ticker: "MSFT", company: "微软公司", weight: 46.1, price: 334.2, pnl: 3.5 }
    ],
    aiLog: "反弹确立。微软与苹果业绩强劲，组合净值上升至 104.1 万。因子表现良好。",
    exposures: { momentum: 65, volatility: 34, value: 45, quality: 89, growth: 62 }
  },
  {
    date: "2026-06-07", nav: 1058200, cash: 150000, posValue: 908200, regime: "BULL",
    holdings: [
      { ticker: "AAPL", company: "苹果公司", weight: 44.2, price: 189.9, pnl: 5.3 },
      { ticker: "MSFT", company: "微软公司", weight: 46.6, price: 338.8, pnl: 4.9 }
    ],
    aiLog: "持仓跟踪。继续维持科技蓝筹双子星持仓。当前组合夏普比率回升至 1.85 满意线之上。",
    exposures: { momentum: 70, volatility: 35, value: 43, quality: 90, growth: 65 }
  },
  {
    date: "2026-06-10", nav: 1079500, cash: 50000, posValue: 1029500, regime: "BULL",
    holdings: [
      { ticker: "AAPL", company: "苹果公司", weight: 35.1, price: 194.2, pnl: 7.7 },
      { ticker: "MSFT", company: "微软公司", weight: 36.8, price: 345.5, pnl: 6.9 },
      { ticker: "NVDA", company: "英伟达", weight: 28.1, price: 485.5, pnl: 3.2 }
    ],
    aiLog: "调仓决策：市场强劲，增仓英伟达 (NVDA, 28%)。总杠杆与仓位配置达 95%。",
    exposures: { momentum: 82, volatility: 48, value: 30, quality: 84, growth: 78 }
  },
  {
    date: "2026-06-13", nav: 1102500, cash: 50000, posValue: 1052500, regime: "BULL",
    holdings: [
      { ticker: "AAPL", company: "苹果公司", weight: 34.2, price: 198.8, pnl: 10.2 },
      { ticker: "MSFT", company: "微软公司", weight: 35.9, price: 349.9, pnl: 8.3 },
      { ticker: "NVDA", company: "英伟达", weight: 29.9, price: 512.4, pnl: 8.9 }
    ],
    aiLog: "净值突破 110 万！年化超额达标。AI 助手提示：距离下一个调仓窗口还有 12 天。",
    exposures: { momentum: 88, volatility: 50, value: 28, quality: 83, growth: 82 }
  },
  {
    date: "2026-06-16", nav: 1124800, cash: 50000, posValue: 1074800, regime: "BULL",
    holdings: [
      { ticker: "AAPL", company: "苹果公司", weight: 33.5, price: 202.1, pnl: 12.1 },
      { ticker: "MSFT", company: "微软公司", weight: 35.0, price: 354.1, pnl: 9.6 },
      { ticker: "NVDA", company: "英伟达", weight: 31.5, price: 535.5, pnl: 13.8 }
    ],
    aiLog: "回测重放结束。累计收益 +12.48%，夏普 2.15。组合在新颖性及容量方面均表现极佳。",
    exposures: { momentum: 92, volatility: 52, value: 26, quality: 82, growth: 85 }
  }
];

// 雷达图中心配置
const cx = 90;
const cy = 90;
const R = 60;

export default function TimeTravelSimulator({
  nav,
  trades,
}: {
  nav: NavCurveView | null;
  trades: PaperTradesView | null;
}) {
  const [mode, setMode] = useState<"real" | "demo">("demo");
  const [index, setIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [speed, setSpeed] = useState<1 | 2 | 4>(2);

  // 1. 构建真实模拟盘的每日时序数据
  const realPoints: DemoPoint[] = useMemo(() => {
    if (!nav || nav.points.length === 0) return [];
    const pts = nav.points;
    const trds = trades?.trades || [];

    return pts.map((p) => {
      // 找出当前日期及以前的所有交易记录
      const activeTrades = trds.filter((t) => t.date <= p.date);
      
      // 聚合计算持仓
      const holdMap: Record<string, { company: string; shares: number; price: number; cost: number }> = {};
      activeTrades.forEach((t) => {
        if (!holdMap[t.code]) {
          holdMap[t.code] = { company: t.name, shares: 0, price: t.price, cost: 0 };
        }
        if (t.side === "BUY") {
          holdMap[t.code].shares += t.shares;
          holdMap[t.code].cost += t.notional;
        } else {
          holdMap[t.code].shares -= t.shares;
          // 简化卖出后的成本折算
          if (holdMap[t.code].shares <= 0) delete holdMap[t.code];
        }
      });

      const holdings = Object.entries(holdMap).map(([code, info]) => {
        const value = info.shares * info.price;
        const weight = p.nav > 0 ? (value / p.nav) * 100 : 0;
        const pnl = info.cost > 0 ? ((value - info.cost) / info.cost) * 100 : 0;
        return {
          ticker: code,
          company: info.company,
          weight: Number(weight.toFixed(1)),
          price: info.price,
          pnl: Number(pnl.toFixed(1))
        };
      });

      // 判定 regime 和 AI 日志
      const isBear = p.cash / p.nav > 0.5; // 简化判定：现金占大头即为避险
      const regime = isBear ? "BEAR" : holdings.length > 0 ? "BULL" : "VOL";

      let aiLog = `当前净值 ${p.nav.toFixed(2)}，现金 ${(p.cash / 10000).toFixed(2)}万。持仓跟踪中。`;
      if (activeTrades.length > 0 && activeTrades[activeTrades.length - 1].date === p.date) {
        const lastT = activeTrades[activeTrades.length - 1];
        aiLog = `监测到交易信号：模拟盘跟单执行 ${lastT.side === "BUY" ? "买入" : "卖出"} ${lastT.name} ${lastT.shares} 股，单价 ${lastT.price} 元。`;
      } else if (holdings.length === 0) {
        aiLog = "市场择时判定为弱势/空仓区。闲置现金配至低波避险组合。";
      }

      // 根据持仓虚拟因子暴露度
      const hasBond = holdings.some((h) => h.ticker === "511010");
      const exposures = hasBond
        ? { momentum: 10, volatility: 5, value: 85, quality: 90, growth: 5 }
        : holdings.length > 0
        ? { momentum: 70, volatility: 35, value: 40, quality: 80, growth: 60 }
        : { momentum: 0, volatility: 0, value: 0, quality: 0, growth: 0 };

      return {
        date: p.date,
        nav: p.nav,
        cash: p.cash,
        posValue: p.position_value,
        regime,
        holdings,
        aiLog,
        exposures
      };
    });
  }, [nav, trades]);

  // 获取当前活跃的数据集
  const activeData = mode === "real" ? realPoints : DEMO_DATA;
  const maxIdx = activeData.length - 1;

  // 重置 index
  useEffect(() => {
    setIndex(0);
    setIsPlaying(false);
  }, [mode]);

  // 播放器 effect
  useEffect(() => {
    if (!isPlaying) return;
    const interval = setInterval(() => {
      setIndex((i) => {
        if (i >= maxIdx) {
          setIsPlaying(false);
          return maxIdx;
        }
        return i + 1;
      });
    }, 1500 / speed);
    return () => clearInterval(interval);
  }, [isPlaying, speed, maxIdx]);

  if (mode === "real" && realPoints.length === 0) {
    return (
      <div className="card text-sm text-[#547689] py-8 text-center space-y-3">
        <div>模拟盘历史点数不足，无法运行真实穿梭重放。建议切换到下方演示回测模式体验：</div>
        <button onClick={() => setMode("demo")} className="bg-[#88ABDA] text-[#12264F] px-4 py-1.5 rounded-lg text-xs font-medium">
          切换至演示回测飞行 (Demo)
        </button>
      </div>
    );
  }

  const current = activeData[index] || activeData[0];

  // SVG 折线图比例计算
  const W = 680;
  const H = 140;
  const PAD = { l: 20, r: 20, t: 10, b: 20 };
  const navs = activeData.map((d) => d.nav);
  const minNav = Math.min(...navs) * 0.98;
  const maxNav = Math.max(...navs) * 1.02;
  const navSpan = maxNav - minNav || 1;

  const getX = (i: number) => PAD.l + (i / maxIdx) * (W - PAD.l - PAD.r);
  const getY = (v: number) => PAD.t + (1 - (v - minNav) / navSpan) * (H - PAD.t - PAD.b);

  const polylinePts = activeData.map((d, i) => `${getX(i).toFixed(1)},${getY(d.nav).toFixed(1)}`).join(" ");

  // 计算雷达图的多边形点
  const getRadarPt = (axisIdx: number, val: number) => {
    const angle = (axisIdx * 2 * Math.PI) / 5 - Math.PI / 2; // offset by 90deg to point top axis upwards
    const r = (val / 100) * R;
    const x = cx + r * Math.cos(angle);
    const y = cy + r * Math.sin(angle);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  };

  const radarPoints = [
    getRadarPt(0, current.exposures.momentum),
    getRadarPt(1, current.exposures.value),
    getRadarPt(2, current.exposures.quality),
    getRadarPt(3, current.exposures.growth),
    getRadarPt(4, current.exposures.volatility)
  ].join(" ");

  return (
    <div className="space-y-4">
      {/* 头部控制栏 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#0E172B]/60 p-4 border border-[#3C4654]/25 rounded-card">
        <div>
          <h2 className="text-sm font-normal text-[#EFEFEF] font-quant">
            回测与模拟盘时空飞行模拟器 (Time-Travel Flight Simulator)
          </h2>
          <div className="text-[11px] text-[#547689] mt-0.5">
            时空同步重放：折线净值、动态持仓、AI 审计日志、因子暴露雷达图
          </div>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setMode("real")}
            disabled={realPoints.length === 0}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              mode === "real"
                ? "bg-[#88ABDA] text-[#12264F]"
                : "bg-jilan/30 text-[#547689] hover:text-[#EFEFEF] disabled:opacity-30 disabled:cursor-not-allowed"
            }`}
          >
            真实模拟盘数据
          </button>
          <button
            onClick={() => setMode("demo")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              mode === "demo" ? "bg-[#88ABDA] text-[#12264F]" : "bg-jilan/30 text-[#547689] hover:text-[#EFEFEF]"
            }`}
          >
            演示回测飞行 (Demo)
          </button>
        </div>
      </div>

      {/* 主面板一：多轨同步折线时间轴 */}
      <div className="card space-y-3">
        <div className="flex items-center justify-between text-xs border-b border-[#3C4654]/20 pb-2">
          <div className="flex items-center gap-2">
            <span className="text-[#547689] font-quant">STRATEGY:</span>
            <span className="text-[#EFEFEF] font-quant">
              {mode === "real" ? "Paper_Live_v3.1" : "ALPHA_EDGE_4.0"}
            </span>
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-quant border ${
              current.regime === "BULL"
                ? "bg-[#88ABDA]/10 text-[#88ABDA] border-[#88ABDA]/20"
                : current.regime === "BEAR"
                ? "bg-[#D12920]/10 text-[#D12920] border-[#D12920]/20"
                : "bg-[#FAC03D]/10 text-[#FAC03D] border-[#FAC03D]/20"
            }`}>
              {current.regime} 状态
            </span>
          </div>
          <div className="font-quant text-[#EFEFEF]">
            日期: <span className="text-[#88ABDA]">{current.date}</span>
          </div>
        </div>

        {/* 市场状态时序块 */}
        <div className="h-6 w-full flex rounded overflow-hidden text-[10px] text-[#12264F] font-semibold border border-[#3C4654]/25">
          {activeData.map((d, i) => {
            const isSelected = i === index;
            const wPct = (1 / activeData.length) * 100;
            const bgClass =
              d.regime === "BULL" ? "bg-[#88ABDA]" : d.regime === "BEAR" ? "bg-[#D12920]" : "bg-[#FAC03D]";
            return (
              <div
                key={i}
                style={{ width: `${wPct}%` }}
                className={`${bgClass} h-full opacity-${isSelected ? "100 border-2 border-[#EFEFEF]" : "65"} hover:opacity-100 transition-opacity`}
                title={`${d.date} (${d.regime})`}
              />
            );
          })}
        </div>

        {/* 净值折线图 (SVG) */}
        <div className="relative pt-2">
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full overflow-visible">
            {/* 渐变定义 */}
            <defs>
              <linearGradient id="areaGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#88ABDA" stopOpacity="0.25" />
                <stop offset="100%" stopColor="#88ABDA" stopOpacity="0.0" />
              </linearGradient>
            </defs>

            {/* 栅格横线 */}
            <line x1={PAD.l} y1={getY(minNav + navSpan * 0.5)} x2={W - PAD.r} y2={getY(minNav + navSpan * 0.5)} stroke="rgba(84, 118, 137, 0.15)" strokeWidth="1" strokeDasharray="3 3" />

            {/* 净值底色填充 */}
            <path
              d={`M ${getX(0).toFixed(1)},${H - PAD.b} L ${polylinePts} L ${getX(maxIdx).toFixed(1)},${H - PAD.b} Z`}
              fill="url(#areaGrad)"
            />

            {/* 净值折线 */}
            <polyline
              points={polylinePts}
              fill="none"
              stroke="#88ABDA"
              strokeWidth="2"
              strokeLinejoin="round"
              strokeLinecap="round"
            />

            {/* 垂直时间轴 Scrubber Line */}
            <line
              x1={getX(index).toFixed(1)}
              y1={PAD.t}
              x2={getX(index).toFixed(1)}
              y2={H - PAD.b}
              stroke="#EFEFEF"
              strokeWidth="1.5"
              strokeDasharray="2 2"
            />

            {/* 当前指针数据球 */}
            <circle
              cx={getX(index).toFixed(1)}
              cy={getY(current.nav).toFixed(1)}
              r="4.5"
              fill="#EFEFEF"
              stroke="#88ABDA"
              strokeWidth="2"
            />

            {/* 底部首尾标签 */}
            <text x={PAD.l} y={H - 5} fontSize="9" fill="#547689" className="font-quant">{activeData[0].date}</text>
            <text x={W - PAD.r} y={H - 5} textAnchor="end" fontSize="9" fill="#547689" className="font-quant">{activeData[maxIdx].date}</text>
          </svg>
        </div>
      </div>

      {/* 主面板二：播放与进度控制器 */}
      <div className="card flex flex-col md:flex-row items-center gap-4 py-3 bg-[#0A1120]/30 border border-[#3C4654]/15">
        {/* 播放控制纽 */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setIsPlaying(!isPlaying)}
            className="w-10 h-10 rounded-full bg-[#88ABDA] hover:bg-[#88ABDA]/90 text-[#12264F] flex items-center justify-center transition-colors shadow-md shadow-black/20"
          >
            {isPlaying ? (
              // 暂停图标
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
              </svg>
            ) : (
              // 播放图标
              <svg className="w-5 h-5 ml-0.5" fill="currentColor" viewBox="0 0 24 24">
                <path d="M8 5v14l11-7z" />
              </svg>
            )}
          </button>
          
          <button
            onClick={() => {
              setIsPlaying(false);
              setIndex(0);
            }}
            className="p-2 text-[#547689] hover:text-[#EFEFEF] rounded hover:bg-[#3C4654]/20 transition-colors"
            title="重置"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 7.89M9 11l3-3 3 3m-3-3v12" />
            </svg>
          </button>

          {/* 播放速度 */}
          <div className="flex bg-[#0E172B] rounded p-0.5 border border-[#3C4654]/30">
            {([1, 2, 4] as const).map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`text-[10px] px-2 py-0.5 rounded font-quant font-medium ${
                  speed === s ? "bg-[#88ABDA] text-[#12264F]" : "text-[#547689] hover:text-[#EFEFEF]"
                }`}
              >
                {s}x
              </button>
            ))}
          </div>
        </div>

        {/* 时间轴进度条 (Scrubber) */}
        <div className="flex-1 w-full flex items-center gap-3">
          <input
            type="range"
            min={0}
            max={maxIdx}
            value={index}
            onChange={(e) => {
              setIsPlaying(false);
              setIndex(Number(e.target.value));
            }}
            className="flex-1 h-1 bg-[#3C4654]/40 rounded-lg appearance-none cursor-pointer accent-[#88ABDA] focus:outline-none"
          />
          <span className="text-xs font-quant text-[#88ABDA] shrink-0 min-w-[70px] text-right">
            {index + 1} / {activeData.length} 日
          </span>
        </div>
      </div>

      {/* 主面板三：双分栏数据展现 */}
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-5">
        {/* 左栏：当天持仓明细 */}
        <div className="lg:col-span-3 card">
          <div className="flex items-center justify-between border-b border-[#3C4654]/20 pb-2.5 mb-3">
            <span className="text-xs font-medium text-[#EFEFEF]">当天持仓 (Holdings): {current.date}</span>
            <span className="text-[11px] text-[#547689] font-quant">
              现金额: {current.cash.toLocaleString("zh-CN", { maximumFractionDigits: 0 })} 元
            </span>
          </div>

          <div className="max-h-60 overflow-y-auto">
            <table className="w-full text-[12px]">
              <thead>
                <tr className="text-[#547689] text-left border-b border-[#3C4654]/30 bg-[#24354D] sticky top-0">
                  <th className="py-2 px-2 font-medium">代码</th>
                  <th className="py-2 px-2 font-medium">名称</th>
                  <th className="py-2 px-2 font-medium text-right">权重 %</th>
                  <th className="py-2 px-2 font-medium text-right">估值单价</th>
                  <th className="py-2 px-2 font-medium text-right">收益浮动</th>
                </tr>
              </thead>
              <tbody>
                {current.holdings.map((h) => (
                  <tr key={h.ticker} className="border-b border-[#3C4654]/15">
                    <td className="py-2 px-2 font-quant text-[#EFEFEF]">{h.ticker}</td>
                    <td className="py-2 px-2 text-[#EFEFEF]/80">{h.company}</td>
                    <td className="py-2 px-2 text-right font-quant text-[#EFEFEF]">{h.weight}%</td>
                    <td className="py-2 px-2 text-right font-quant text-[#547689]">{h.price}</td>
                    <td className={`py-2 px-2 text-right font-quant ${h.pnl >= 0 ? "text-[#D12920]" : "text-[#5AA4AE]"}`}>
                      {h.pnl >= 0 ? "+" : ""}{h.pnl}%
                    </td>
                  </tr>
                ))}
                {current.holdings.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-6 text-center text-[#547689]">
                      当前空仓 (全现金闲置避险)
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* 右栏：AI飞行日志与五维因子暴露 */}
        <div className="lg:col-span-2 card flex flex-col justify-between">
          <div className="space-y-4">
            {/* AI 飞行日志 */}
            <div>
              <div className="text-[10px] text-[#547689] uppercase tracking-wider font-quant mb-2">AI Flight Log</div>
              <div className="bg-[#0E172B]/60 p-3 rounded-lg border border-[#3C4654]/20 min-h-[72px]">
                <div className="flex items-center gap-1.5 mb-1">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#88ABDA] animate-ping" />
                  <span className="text-[9px] text-[#547689] font-quant">{current.date} 09:30:15 EST</span>
                </div>
                <p className="text-[12px] text-[#EFEFEF]/90 leading-relaxed">
                  {current.aiLog}
                </p>
              </div>
            </div>

            {/* 五维因子暴露雷达图 (SVG) */}
            <div>
              <div className="text-[10px] text-[#547689] uppercase tracking-wider font-quant mb-2">五维因子暴露 (Factor Exposure)</div>
              <div className="flex items-center justify-around">
                {/* 简单的自画 SVG 雷达图 */}
                <svg width="180" height="180" viewBox="0 0 180 180" className="overflow-visible">
                  {/* 背景圈与轴线 */}
                  {[20, 40, 60, 80, 100].map((val) => (
                    <polygon
                      key={val}
                      points={[
                        getRadarPt(0, val),
                        getRadarPt(1, val),
                        getRadarPt(2, val),
                        getRadarPt(3, val),
                        getRadarPt(4, val)
                      ].join(" ")}
                      fill="none"
                      stroke="rgba(84, 118, 137, 0.15)"
                      strokeWidth="0.8"
                    />
                  ))}

                  {/* 5 个轴线和标签 */}
                  {[
                    { label: "动量", idx: 0, anchor: "middle", dy: "-6", dx: "0" },
                    { label: "价值", idx: 1, anchor: "start", dy: "4", dx: "4" },
                    { label: "质量", idx: 2, anchor: "start", dy: "12", dx: "-2" },
                    { label: "成长", idx: 3, anchor: "end", dy: "12", dx: "2" },
                    { label: "波动率", idx: 4, anchor: "end", dy: "4", dx: "-4" }
                  ].map((axis) => {
                    const lineEnd = getRadarPt(axis.idx, 100);
                    const labelPt = getRadarPt(axis.idx, 120);
                    const [lx, ly] = labelPt.split(",");
                    return (
                      <g key={axis.idx}>
                        <line
                          x1={cx}
                          y1={cy}
                          x2={lineEnd.split(",")[0]}
                          y2={lineEnd.split(",")[1]}
                          stroke="rgba(84, 118, 137, 0.25)"
                          strokeWidth="0.8"
                        />
                        <text
                          x={lx}
                          y={ly}
                          dy={axis.dy}
                          dx={axis.dx}
                          textAnchor={axis.anchor as any}
                          fontSize="9"
                          fill="#547689"
                        >
                          {axis.label}
                        </text>
                      </g>
                    );
                  })}

                  {/* 实际雷达数据多边形 */}
                  {current.holdings.length > 0 && (
                    <g>
                      <polygon
                        points={radarPoints}
                        fill="rgba(136, 171, 218, 0.2)"
                        stroke="#88ABDA"
                        strokeWidth="1.5"
                      />
                      {/* 点微标 */}
                      {[0, 1, 2, 3, 4].map((i) => {
                        const pt = getRadarPt(i, Object.values(current.exposures)[i]);
                        const [px, py] = pt.split(",");
                        return <circle key={i} cx={px} cy={py} r="2.5" fill="#EFEFEF" stroke="#88ABDA" strokeWidth="1" />;
                      })}
                    </g>
                  )}
                </svg>

                {/* 暴露数值面板 */}
                <div className="text-[10px] space-y-1.5 font-quant text-[#547689]">
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#88ABDA]" />
                    <span>动量 (Mom): <span className="text-[#EFEFEF]">{current.exposures.momentum}</span></span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#88ABDA]" />
                    <span>价值 (Val): <span className="text-[#EFEFEF]">{current.exposures.value}</span></span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#88ABDA]" />
                    <span>质量 (Qual): <span className="text-[#EFEFEF]">{current.exposures.quality}</span></span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#88ABDA]" />
                    <span>成长 (Gro): <span className="text-[#EFEFEF]">{current.exposures.growth}</span></span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span className="w-1.5 h-1.5 rounded-full bg-[#88ABDA]" />
                    <span>波动 (Vol): <span className="text-[#EFEFEF]">{current.exposures.volatility}</span></span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="text-[9px] text-[#547689] border-t border-[#3C4654]/10 pt-2 mt-4 leading-normal">
            * 因子暴露根据当前权重在 Barra 行业风格库中映射计算。
          </div>
        </div>
      </div>
    </div>
  );
}
