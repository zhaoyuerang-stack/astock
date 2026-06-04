# STATUS — 当前进度

> 更新:2026-06-03。任何 AI 进来先读 本文件 + [CLAUDE.md](CLAUDE.md);系统设计见 [SPEC.md](SPEC.md)。

## 一句话
阶段 0 已关闭:数据基础设施 + 统一 `core/` 回测内核 + 两层台账已建,旧 `data_full/data` 已清理。当前处于**阶段 1 多目标工厂化复验后**;在册母策略仅 `small-cap-size`,factory 已用干净 amount + 2010 预热重跑 fundamental 和两融资金面,仍未产出合格新母策略。

## 各层状态
| 层 | 状态 | 说明 |
|----|------|------|
| 数据基础设施 | ✅ | data_lake 全市场+全历史+含退市股,质量 ~99.9%;旧 data_full/data 已删;两融已落 `data_lake/capital/margin_all.parquet`,北向个股源当前被 Eastmoney/代理阻断 |
| 统一回测内核 `core/` | ✅ | data_lake + 小盘因子/择时 + 真实换手成本 + 融资成本;`amount=volume×100×不复权价` |
| 策略工厂 | ⏳ | 阶段 1.1-1.13 已建;2026-06-03 已按干净 amount + 2010 预热重跑 fundamental 1.9-1.13;2026-06-04 已接两融资金面并验证;候选验收仍未达 |
| 有效策略管理 | ✅台账 / ○监控 | 两层台账已建;失效信号还是文本、无定量阈值 |
| 中央调度层 | ⏳ | 已新增 launchd 定时增量更新/周维护入口;更完整事件驱动调度未建 |
| 组合层 | ○ | 未建 |
| 展示层 | ○ | 未建 |

## 在册策略(详见 `strategy_versions.json`)
- `small-cap-size / v2.0`(data_lake 2018-2026,干净 amount + 2010 预热 + 真实成本):年化 **22.2%** / 回撤 **-20.0%** / 夏普 **1.38** / 卡玛 1.11 → **已达项目级满意线**(年化≥20% & 夏普≥1.0),未达卓越线(28% 或卡玛 1.6);status=在册。
- v1.0(data_full)幸存者偏差水分 → 参考;v2.1 全历史压力测试 → 参考。

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
- 已完成 ops:新增 `scripts/ops/scheduled_daily_update.py`、周维护入口和 launchd plist;每日更新先过 stale gate,避免旧数据覆盖信号状态。
- 已完成 1.14:独立择时验证(`factory/timing.py` 13 个全市场 regime/vol-target/止损基因 × 9 fundamental/defensive 候选 = 117 组合)→ **0 过三道闸**。择时能把相关压到 0.3-0.4,但救不了 fundamental 的结构性压力回撤(与全市场 regime 不同步,`mkt_dd_stop` 止损反而双杀)。**结论:fundamental/defensive 转组合分散件定位(非独立母策略),`timing.py` 作可复用资产保留;找第 2 个母策略需换思路——找本身回撤就可控的正交 alpha**(详见 LESSONS)。
- 当前结论:`candidate_batch.json` 仍为空;**尚未满足 ≥2 个非 small-cap 低相关候选母策略**。fundamental 汇总见 `reports/factory_clean_rerun_summary.json`;资金面汇总见 `reports/capital_flow_validation_summary.json`。
- 下一焦点:fundamental 和两融都只保留为组合/孵化材料;若要继续找第 2 个母策略,先修北向 Eastmoney 直连并补完整北向持股历史,否则需要接受当前数据基础下"A股稳定 alpha 主要只有小盘"的现实。
