// FastAPI 客户端(Phase 0 services 接缝)。前端不做任何量化计算,只调 API。
import type {
  AgentAskResponse,
  AuditView,
  AutoResearchCandidateView,
  AutoResearchFunnelView,
  AutoResearchIslandSearchResponse,
  AutoResearchLLMGenResponse,
  AutoResearchPromoteResponse,
  AutoResearchReviewItemView,
  AutoResearchRunResponse,
  BacktestResult,
  DataQualityView,
  LLMConfigView,
  LLMTestResult,
  FactorHealthView,
  FactorView,
  FunnelView,
  HypothesisView,
  MarketStateView,
  NavCurveView,
  PaperTradesView,
  PortfolioView,
  RegisteredExperimentView,
  TradePlanView,
  RiskReport,
  StrategyView,
  SystemConfigView,
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
  paperPlan: () => get<TradePlanView>("/paper/plan"),
  paperTrades: (limit = 200) => get<PaperTradesView>(`/paper/trades?limit=${limit}`),
  paperNav: () => get<NavCurveView>("/paper/nav"),
  risk: () => get<RiskReport>("/risk"),
  funnel: () => get<FunnelView>("/experiments/funnel"),
  hypotheses: (status?: string, limit = 60) =>
    get<HypothesisView[]>(`/experiments/hypotheses?${new URLSearchParams({ ...(status ? { status } : {}), limit: String(limit) })}`),
  registeredExperiments: () => get<RegisteredExperimentView[]>("/experiments/registered"),
  autoresearchFunnel: () => get<AutoResearchFunnelView>("/experiments/autoresearch/funnel"),
  autoresearchCandidates: (limit = 40) =>
    get<AutoResearchCandidateView[]>(`/experiments/autoresearch/candidates?limit=${limit}`),
  autoresearchReviewQueue: (limit = 20) =>
    get<AutoResearchReviewItemView[]>(`/experiments/autoresearch/review-queue?limit=${limit}`),
  reviewAutoresearch: (fingerprint: string, action: "approve" | "reject", notes = "") =>
    post<AutoResearchReviewItemView>(`/experiments/autoresearch/review/${fingerprint}`, { action, notes }),
  promoteAutoresearch: (fingerprint: string, version = "v1.0") =>
    post<AutoResearchPromoteResponse>(`/experiments/autoresearch/promote/${fingerprint}?version=${encodeURIComponent(version)}`, {}),
  runAutoresearchLLM: (params: { n?: number; theme?: string; max_stage?: string }) => {
    const q = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => [k, String(v)])
    );
    return post<AutoResearchLLMGenResponse>(`/experiments/autoresearch/run-llm?${q.toString()}`, {});
  },
  runIslandSearch: (params: { islands?: number; generations?: number; population?: number; final_stage?: string }) => {
    const q = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => [k, String(v)])
    );
    return post<AutoResearchIslandSearchResponse>(`/experiments/autoresearch/island-search?${q.toString()}`, {});
  },
  runAutoresearchSeeds: (params: { limit?: number; max_stage?: string; start?: string; sample_dates?: number | null }) => {
    const q = new URLSearchParams(
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== null && v !== "")
        .map(([k, v]) => [k, String(v)])
    );
    return post<AutoResearchRunResponse>(`/experiments/autoresearch/run-seeds?${q.toString()}`, {});
  },
  agentAsk: (request: string, context: Record<string, unknown> = {}) =>
    post<AgentAskResponse>("/agent/ask", { request, context }),
  systemConfig: () => get<SystemConfigView>("/settings/config"),
  audit: (limit = 40) => get<AuditView>(`/settings/audit?limit=${limit}`),
  getLlmConfig: () => get<LLMConfigView>("/settings/llm"),
  setLlmConfig: (body: { provider: string; model: string; base_url: string; api_key?: string | null }) =>
    post<LLMConfigView>("/settings/llm", body),
  testLlm: () => post<LLMTestResult>("/settings/llm/test", {}),
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
