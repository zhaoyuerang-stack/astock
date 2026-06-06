# STATUS — 当前进度

> 更新:2026-06-06。任何 AI 进来先读 本文件 + [CLAUDE.md](CLAUDE.md);系统设计见 [SPEC.md](SPEC.md)。

## 一句话
阶段 0 已关闭。**2026-06-06 重大升级**:Pure Trend tw=2 overlay 经三段回测验证后注册为 `small-cap-size/v2.2`(年化50.5%/夏普3.80/回撤-6.2%,全面超越v2.0);生产代码(`run_daily.py`)已同步集成。

## 各层状态
| 层 | 状态 | 说明 |
|----|------|------|
| 数据基础设施 | ✅ | data_lake 全市场+全历史+含退市股,质量 ~99.9%;旧 data_full/data 已删;两融已落 `data_lake/capital/margin_all.parquet`;北向 fallback 已落 `data_lake/capital/northbound_all.parquet`(2017-2024,774只)。**2026-06-05 标准化修**:①`update_raw_prices()` 更新逐只后补调 `compact_raw_prices` 重建大表(日增量/全量两处);②`merge_northbound()` 输出改 `northbound_daily_all.parquet`,防覆盖 `merge_northbound_stock()` 构建的正确大表 |
| 统一回测内核 `core/` | ✅ | `core/engine.BacktestEngine` 统一接口已落地;`core/backtest.py` 核心逻辑内部走 engine,旧函数标记 deprecated;`amount=volume×100×不复权价` |
| 策略工厂 | ⏳ | 阶段 1.1-1.13 已建;2026-06-03 已按干净 amount + 2010 预热重跑 fundamental 1.9-1.13;2026-06-04 已接两融/北向资金面并验证;候选验收仍未达 |
| 有效策略管理 | ✅台账 / ✅监控 / ✅模拟盘 | 两层台账已建;失效监控 `decay_monitor` 把 decay_signal 定量化(size因子IC衰减/小盘动量/滚动夏普 + 前瞻阈值,当前 v2.0 🔴预警);实盘就绪卡 `live_readiness`(操作+容量+失效);**模拟盘 `scripts/ops/paper_trade.py`=真实盘口径:T+1 不复权开盘价成交 + pending order 跨天结算 + 停牌/一字涨跌停不可成交;100万本金/1.0x,写 Obsidian `30.output/A股v2.0模拟盘/`,`--preview` 出次日开盘建仓清单。回测口径(收盘撮合)不动** |
| 中央调度层 | ⏳ | launchd 每日增量更新已接 `paper_trade`;周维护已接 `decay_monitor`/`tradability`/`live_readiness`;更完整事件驱动调度未建 |
| 组合层 | ○ | 未建 |
| 展示层 | ○ | 未建 |

## 在册策略(详见 `strategy_versions.json`)
- `small-cap-size / v2.2`(2026-06-06,**当前生产版本**):MA16 × PureTrend(tw=2) overlay — IS 年化 **50.5%** / 回撤 **-6.2%** / 夏普 **3.80** / 卡玛 8.11;OOS 53.0%/3.56/-6.2%;压力 70.3%/4.22/-8.0% → **达卓越线**;WF 12年100%选tw=2,OOS≈IS无过拟合。⚠️T+1真实执行打折约6-10%。
- v2.0(MA16 alone,干净口径):年化22.2%/夏普1.38/回撤-20.0% → 参考(已被v2.2超越)。
- v1.0(data_full,幸存者偏差)→ 参考;v2.1(压力测试参考)→ 参考。

## 回测平台标准化(2026-06-05)

**状态:已完成。** 统一接口 `core/engine.BacktestEngine` 已落地,所有主流程已迁移:

| 模块 | 状态 |
|------|------|
| `core/engine.py` 统一接口层 | ✅ `BacktestEngine`/`Signal`/`BacktestResult`/`PricePanel` |
| `strategy_lake.py` | ✅ 已迁移到 engine |
| `run_daily.py` 生产入口 | ✅ 已迁移到 engine |
| `factory/evaluator.py` 工厂主入口 | ✅ `evaluate_candidates()` 走 engine;`prepare_context()` 内部 benchmark 走 engine |
| `engine/backtest.py` → `factor_analysis.py` | ✅ 重命名,职责清晰(IC/分层) |
| `engine/portfolio.py` + `composer.py` | ✅ 接入 `to_signal()` 桥接;独立回测逻辑 deprecated |
| 兼容层 | ⚠️ `core/backtest.py`(backtest_weights)/`factory/evaluator.py`(run_candidate_returns等)/`engine/portfolio.py`(top_n_portfolio) 标记 deprecated,保留至调用方迁移完成 |
| 文档 | ✅ `factor_research/docs/engine_usage.md` |
| 测试 | ✅ `test_engine.py` 6项回归测试全部通过 |
| 数值漂移 | ✅ 零漂移:strategy_lake/run_daily/factory baseline/registry 全部验证一致 |
| **hit 阈值对齐(2026-06-05修)** | ✅ `engine/metrics.py` TARGET_ANNUAL/MAXDD 从旧 35%/15%(data_full 水分已退役)更新为 15%/20%;`BacktestConfig` 默认阈值同步;`BacktestResult.hit` @property 修 Python 参数 bug(伪参数不生效);边界改用严格 `>`/`<` 与 `factory/objectives.py` 一致 |

## 当前阶段
**阶段 1 — 多目标策略工厂化**。完整路线见 [ROADMAP.md](ROADMAP.md)。
- 已完成 1.1: `factory/` 最小策略工厂骨架,可评估候选并输出 `reports/factory_stage1_1.json`。
- 已完成 1.2: `factory/run_factory.py --mode grid` 可做确定性批量扫描,输出 `reports/factory_stage1_2.json`;Pareto 先过正收益/正 Sharpe/回撤/OOS 基础门槛。
- 已完成 1.3: `factory/run_factory.py --mode nsga2` 可跑最小 NSGA-II 多目标搜索,输出 `reports/factory_stage1_3.json` 和 generation history。
- 已完成 1.4: `--niche non_size/reversal_liquidity/quality_location` 支持生态位搜索,并输出 `*_review.json` 复核清单。
- 已完成 1.5: `factory/review_shortlist.py` 可对 review shortlist 做 2018/2023/2010 三段复测 + 成本上浮 50% 敏感性 + `registry_precheck`;同时标注 `incubate` 弱候选。
- 当前结论:`reports/factory_stage1_5_non_size_audit.json` 中 8 个 non-size 小样本候选均未通过台账预审,主要败在压力回撤和成本上浮。
- 已完成 1.6: `factory/run_islands.py` 可跑隔离岛屿,每岛独立 niche/seed/种群/输出,汇总 `registry_precheck=true` 为 `reports/islands/candidate_batch.json`,汇总 `incubate=true` 为 `reports/islands/incubation_pool.json`。
- 已完成 1.7:扩展非 small-cap 因子池(流动性冷却/低 beta/波动压缩/趋势稳定),新增 `defensive_liquidity` / `trend_quality` 生态位,并扩大 top_n/rebalance 低换手搜索空间。
- 已完成 1.8:孵化池候选降杠杆/降频/组合贡献测试,`registry_precheck=0`;低相关弱候选仍只能留在孵化池。
- 已完成 1.9:接入 `fundamental_batch.parquet` 的 quality/growth/value 正交因子池,新增 `fundamental_quality` / `fundamental_value` / `orthogonal_fundamental` niche 和 fundamental 岛屿;2026-06-03 已用干净 amount + 2010 预热重跑 NSGA clean reports:7 个 fundamental niche 共审计 46 个 review 候选,`registry_precheck=0`,`incubate=46`。
- 已完成 1.10:fundamental 三岛长跑已按干净 amount + 预热重跑,`review=13` / `registry_precheck=0` / `incubate=13`;弱 alpha 仍集中在 BP/value 与少量 growth,但收益/回撤未达母策略预审。
- 已完成 1.11:fundamental 因子工程升级,新增行业内排名、行业中性、财务变化率、估值分位和质量+价值 regime 因子,并新增对应 niche/island。
- 已完成 1.12:工程化 fundamental 四岛已按干净 amount + 预热重跑,`review=40` / `registry_precheck=0` / `incubate=40`;`reports/islands_fundamental_1_12_parallel/candidate_batch.json` 为空,`incubation_pool.json` 有 40 个分散件候选。最好单候选约 13.6% 年化 / -20.9% 回撤,仍卡在入册线;直接组合测试 15 组中 6 组过 `combo_precheck`,作为组合路线材料而非独立母策略。
- 已完成 1.13:`factory/evolve_incubation.py` 已用新 1.12 孵化池重跑 3 代 × 12 候选,`evaluated=36` / `registry_precheck=0` / `incubate=36` / `acceptance=false`;最强变体可到 15.9% 年化,但回撤 -26.0%,仍不能入册。
- 已完成 1.15:补两融资金面正交数据,`data_lake/capital/margin_all.parquet` 覆盖 2010-03-31~2026-06-03、634万行;新增 `margin_flow`/`capital_flow` 因子族并按 T+1 可用防未来函数。验证结果:`reports/capital_margin_flow.json` 在 corr<0.5 闸下 review=0;`reports/capital_margin_flow_audit.json` 审计 22 个候选 `registry_precheck=0`;确定性 `reports/capital_margin_grid.json` 168 个候选 `hit_single=0`,最佳约 10.3% 年化 / -31.4% 回撤 / corr 0.76。北向个股源已接代码,但 Eastmoney 当前返回 9701/None,未能落完整表。
- 已完成 1.16:补北向持股历史 fallback。东财每日批量接口仍返回 9701/None,改用 `stock_hsgt_individual_em` 对 top1000 高流动性股票低并发拉单股完整历史,成功 774 只,`data_lake/capital/northbound_all.parquet` 675,072 行,覆盖 2017-03-16~2024-08-16。已接持股占比/市值/变化/净买入强度因子并按 T+1 防未来函数。正确验证窗口切到 2018~2024-08:345 个北向候选 `review=0` / `hit_single=0`,最佳约 0.7% 年化 / -28.3% 回撤 / corr 0.57;低相关组合 corr~0.47 但收益为负且回撤大;top30 audit `registry_precheck=0`。详见 `reports/northbound_validation_summary.json`。
- 已完成 ops:新增 `scripts/ops/scheduled_daily_update.py`、周维护入口和 launchd plist;每日更新先过 stale gate,避免旧数据覆盖信号状态。
- 已完成 1.14:独立择时验证(`factory/timing.py` 13 个全市场 regime/vol-target/止损基因 × 9 fundamental/defensive 候选 = 117 组合)→ **0 过三道闸**。择时能把相关压到 0.3-0.4,但救不了 fundamental 的结构性压力回撤(与全市场 regime 不同步,`mkt_dd_stop` 止损反而双杀)。**结论:fundamental/defensive 转组合分散件定位(非独立母策略),`timing.py` 作可复用资产保留;找第 2 个母策略需换思路——找本身回撤就可控的正交 alpha**(详见 LESSONS)。
- 当前结论:`candidate_batch.json` 仍为空;**尚未满足 ≥2 个非 small-cap 低相关候选母策略**。fundamental 汇总见 `reports/factory_clean_rerun_summary.json`;两融汇总见 `reports/capital_flow_validation_summary.json`;北向汇总见 `reports/northbound_validation_summary.json`。
- 下一焦点:接受当前数据基础下"A股稳定 alpha 主要只有小盘"的现实,把 `small-cap-size/v2.0` 当唯一母策略做实盘化/风控/容量/失效监控;fundamental/两融/北向只保留为组合分散件或监控辅助,不再围绕这些方向硬凑第 2 母策略。
- 已落地 实盘部署(2026-06-04):`scripts/ops/paper_trade.py` 模拟盘(100万本金,1.0x,读当日 signal 模拟成交+真实成本,写 Obsidian `30.output/A股v2.0模拟盘/今日操作.md`+`历史/`,`--preview` 出建仓清单),已接每日 launchd;周维护接入 `decay_monitor`/`tradability`/`live_readiness`。**期间修两个生产 bug**:① 当天数据残缺(不复权 raw 滞后于后复权 daily + 盘后部分抓取)使最新日 `amount` 全 NaN → 选不出 top25、择时值脏,`load_price_panels` 改按 **amount 完整性**截断尾部不完整日;② 模拟盘下单股数误用后复权价(虚高数倍)→ 买 0 股,改用 `daily_raw` 不复权价。详见 LESSONS。
- 已落地 真实盘成交重构(2026-06-05):按"模拟=真实盘"要求,`paper_trade` 改 **T+1 不复权开盘价成交 + pending order + 停牌/一字涨跌停约束**(回测归回测、成交归真实买卖);`fetch_raw_close` 改拉**不复权 OHLC + 增量**,`daily_update` 每日同步 `daily_raw`(raw 滞后已根治)。端到端 6 项验证通过,期间修:涨跌停价须按分 `round(×1.1,2)`(否则 7.403 漏判 7.40 涨停)、卡片字符串中文引号语法错。
- 历史重放验证(2026-06-05):`scripts/research/paper_replay.py` 用真实盘口径重放 2024-2025,整机跑通(64 次调仓/1561 笔成交/受阻 3 笔)。**真实盘 T+1 23.7%/-11.4%/夏普1.29 vs 回测收盘撮合 45.1%/-10.9%/1.97——隔夜跳空摩擦拖累年化 21.4%**,高换手小盘策略回测严重高估、真实执行吃掉一半。补:全量重拉历史不复权 OHLC(增量只补 20 天,回放需全量)。**v2.0 真实盘 T+1 预期已确认(全区间 2018-2026 重放):17.5%/-16.1%/夏普1.19 vs 回测收盘 24.0%/-20.0%/1.41——年化未达满意线 20%,但夏普(1.19≥1.0)、回撤(-16.1%)达标;常态摩擦仅 6.5%(2024-2025 腰斩是小盘大年极端)。在册回测口径数字不变,但真实盘预期以此为准:合格但不惊艳。**
