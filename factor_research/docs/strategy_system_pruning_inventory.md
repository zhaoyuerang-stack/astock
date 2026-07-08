# Strategy System Pruning Inventory

Date: 2026-07-08

Purpose: classify system surfaces by whether they help produce live-tradable strategies through the canonical path:

```text
PIT data -> candidate generation -> canonical backtest -> L0-L3/9-Gate/holdout/DSR/capacity review -> registry -> readiness -> signals/paper forward -> retirement
```

This is not a deletion script. It is a triage map for reducing attention, code surface, and product clutter. Anything moved or removed still needs explicit path-level diff review and the usual guards.

## Decision Rule

| Bucket | Meaning | Default action |
| --- | --- | --- |
| KEEP | Directly protects or advances the canonical live-strategy production loop. | Continue maintaining; improve tests and guard coverage. |
| REHOME | Useful capability, wrong boundary or duplicated authority. | Move behind canonical `lake/`, `workflow/`, `services/`, `governance/`, `portfolio/`, or registry surfaces. |
| ARCHIVE | Historical, exploratory, prototype, or optional product surface. | Stop expanding; preserve only if audit/research value remains. |
| DELETE | Generated, private, local, cache, or one-off artifact with no audit value. | Do not commit; remove or ignore after confirming it is not referenced. |

## KEEP

| Surface | Why it stays | Guardrail |
| --- | --- | --- |
| `factor_research/data_lake/` | Canonical research data and artifacts. Without PIT, full-market, schema-governed data, every strategy result is suspect. | Writes must go through canonical lake writers and manifest/quality checks. |
| `factor_research/lake/` | Canonical loaders, source adapters, and data writers. | No ad hoc direct protected writes from scripts or services. |
| `factor_research/core/` | `BacktestEngine`, costs, T+1 semantics, and execution assumptions are the formal performance authority. | Never revive retired backtest modules or per-strategy backtest forks. |
| `factor_research/factors/` | Factor definitions and policy filters used by canonical strategy and research paths. | Separate alpha factors from policy/veto filters during ontology cleanup. |
| `factor_research/strategies/` | Implements registered strategy behavior and production signal logic. | Must not bypass registry status or production readiness. |
| `factor_research/factory/` | Candidate generation and validation entry into the research funnel. | Candidate output must still flow through workflow and gates before registry use. |
| `factor_research/workflow/` | Promotion, 9-Gate orchestration, holdout truncation, and registry admission path. | Any selection path using full data must truncate to `< boundary()` before metrics or persistence. |
| `factor_research/governance/` | Holdout, trial ledger, marginal checks, decay, and lifecycle controls. | Treat governance as enforcement, not as dashboard decoration. |
| `factor_research/research_ledger/` | Provenance and trial accounting needed to fight hidden p-hacking. | Append-only behavior and traceability matter more than UI polish. |
| `factor_research/app_config/` | Runtime settings, deployment policy, and guarded configuration. | No hardcoded model, path, data-source, cost, or readiness switches in business logic. |
| `factor_research/deployments/` | Deployment manifests and production identity. | Deployment must fail closed when registry/readiness/gate identity drifts. |
| `factor_research/runtime/` | Artifact path repositories and production readiness contracts. | API/read services should use runtime artifact repositories instead of open-coded paths. |
| `factor_research/portfolio/` core runners and paper engine | Strategy returns, deployment composition, cross-asset legs, and paper execution meet here. | Optimizer experiments must not bypass registry/readiness. |
| `factor_research/services/` | Controlled boundary between API/Web and research/runtime internals. | `services/read` stays read-only; `services/actions` owns heavy/write actions; `services/agent` never judges alpha validity. |
| `factor_research/api/` | Thin product/API surface over services. | API should not directly read/write runtime artifacts or call deep research internals. |
| `factor_research/contracts/` | Stable read/action view contracts for UI/API. | Contract changes require tests and consumer updates. |
| `factor_research/scripts/ci/` | Architecture, lake-writer, evidence, and holdout guardrails. | These are production safety rails, not optional helper scripts. |
| `factor_research/scripts/data/` and key `scripts/ops/` | Data updates, scheduled maintenance, readiness, signal generation, and alerting. | Ops failures should be explicit and fail closed. |
| `factor_research/tests/` | Regression, guard, and adversarial coverage. | Keep negative tests for forbidden imports/writes/bypasses, not only happy paths. |
| `factor_research/signals/`, `factor_research/paper/`, `factor_research/reports/` durable outputs | Operational and audit outputs for current signals, paper forward, and formal reports. | Generated outputs are not source code; commit only when they have explicit audit value. |
| Root governance docs: `CLAUDE.md`, `STATUS.md`, `WORKFLOW.md`, `SPEC.md`, `DECISIONS.md`, `RUNBOOK.md`, `TASKS.md`, `MULTI_AGENT.md` | They define the research constitution, current state, workflow, and collaboration rules. | Avoid duplicating source-of-truth rules across stale docs. |

## REHOME

| Surface | Why not keep as-is | Target home |
| --- | --- | --- |
| `factor_research/capacity/` | Capacity and crowding are useful, but a standalone module overstates active governance if gates consume separate logic. | Rehome live capacity checks into 9-Gate, `governance/`, or portfolio constraints. |
| `factor_research/reporting/` | Reporting concepts are useful, but active product reads mostly flow through `services/read` and generated `reports/`. | Move used report builders into `services/read`, `governance/`, or explicit report scripts. |
| `factor_research/execution/` simulation/TCA pieces | True broker execution is out of scope, but T+1/limit/suspend simulation can support paper and backtest realism. | Move used simulation/TCA logic into `core.engine`, `portfolio/paper_engine`, or governance reports. |
| `factor_research/model_risk/` | Model cards and approvals are useful, but not the canonical admission authority. | Integrate with registry, 9-Gate, and production readiness; remove duplicate evidence stores. |
| `factor_research/factor_store/` | Factor caching can speed research but is not yet mandatory production or validation infrastructure. | Promote only after provenance, freshness, and workflow/factory tests make it a real dependency. |
| `factor_research/data/` | Name conflicts with canonical `data_lake/`, and current artifacts are ad hoc AutoResearch/runs. | Move durable records to `reports/experiments`, `research_ledger`, or schema-reviewed `data_lake/factory`. |
| `factor_research/results/` | Old-style result directory should not look like an active module. | Move durable evidence to `reports/experiments`, `reports/research`, or archive. |
| `factor_research/research_toolkit/` reusable helpers | Veto/marginal-audit semantics are useful but not standalone authority. | Fold reusable pieces into `workflow/`, `governance/`, or documented research scripts. |
| `factor_research/metasearch/` recommendations | MI maps and signal-flow diagnostics help reduce search waste, but they do not prove alpha. | Feed search-space pruning decisions into factory/workflow notes; never wire directly to production selection. |
| `factor_research/knowledge/` | Useful memory and feedback context, but not a production decision engine. | Keep as research support backed by ledgers/reports; expose only traceable facts. |
| `factor_research/scripts/research/` promoted scripts | Some scripts have durable value, others are one-off. | Keep reusable, documented report generators; archive or delete one-off probes after extracting conclusions. |
| Web research pages with overlapping decisions | Multiple dashboards can create false confidence and duplicate truth. | Collapse around lifecycle decisions: experiments queue, registry, governance, data health, readiness, signals/paper. |
| Miniapp/backend read surfaces | Personal-user product may be valuable, but it is a separate audience and can confuse internal research authority. | If kept, expose conservative read-only stock decision cards through `services/read`, not internal research machinery. |
| Global data infrastructure prototypes | Global/cross-asset data may become useful, but should not pollute A-share canonical claims before schema and PIT review. | Integrate only through `lake/` and explicit data docs after production-grade validation. |

## ARCHIVE

| Surface | Why archive | Archive note |
| --- | --- | --- |
| Broker routing, TWAP/VWAP, kill-switch prototypes | They imply account automation that the system does not currently operate. | Preserve design notes only if a real execution project is later approved. |
| GIPS-style standalone audit-pack helpers with no canonical consumer | More reporting surface does not improve strategy truth unless it is wired to registry/gates. | Archive until a formal consumer exists. |
| Standalone capacity dashboards/helpers not used by gates | Capacity must affect admission or sizing, not live as a parallel narrative. | Rehome useful formulas first, then archive the shell. |
| Promotional/prototype sites under `prototypes/` | They do not produce or validate strategies. | Keep final screenshots/specs only if needed for product history. |
| Old frontend requirement docs and design variants | Product specs drift quickly and should not compete with current source-of-truth docs. | Archive with a historical-reference header. |
| One-off industry/computing/liquid-cooling reports in `docs/` | Sector reports can be research input, but most are not canonical strategy evidence. | Move durable, reproducible reports to `reports/research`; otherwise archive. |
| Strategy reports for mock or failed families | Failed evidence is useful, but should not look like current production capability. | Keep under `reports/research` only with clear status and failure reason. |
| `factor_research/scratch/` scripts with reusable lessons | Scratch is necessary for exploration but cannot remain a dependency. | Convert reusable scripts to `scripts/research` with dry-run/tests; otherwise archive. |
| Redundant Web pages that answer the same readiness/governance question | Duplicate surfaces raise maintenance cost and trust risk. | Merge the decision into the canonical page before archiving the extra route. |
| LLM/knowledge-graph visualizations that do not feed PIT-auditable factors | Narrative maps are not alpha evidence. | Archive as research context unless they generate canonical hypotheses. |

## DELETE / IGNORE

| Surface | Why delete or ignore | Constraint |
| --- | --- | --- |
| `.agents/`, `.superpowers/`, `.workbuddy/` | Local agent state and personal tooling. | Do not commit. |
| `astcok.code-workspace`, IDE/workspace files | Local machine preference. | Do not commit. |
| `project.private.config.json`, local miniapp private config | Private/local config risk. | Do not commit. |
| `default.profraw`, profiler output, `.pytest_cache/`, `.ruff_cache/`, `__pycache__/` | Generated runtime/test artifacts. | Delete or ignore. |
| Prototype render caches: `.thumbnails/`, `.waveform-cache/`, `renders/` | Generated media cache. | Delete or ignore. |
| Temporary CSV/JSON/log files in `scratch/` | Reproducible or one-off intermediate outputs. | Delete unless promoted into an auditable report. |
| Generated docs with no source or decision value | They rot and confuse source-of-truth hierarchy. | Delete or archive only with clear historical value. |
| Large local data caches outside canonical lake governance | They can create stale or non-PIT evidence paths. | Keep out of git; only canonical schema/manifest changes may be tracked. |
| Unreferenced demo data, mock datasets, and cosmetic sample content | Demo data previously caused false confidence in UI state. | Delete unless explicitly scoped as a fixture in tests. |

## First-Principles Cut Line

Keep a surface only if it answers at least one of these questions with mechanical evidence:

1. Does it make data more PIT-correct, complete, fresh, or auditable?
2. Does it create more candidate hypotheses without deciding their validity?
3. Does it make backtests, costs, capacity, holdout, DSR, or failure modes harder to fake?
4. Does it move a candidate through the canonical lifecycle without bypassing gates?
5. Does it make a live or paper decision safer, clearer, or easier to revert?

If the answer is no, the surface is not part of the strategy-production engine. It is either product packaging, historical research context, or local waste.

## Adversarial Review

Likely failure points and mitigations:

1. **Over-deleting useful formulas.** Rehome formulas first, delete shells later.
2. **Mistaking dashboards for controls.** A page is useful only if it reads canonical evidence and changes an operator decision.
3. **Creating a second admission authority.** `model_risk`, reports, and knowledge graphs must not override registry/workflow/9-Gate.
4. **Archiving failed research too aggressively.** Failed results can be valuable if they document falsification and reduce future duplicate search.
5. **Committing local noise.** Every cleanup commit must use explicit paths and prove scope with `git diff --cached`.

## Suggested Cleanup Order

1. Freeze expansion of `execution/`, `capacity/`, `reporting/`, `results/`, and non-canonical `data/`.
2. Rehome any functions actively imported by `workflow/`, `portfolio/`, `services/`, or tests.
3. Archive prototype/product/spec clutter with historical-reference headers.
4. Delete local/generated/private artifacts after confirming no tracked code references them.
5. Add guard coverage only where a class of bypass can recur.
