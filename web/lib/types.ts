// 镜像 factor_research/contracts/views.py(API 响应形状)

export interface BacktestResult {
  annual: number;
  vol: number;
  sharpe: number;
  maxdd: number;
  calmar: number;
  hit: boolean;
  n: number;
  turnover_annual: number;
  cost_annual: number;
  yearly_returns: Record<string, number>;
  n_stocks: number;
  n_days: number;
  start: string;
  end: string;
  family: string;
  version: string;
}

export interface StrategyView {
  strategy_id: string;
  family: string;
  family_name: string;
  family_status: string;
  version: string;
  status: string;
  hypothesis: string;
  regime: string;
  desc: string;
  data_scope: Record<string, unknown> | string;
  metrics: Record<string, number>;
  config: Record<string, unknown>;
  notes: string;
  capacity_m: number;
  admission?: Record<string, any>;   // 双轨准入 {track, rationale}
  nine_gate?: Record<string, any>;   // Nine-Gate 摘要 {dsr_p, gate4_verdict, n_trials, ...}
  style_betas?: Record<string, number>;        // 家族级风格暴露 {size, value, momentum, ...}
  failure_boundaries?: Record<string, number>; // 家族级失效边界 {max_drawdown, max_drawdown_days}
  decay_signal?: string;                        // 家族级失效信号(死因/触发条件)
}

export interface FactorView {
  name: string;
  display_name: string;
  hypothesis: string;
  regime: string;
  n_versions: number;
  n_registered?: number;   // 在册版本数(0 = 候选/噪音池)
  status: string;
}

// Phase 2 状态层
export interface DataQualityView {
  total: number;
  clean: number;
  clean_ratio: number;
  issue_breakdown: Record<string, number>;
  n_flagged: number;
  flagged_sample: { code: string; issues: string[] }[];
  severe_count: number;
  jump_count: number;
  verdict: string;
  triage_summary?: Record<string, any>;
  production_blocked?: boolean;
  backtest_blocked?: boolean;
  duckdb: {
    available: boolean;
    note?: string;
    rows?: number;
    codes?: number;
    date_range?: string;
    nonpositive_close?: number;
    quarantined_ranges?: number;
  } | null;
}

export interface FactorHealthView {
  name: string;
  sharpe: number;
  momentum_6m: number;
  trend: string;
}

export interface MarketStateView {
  current_position: string;
  last_action: string;
  last_signal_date: string | null;
  last_rebalance_date: string | null;
  n_holdings: number;
}

// Phase 3 组合 / 风控
export interface Holding {
  code: string;
  weight: number;
}

export interface PortfolioView {
  nav: number;
  cash: number;
  current_positions: Holding[];
  stance: string;
  regime: string;
  note: string;
  target_holdings: Holding[];
  target_as_of: string | null;
  target_note: string;
}

export interface RiskRuleCheck {
  rule: string;
  threshold: number;
  current: number | null;
  status: "ok" | "warn" | "breach" | "na";
  note: string;
}

export interface ControlAction {
  action_id: string;
  object_type: string;
  object_id: string;
  trigger_state: string;
  action: string;
  reason: string;
  recommendation: string;
  requires_confirmation: boolean;
  executed: boolean;
  executed_by: string;
}

export interface RiskReport {
  evaluated_on: string;
  checks: RiskRuleCheck[];
  control_actions: ControlAction[];
  verdict: "正常" | "预警" | "超限";
}

// Phase 4 研究实验
export interface FunnelView {
  total: number;
  stages: { stage: string; count: number }[];
  side: { stage: string; count: number }[];
  discard_ratio: number;
  registered: number;
}

export interface HypothesisView {
  id: string;
  name: string;
  factor_fn_name: string;
  factor_params: Record<string, unknown>;
  timing_fn_name: string | null;
  status: string;
  source: string;
  mechanism: string;
  citation: string;
  created_at: string;
}

export interface RegisteredExperimentView {
  strategy_id: string;
  family_name: string;
  version: string;
  status: string;
  date: string;
  config_hash: string;
  config: Record<string, unknown>;
  metrics: Record<string, number>;
  data_scope: Record<string, unknown>;
}

export interface AutoResearchCandidateView {
  fingerprint: string;
  status: string;
  source: string;
  ast: Record<string, unknown>;
  complexity_score: number;
  max_auto_stage: string;
  notes: string;
  created_at: string;
}

export interface AutoResearchReviewItemView {
  fingerprint: string;
  status: string;
  decision: string;
  reason: string;
  candidate: Record<string, unknown>;
  metrics: Record<string, unknown>;
  review_action: string; // "" = 待复核;approve / reject = 已人工决策
  reviewer_notes: string;
  reviewed_at: string;
}

export interface AutoResearchFunnelView {
  total: number;
  stages: { stage: string; count: number }[];
  review_queue: number;
}

export interface AutoResearchRunResultView {
  fingerprint: string;
  status: string;
  decision: string;
  reason: string;
  protocols: string[];
}

export interface AutoResearchRunResponse {
  vintage_id: string;
  max_stage: string;
  results: AutoResearchRunResultView[];
}

export interface AutoResearchPromoteResponse {
  fingerprint: string;
  hypothesis_name: string;
  version: string;
  registered: boolean;
  detail: string;
}

export interface AutoResearchLLMGenResponse {
  model: string;
  requested: number;
  accepted: number;
  rejected: string[];
  run: AutoResearchRunResponse;
}

export interface AutoResearchChampionView {
  fingerprint: string;
  island: number;
  generation: number;
  icir: number;
  expr: string;
  status: string;
  decision: string;
  reason: string;
}

export interface AutoResearchIslandSearchResponse {
  vintage_id: string;
  islands: number;
  generations: number;
  evaluated: number;
  seeded_by: string;
  champions: AutoResearchChampionView[];
}

export interface ActionTokenView {
  header: string;
  token: string;
  source: string;
}

export interface ActionJobView {
  job_id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed" | string;
  created_at: string;
  started_at: string;
  finished_at: string;
  result: Record<string, unknown> | null;
  error: string;
}

// Phase 5 Agent
export interface AgentCitation {
  source_id: string;
  source_type: string;
  title: string;
  source_path: string;
  excerpt: string;
}

export interface AgentMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AgentSessionMessage {
  role: "user" | "assistant" | string;
  content: string;
  created_at: string;
  metadata: Record<string, unknown>;
}

export interface AgentSession {
  session_id: string;
  user_id: string;
  title: string;
  page_context: string;
  status: string;
  created_at: string;
  updated_at: string;
  messages: AgentSessionMessage[];
}

export interface AgentOutput {
  summary: string;
  evidence: string[];
  risk: string[];
  recommendation: string[];
  next_actions: string[];
  citations: AgentCitation[];
  source_types: string[];
  suggested_navigation: string[];
  confidence: number;
  requires_human_confirmation: boolean;
}

export interface AgentAskResponse {
  output: AgentOutput;
  task_id: string;
  tool: string | null;
  risk: string | null;
  llm_ready: boolean;
}

export interface AgentSessionAskResponse extends AgentAskResponse {
  session: AgentSession;
}

// Phase 6 系统设置 / 审计
export interface SystemConfigView {
  cost: Record<string, number | boolean>;
  strategy: Record<string, unknown>;
  risk_policy: Record<string, number>;
  data: Record<string, unknown>;
  ai_model: { llm_ready: boolean; provider: string; mode: string; model?: string; base_url?: string };
  services: { name: string; status: string }[];
  quarantine_ranges: number;
}

export interface AuditEntry {
  kind: string;
  summary: string;
  detail: string;
  status: string;
  actor: string;
}

export interface AuditView {
  entries: AuditEntry[];
  total: number;
}

export interface LLMConfigView {
  provider: string;
  model: string;
  base_url: string;
  has_key: boolean;
  key_hint: string;
  llm_ready: boolean;
}

export interface LLMTestResult {
  ok: boolean;
  message: string;
}

// ── 模拟盘跟单(P5 债券轮动 · 操作卡/流水/净值)──────────────────────────────
export interface PaperTradeRow {
  date: string;
  code: string;
  name: string;
  side: "BUY" | "SELL" | string;
  shares: number;
  price: number;
  notional: number;
  cost: number;
  cash_after: number;
}

export interface PaperBlockedRow {
  side: string;
  code: string;
  name: string;
  reason: string;
}

export interface PaperPositionRow {
  code: string;
  name: string;
  shares: number;
  cost: number;
  price: number | null;
  mv: number;
  pnl: number;
  asset: "stock" | "etf" | string;
}

export interface PaperPlanItem {
  action: "BUY" | "SELL" | string;
  code: string;
  name: string;
  ref_price: number;
  est_shares: number;
  est_notional: number;
}

export interface BondInstructionView {
  active: boolean;
  side: "BUY" | "SELL" | "HOLD" | string;
  code: string;
  name: string;
  ref_price: number;
  est_shares: number;
  est_notional: number;
  shares_held: number;
  note: string;
}

export interface CandidateStockRow {
  code: string;
  name: string;
}

export interface TradePlanView {
  signal_date: string;
  account_date: string;
  last_exec_signal_date: string;
  generated_at: string;
  stale: boolean;
  stale_reason: string;
  regime: string;
  regime_dist: number;
  in_market: boolean;
  band_exposure: number;
  action: string;
  small_index_vs_ma16: number;
  binary_in_market_shadow: boolean;
  base_in_market: boolean;
  executed: PaperTradeRow[];
  blocked: PaperBlockedRow[];
  plan: PaperPlanItem[];
  bond: BondInstructionView | null;
  positions: PaperPositionRow[];
  candidates: CandidateStockRow[];
  nav: number;
  cash: number;
  position_value: number;
  total_return: number;
  disclaimer: string;
}

export interface NavPoint {
  date: string;
  nav: number;
  cash: number;
  position_value: number;
  total_return: number;
}

export interface NavCurveView {
  points: NavPoint[];
  inception: string;
  init_capital: number;
  latest_nav_date: string;
  latest_nav: number;
  total_return: number;
  max_drawdown: number;
}

export interface PaperTradesView {
  trades: PaperTradeRow[];
  total: number;
}

export interface TradeReadinessView {
  allowed_to_trade: boolean;
  data_status: string;
  model_version: string;
  factor_health: string;
  portfolio_risk: string;
  cost_forecast: string;
  liquidity_status: string;
  regime_status: string;
  regime_confidence: number;
  kill_switch_status: string;
  human_approval_required: boolean;
  details: Record<string, any>;
}

export interface GovernanceView {
  model_cards: Record<string, any>[];
  validation_reports: Record<string, any>[];
  experiments_ledger: Record<string, any>[];
  committees: Record<string, any>[];
}
