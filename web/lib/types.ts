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
