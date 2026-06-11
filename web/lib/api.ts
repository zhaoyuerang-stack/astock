// FastAPI 客户端(Phase 0 services 接缝)。前端不做任何量化计算,只调 API。
import type {
  BacktestResult,
  DataQualityView,
  FactorHealthView,
  FactorView,
  MarketStateView,
  PortfolioView,
  RiskReport,
  StrategyView,
} from "./types";

const BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8011";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${path} → ${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  base: BASE,
  health: () => get<{ status: string; phase: number }>("/health"),
  strategies: () => get<StrategyView[]>("/strategies"),
  factors: () => get<FactorView[]>("/factors"),
  dataQuality: () => get<DataQualityView>("/data/quality"),
  strategyHealth: () => get<FactorHealthView[]>("/state/health"),
  marketState: () => get<MarketStateView>("/state/market"),
  portfolio: () => get<PortfolioView>("/portfolio"),
  risk: () => get<RiskReport>("/risk"),
  runBacktest: (params: {
    start?: string;
    top_n?: number;
    rebalance_days?: number;
    factor_window?: number;
    timing_ma?: number;
    leverage?: number;
  }) => {
    const q = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== "")
        .map(([k, v]) => [k, String(v)])
    );
    return get<BacktestResult>(`/backtest/run?${q.toString()}`);
  },
};

// 格式化助手
export const pct = (x: number, d = 2) => `${(x * 100).toFixed(d)}%`;
export const signedPct = (x: number, d = 2) =>
  `${x >= 0 ? "+" : ""}${(x * 100).toFixed(d)}%`;
export const num = (x: number, d = 2) => x.toFixed(d);
