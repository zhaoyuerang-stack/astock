---
name: a-share-valuation-snapshot
description: Generate guarded A-share company valuation snapshot tables, relative valuation analysis, and a rule-based financial valuation attractiveness index with PNG chart output from the local factor_research data lake. Use when the user asks to fill valuation frameworks for A-share stocks, compare companies by stock price, market cap, PE/PB/PS, EV/EBITDA, PEG, calculate medians, relative deviations, valuation premium/discount, build a buy/attractiveness index, output a PNG image plus explanation, or asks why local data infrastructure should be used instead of ad hoc web/API scraping.
---

# A Share Valuation Snapshot

## Overview

Use this skill to build A-share valuation tables, cross-sectional relative valuation analysis, and a PNG financial-valuation attractiveness chart from the repository's own `factor_research/data_lake` first. The goal is not to maximize field coverage; it is to produce an output whose source, date, units, missing fields, function relationship, and peer-relative conclusions are honest.

The skill must never assume a fixed stock batch. The stock universe must come from the user's request, a supplied stock-universe file, or a clearly stated upstream screen.

## First Principles

- Treat `data_lake` as the first source of truth before external web/API scraping.
- Do not hardcode a peer set. Every run must accept its company universe as an input.
- Use source-defined valuation fields when available. Do not recompute PE/PB/PS from adjusted prices.
- Keep forecast fields separate from historical fields. `PE(2026E)` and consensus PEG require a forecast/consensus source; do not backfill them from historical financials.
- State stale dates per security. A mixed-date table is allowed only when each row shows or discloses the row date.
- Prefer leaving a cell blank or `—` over inventing a number.
- Treat median/deviation analysis as peer-sample diagnostics, not an absolute cheap/expensive truth.
- Treat the "买入指数" as a rule-based attractiveness index for further review, not an automatic trading instruction.

## Workflow

1. Read repo context if not already done: `CLAUDE.md`, `STATUS.md`, and `git status --short --branch`.
2. Confirm the requested companies and map each to a six-digit A-share code. If the user has not provided a universe, ask for one or use a clearly named upstream screen; never reuse a previous ad hoc batch.
3. Inspect local availability:
   - `factor_research/data_lake/daily_basic/daily_basic_all.parquet` for `total_mv`, `pe_ttm`, `pb`, `ps_ttm`/`ps`.
   - `factor_research/data_lake/price/daily_raw/<code>.parquet` for unadjusted `raw_close`.
   - Optional: `financials/income_all.parquet` and `financials/balancesheet_all.parquet` for estimated EV/EBITDA.
   - Optional: `financials/fina_indicator_all.parquet` for latest historical `netprofit_yoy` if the user accepts a historical PEG proxy.
4. Use the bundled script when the standard table is enough. Prefer `--codes-file` for reusable screens and larger peer sets:

```bash
python3 .agents/skills/a-share-valuation-snapshot/scripts/valuation_snapshot.py \
  --codes-file /path/to/stock_universe.csv \
  --include-date \
  --analysis \
  --buy-index \
  --output-png /private/tmp/a_share_buy_index.png
```

For quick one-off runs, pass an explicit comma-separated list:

```bash
python3 .agents/skills/a-share-valuation-snapshot/scripts/valuation_snapshot.py \
  --codes "000001:示例公司A,600000:示例公司B" \
  --analysis
```

`--codes-file` accepts CSV/TSV files with columns such as `code,name`, `ts_code,name`, `股票代码,公司`, or plain text with one `code[:name]` per line.

5. If the user asked for the exact framework without a date column, disclose dates in prose and omit `日期` from the final table.
6. For comparison requests, include the analysis section unless the user only asked for raw data.
7. For buy-index requests, return the PNG image path and a concise explanation of support/constraint factors for each company.
8. Before finalizing, run the adversarial review checklist below.

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

## Analysis Policy

Calculate peer-relative analytics only on available numeric values:

- **Peer median**: report the sample median and valid-company count for `市值`, `PE(TTM)`, `PB`, `PS`, `EV/EBITDA`, and `PEG`.
- **Deviation**: `deviation_pct = (company_value / peer_median - 1) * 100`; leave blank if the company value or median is missing/non-positive.
- **Composite premium/discount**: median of available deviations across valuation multiples only: `PE(TTM)`, `PB`, `PS`, `EV/EBITDA`, `PEG`. Exclude `市值` because it is scale, not valuation richness. Require at least 3 available multiples before assigning a relative premium/discount label.
- **Labeling**: `>= +20%` = relative premium, `<= -20%` = relative discount, otherwise near peer median. Use neutral wording and say "relative to this peer set".
- **Do not overread**: a high PEG proxy can be caused by stale/low historical growth; a missing or negative-growth PEG should not be ranked as cheap.

## Buy Index Function

Use this transparent first-version rule function:

```text
FinancialQuality =
  0.25 * RevenueQuality
+ 0.25 * ProfitQuality
+ 0.25 * CashflowQuality
+ 0.15 * BalanceSheetStrength
+ 0.10 * OperatingEfficiency

ValuationAttractiveness = 100 / (1 + exp(RelativeValuationPremium / 35))
RiskControl = 100 - RiskPenalty

PreConfidenceIndex =
  0.30 * FinancialQuality
+ 0.25 * GrowthCredibility
+ 0.30 * ValuationAttractiveness
+ 0.15 * RiskControl

BuyIndex = PreConfidenceIndex * DataConfidence
```

Implementation notes:

- `RelativeValuationPremium` comes from the peer-median deviation analysis across `PE(TTM)`, `PB`, `PS`, `EV/EBITDA`, and `PEG`.
- `RiskPenalty` is the max of major stress signals where available: receivable stress, inventory stress, cashflow/profit mismatch, leverage stress, and stale-data penalty.
- `DataConfidence` is the minimum of field coverage, market-data freshness, and report recency. Missing data must reduce confidence instead of being silently treated as neutral.
- The PNG chart must be raster image output (`.png`), not SVG. Use quality on the y-axis, valuation attractiveness on the x-axis, point size for market cap, and color for risk penalty.

## Adversarial Review

Attack the output before returning it:

1. Did any row use a different latest date? If yes, disclose it.
2. Did any field come from historical financials while the label implies forecast consensus? If yes, relabel or blank it.
3. Did any valuation use adjusted prices directly? If yes, discard and use `daily_basic` or `daily_raw`.
4. Are units correct, especially Tushare `total_mv`? It is ten-thousand yuan, not yuan.
5. Are missing values honest? Do not replace missing `PE(2026E)` with an inferred value.
6. Did the analysis confuse size with valuation? Keep `市值` deviation separate from composite valuation.
7. Are fewer than 3 valuation multiples available for a row? If yes, mark the row as insufficient instead of cheap/expensive.
8. Did the buy index hide missing fields? If yes, lower `DataConfidence` or mark the row insufficient.
9. Is the peer set small or mixed-date? If yes, weaken conclusion language.

## Delivery Pattern

Keep the final answer short and explicit:

- Give the table.
- Add peer medians, relative deviations, and composite premium/discount when comparing companies.
- For buy-index requests, show the PNG image and include the buy-index table plus concise explanations.
- State data source paths and latest row dates.
- State which columns are unavailable locally and why.
- State whether `EV/EBITDA` and `PEG` are strict consensus fields or local historical estimates.
