---
name: a-share-valuation-snapshot
description: Generate guarded A-share company valuation snapshot tables from the local factor_research data lake. Use when the user asks to fill valuation frameworks for A-share stocks, compare companies by stock price, market cap, PE/PB/PS, EV/EBITDA, PEG, or asks why local data infrastructure should be used instead of ad hoc web/API scraping.
---

# A Share Valuation Snapshot

## Overview

Use this skill to build A-share valuation tables from the repository's own `factor_research/data_lake` first. The goal is not to maximize field coverage; it is to produce a table whose source, date, units, and missing fields are honest.

## First Principles

- Treat `data_lake` as the first source of truth before external web/API scraping.
- Use source-defined valuation fields when available. Do not recompute PE/PB/PS from adjusted prices.
- Keep forecast fields separate from historical fields. `PE(2026E)` and consensus PEG require a forecast/consensus source; do not backfill them from historical financials.
- State stale dates per security. A mixed-date table is allowed only when each row shows or discloses the row date.
- Prefer leaving a cell blank or `—` over inventing a number.

## Workflow

1. Read repo context if not already done: `CLAUDE.md`, `STATUS.md`, and `git status --short --branch`.
2. Confirm the requested companies and map each to a six-digit A-share code.
3. Inspect local availability:
   - `factor_research/data_lake/daily_basic/daily_basic_all.parquet` for `total_mv`, `pe_ttm`, `pb`, `ps_ttm`/`ps`.
   - `factor_research/data_lake/price/daily_raw/<code>.parquet` for unadjusted `raw_close`.
   - Optional: `financials/income_all.parquet` and `financials/balancesheet_all.parquet` for estimated EV/EBITDA.
   - Optional: `financials/fina_indicator_all.parquet` for latest historical `netprofit_yoy` if the user accepts a historical PEG proxy.
4. Use the bundled script when the standard table is enough:

```bash
python3 .agents/skills/a-share-valuation-snapshot/scripts/valuation_snapshot.py \
  --codes "002371:北方华创,688012:中微公司,688082:盛美上海" \
  --include-date
```

5. If the user asked for the exact framework without a date column, disclose dates in prose and omit `日期` from the final table.
6. Before finalizing, run the adversarial review checklist below.

## Field Policy

| Requested field | Local source | Unit / rule |
|---|---|---|
| 股价 | `price/daily_raw/<code>.parquet::raw_close` | Yuan, unadjusted close |
| 市值 | `daily_basic.total_mv` | Tushare unit is ten-thousand yuan; convert to 亿元 by `/ 10000` |
| PE(TTM) | `daily_basic.pe_ttm` | Source-defined, leave blank if missing/non-finite |
| PE(2026E) | Consensus/forecast source only | Leave blank unless a real forecast source is available |
| PB | `daily_basic.pb` | Source-defined |
| PS | Prefer `daily_basic.ps_ttm`, fallback to `ps` | Source-defined |
| EV/EBITDA | Optional estimate from local financials | Clearly label as local historical estimate, not vendor consensus |
| PEG | Consensus PEG preferred; historical proxy only if disclosed | If using local proxy: `PE(TTM) / latest netprofit_yoy_pct`, positive growth only |

## Adversarial Review

Attack the output before returning it:

1. Did any row use a different latest date? If yes, disclose it.
2. Did any field come from historical financials while the label implies forecast consensus? If yes, relabel or blank it.
3. Did any valuation use adjusted prices directly? If yes, discard and use `daily_basic` or `daily_raw`.
4. Are units correct, especially Tushare `total_mv`? It is ten-thousand yuan, not yuan.
5. Are missing values honest? Do not replace missing `PE(2026E)` with an inferred value.

## Delivery Pattern

Keep the final answer short and explicit:

- Give the table.
- State data source paths and latest row dates.
- State which columns are unavailable locally and why.
- State whether `EV/EBITDA` and `PEG` are strict consensus fields or local historical estimates.
