"""Central runtime artifact path definitions.

This module is intentionally path-only: it must not read, write, or create
runtime artifacts. Callers inject a root in tests and decide their own IO mode.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ArtifactPaths:
    root: Path = PROJECT_ROOT

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))

    @property
    def data_lake(self) -> Path:
        return self.root / "data_lake"

    @property
    def reports(self) -> Path:
        return self.root / "reports"

    @property
    def paper(self) -> Path:
        return self.root / "paper"

    @property
    def signals(self) -> Path:
        return self.root / "signals"

    @property
    def agent_dir(self) -> Path:
        return self.data_lake / "agent"

    @property
    def research_signals_dir(self) -> Path:
        return self.data_lake / "research_signals"

    @property
    def shadow_incubation_log(self) -> Path:
        return self.agent_dir / "shadow_incubation_log.json"

    @property
    def ontology_predictions(self) -> Path:
        return self.research_signals_dir / "ontology_predictions.json"

    @property
    def shadow_ontology_performance(self) -> Path:
        return self.reports / "islands" / "shadow_ontology_performance.json"

    @property
    def amount_timing_validation(self) -> Path:
        return self.reports / "ops" / "amount_timing_validation.json"

    @property
    def logic_chains_dir(self) -> Path:
        return self.research_signals_dir / "logic_chains"

    @property
    def industry_knowledge_graph(self) -> Path:
        return self.research_signals_dir / "industry_knowledge_graph.json"

    @property
    def quality_report(self) -> Path:
        return self.data_lake / "quality_report.json"

    @property
    def data_issue_triage(self) -> Path:
        return self.reports / "data" / "data_issue_triage.json"

    @property
    def factor_health(self) -> Path:
        return self.reports / "factor_health.json"

    @property
    def decay_status(self) -> Path:
        return self.reports / "decay_status.json"

    @property
    def paper_account(self) -> Path:
        return self.paper / "account.json"

    @property
    def signal_state(self) -> Path:
        return self.signals / "state.json"

    @property
    def daily_all_prices(self) -> Path:
        return self.data_lake / "price" / "daily_all.parquet"

    @property
    def daily_raw_all_prices(self) -> Path:
        return self.data_lake / "price" / "daily_raw_all.parquet"

    @property
    def price_daily_dir(self) -> Path:
        return self.data_lake / "price" / "daily"

    @property
    def trade_calendar(self) -> Path:
        return self.data_lake / "meta" / "trade_calendar.parquet"

    @property
    def agent_task_log(self) -> Path:
        return self.agent_dir / "agent_tasks.jsonl"

    @property
    def config_audit_log(self) -> Path:
        return self.agent_dir / "config_audit.jsonl"

    @property
    def action_audit_log(self) -> Path:
        return self.agent_dir / "action_audit.jsonl"

    @property
    def factory_dir(self) -> Path:
        return self.data_lake / "factory"

    @property
    def autoresearch_dir(self) -> Path:
        return self.factory_dir / "autoresearch"

    @property
    def autoresearch_candidates(self) -> Path:
        return self.autoresearch_dir / "candidates.jsonl"

    @property
    def autoresearch_experiment_log(self) -> Path:
        return self.autoresearch_dir / "experiment_log.jsonl"

    @property
    def autoresearch_review_queue(self) -> Path:
        return self.autoresearch_dir / "review_queue.jsonl"

    @property
    def factory_experiment_log(self) -> Path:
        return self.factory_dir / "experiment_log.jsonl"

    @property
    def research_workspace_dir(self) -> Path:
        return self.factory_dir / "research_workspace"

    @property
    def research_workspace_drafts(self) -> Path:
        return self.research_workspace_dir / "drafts.jsonl"

    @property
    def research_workspace_reviews(self) -> Path:
        return self.research_workspace_dir / "reviews.jsonl"
