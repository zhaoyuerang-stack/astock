# Storyboard

**Format:** 1920×1080  
**Audio:** TTS voiceover if available; captions and light interface SFX are built into the visual timeline.  
**VO direction:** calm senior operator, Chinese product demo tone, deliberate pauses, no hype.  
**Style basis:** DESIGN.md, captured Quant Research OS dashboard, and repository data infrastructure docs.

## Asset Audit

| Asset | Type | Assign to Beat | Role |
| --- | --- | --- | --- |
| `capture/screenshots/scroll-000.png` | Product screenshot | Beats 1, 5, 6 | Three-column cockpit proof, framed in perspective |
| `capture/screenshots/scroll-100.png` | Product screenshot | Beat 4 | Fail-closed / blocked state evidence |
| `capture/assets/svgs/logo-2aa74f07.svg` | SVG logo | Beats 1, 6 | Brand mark opener and closer |
| `capture/assets/svgs/logo-cf7c7c59.svg` | SVG logo | Beat 6 | Secondary logo accent if it renders correctly |

## BEAT 1 — DATA FIRST (0.00-10.00s)

**VO:** "一个量化系统，最先该搭的，不是策略页面。是数据地基。如果数据源、字段、时间线和口径没有被管住，任何漂亮回测，都只是幻觉。"

**Concept:** The video opens inside the actual Quant OS cockpit, but the product UI is treated as the end result, not the beginning. The dashboard screenshot tilts backward while a glowing foundation grid assembles underneath it. The viewer should immediately understand the first-principles claim: strategy screens are downstream of data discipline.

**Visual:** Full black canvas with the captured dashboard screenshot framed as a large floating workstation. Under it, blue gridlines draw into a data foundation; red "幻觉风险" strips flicker and then get pinned down by green guard points. Large kinetic headline: "先搭数据地基".

**Techniques:** CSS 3D screenshot frame, SVG path drawing, per-word kinetic typography, deterministic canvas grid.

**Transition:** Velocity-matched upward into the source registry.

## BEAT 2 — REGISTER SOURCES (10.00-20.00s)

**VO:** "Quant OS 的做法很直接：先把数据源注册成可审计接口。谁负责价量，谁负责财务，谁负责停牌、涨跌停、资金流，都写进声明，而不是散落在脚本里。"

**Concept:** Data ingestion is not "more connectors"; it is a registry with declared responsibility. Cards for source systems assemble into a structured source registry, then lock into one manifest spine.

**Visual:** Five source cards slide in: Tushare, Tencent, Akshare, Exchange, Eastmoney. Each card lists dataset duties. A blue route line connects them to `INTERFACES[]`, then a manifest badge stamps "可审计".

**Techniques:** SVG connector drawing, card cascade, terminal typing for `INTERFACES`, counter pulse.

**Transition:** Hard cut on manifest stamp to the data lake stack.

## BEAT 3 — BUILD THE LAKE (20.00-30.00s)

**VO:** "第二步，落成数据湖。原始价、复权价、财务长表、交易日历、股票池和 manifest 分层保存。每次更新，都留下日期、规模、字段和 vintage。"

**Concept:** The lake is an engineered warehouse, not a folder dump. Layers rise from the bottom of the frame, each with a clear contract and a visible write record.

**Visual:** A 3D layered stack: `price/daily_raw`, `price/daily`, `fundamental_batch`, `meta`, `_manifest.json`. Rows and dates stream into each layer, then a green vintage seal is applied.

**Techniques:** CSS 3D stack, flowing particles, manifest typing, green seal animation.

**Transition:** Blue flow spine bends into a PIT lock.

## BEAT 4 — LOCK TIME (30.00-40.00s)

**VO:** "第三步，是防未来。财务按公告日对齐，盘后数据统一 shift one day，估值用不复权价格。T 日信号，只能看到 T 日之前已经公开的东西。"

**Concept:** The timeline becomes the main character. A vertical red holdout wall prevents future information from leaking backward; records that arrive too late bounce off until their public date.

**Visual:** A horizontal date rail with T-2, T-1, T, T+1. Financial announcement packets land on `avail_date`; moneyflow packets shift from T to T+1; valuation uses `raw_close` while adjusted price is marked for returns only.

**Techniques:** Timeline rail, SVG lock path, token packets, red leak-block animation.

**Transition:** Blur-through into guard board.

## BEAT 5 — MACHINE GUARDS (40.00-50.00s)

**VO:** "第四步，是质量闸门。极端跳变、负价格、OHLC 不一致、旧缓存读取、非法写湖入口，都先被机器拦住。系统宁可显示 blocked，也不假装 ready。"

**Concept:** The captured blocked dashboard is reframed as a strength: the system refuses to fake readiness. Guard cards run one by one, catching concrete failure modes.

**Visual:** The screenshot slides behind a row of guard cards: `validate_final.py`, `check_no_legacy_data.py`, `check_lake_writers.py`, `check_layer_deps.py`. Red risks are stamped BLOCKED; green checks are stamped PASS where the method is valid.

**Techniques:** Product screenshot parallax, guard-card cascade, red stamp, status pulses.

**Transition:** Upward flow to the service layer.

## BEAT 6 — ONE FACT SOURCE (50.00-60.00s)

**VO:** "最后，所有研究和前端，只能走统一加载层。因子、回测、九门禁、模拟盘和工作台，读的是同一份事实源。所以，这不是“接几个数据接口”。这是一个可复测、可审计、可替换的数据基础设施搭建方法：注册源，沉淀湖，锁时间，跑守卫，再服务研究。"

**Concept:** The method closes as an operating recipe. One source of truth fans out to research, backtest, gates, and web, then collapses into a five-step checklist.

**Visual:** A central `lake/load_lake.py` node fans out to `factors`, `BacktestEngine`, `9-Gate`, `run_daily`, and `web`. The final checklist appears: 注册源 / 沉淀湖 / 锁时间 / 跑守卫 / 服务研究. Logo and product name settle in the final frame.

**Techniques:** Radial graph, SVG fan-out, checklist reveal, product screenshot mini-card, logo close.

**Transition:** End hold for 1.5s.

## Production Architecture

```
prototypes/data-infra-promo/
├── index.html
├── DESIGN.md
├── SCRIPT.md
├── STORYBOARD.md
├── narration.txt
├── transcript.json
├── capture/
│   ├── screenshots/
│   ├── assets/
│   └── extracted/
└── compositions/
    ├── scene-1-data-first.html
    ├── scene-2-source-registry.html
    ├── scene-3-data-lake.html
    ├── scene-4-pit-lock.html
    ├── scene-5-guards.html
    └── scene-6-method.html
```
