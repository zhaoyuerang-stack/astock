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
}

export interface FactorView {
  name: string;
  display_name: string;
  hypothesis: string;
  regime: string;
  n_versions: number;
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

// Phase 5 Agent
export interface AgentOutput {
  summary: string;
  evidence: string[];
  risk: string[];
  recommendation: string[];
  next_actions: string[];
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
