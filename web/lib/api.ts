// FastAPI 客户端(Phase 0 services 接缝)。前端不做任何量化计算,只调 API。
import type {
  AgentAskResponse,
  BacktestResult,
  DataQualityView,
  FactorHealthView,
  FactorView,
  FunnelView,
  HypothesisView,
  MarketStateView,
  PortfolioView,
  RegisteredExperimentView,
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

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    cache: "no-store",
  });
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
  funnel: () => get<FunnelView>("/experiments/funnel"),
  hypotheses: (status?: string, limit = 60) =>
    get<HypothesisView[]>(`/experiments/hypotheses?${new URLSearchParams({ ...(status ? { status } : {}), limit: String(limit) })}`),
  registeredExperiments: () => get<RegisteredExperimentView[]>("/experiments/registered"),
  agentAsk: (request: string, context: Record<string, unknown> = {}) =>
    post<AgentAskResponse>("/agent/ask", { request, context }),
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
