# STATUS — 当前进度

> 更新:2026-06-02。任何 AI 进来先读 本文件 + [CLAUDE.md](CLAUDE.md);系统设计见 [SPEC.md](SPEC.md)。

## 一句话
阶段 0 已关闭:数据基础设施 + 统一 `core/` 回测内核 + 两层台账已建,旧 `data_full/data` 已清理。当前进入**阶段 1 多目标工厂化**;在册母策略仅 `small-cap-size`,真实成本口径未达项目级目标。

## 各层状态
| 层 | 状态 | 说明 |
|----|------|------|
| 数据基础设施 | ✅ | data_lake 全市场+全历史+含退市股,质量 ~99.9%;旧 data_full/data 已删 |
| 统一回测内核 `core/` | ✅ | data_lake + 小盘因子/择时 + 真实换手成本 + 融资成本 |
| 策略工厂 | ⏳ | 阶段 1.1 最小骨架;阶段 1.2 网格;阶段 1.3 NSGA-II;阶段 1.4 生态位;阶段 1.5 审计+孵化池;阶段 1.6 岛屿;阶段 1.7 扩价量因子池;阶段 1.8 孵化池校准;阶段 1.9 fundamental 正交因子池;阶段 1.10 fundamental 岛屿长跑;阶段 1.11 fundamental 因子工程升级;阶段 1.12 工程化 fundamental 岛屿;阶段 1.13 孵化池自进化;候选验收未达 |
| 有效策略管理 | ✅台账 / ○监控 | 两层台账已建;失效信号还是文本、无定量阈值 |
| 中央调度层 | ⏳ | 已新增 launchd 定时增量更新/周维护入口;更完整事件驱动调度未建 |
| 组合层 | ○ | 未建 |
| 展示层 | ○ | 未建 |

## 在册策略(详见 `strategy_versions.json`)
- `small-cap-size / v2.0`(data_lake 2018-2026,真实成本):年化 **21.2%** / 回撤 **-16.2%** / 夏普 1.22 → **已达项目级满意线**(年化≥20% & 夏普≥1.0),未达卓越线(28% 或卡玛 1.6);status=在册。
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
- 已完成 1.9:接入 `fundamental_batch.parquet` 的 quality/growth/value 正交因子池,新增 `fundamental_quality` / `fundamental_value` / `orthogonal_fundamental` niche 和 fundamental 岛屿。
- 已完成 1.10:fundamental 三岛长跑,`review=11` / `registry_precheck=0` / `incubate=11`;弱 alpha 集中在 `fund_bp_value`,但收益、回撤和相关性均未达母策略预审。
- 已完成 1.11:fundamental 因子工程升级,新增行业内排名、行业中性、财务变化率、估值分位和质量+价值 regime 因子,并新增对应 niche/island。
- 已完成 1.12:工程化 fundamental 四岛并发长跑,`review=24` / `registry_precheck=0` / `incubate=23`;最好候选接近 15% 年化但压力回撤失控。
- 已完成 1.13:新增 `factory/evolve_incubation.py` 孵化池自进化程序,从孵化池读取候选,按代做本地规则化变异→三段审计→幸存者选择→继续进化;不调用 OpenAI API。
- 已完成 ops:新增 `scripts/ops/scheduled_daily_update.py`、周维护入口和 launchd plist;每日更新先过 stale gate,避免旧数据覆盖信号状态。
- 已完成 1.14:独立择时验证(`factory/timing.py` 13 个全市场 regime/vol-target/止损基因 × 9 fundamental/defensive 候选 = 117 组合)→ **0 过三道闸**。择时能把相关压到 0.3-0.4,但救不了 fundamental 的结构性压力回撤(与全市场 regime 不同步,`mkt_dd_stop` 止损反而双杀)。**结论:fundamental/defensive 转组合分散件定位(非独立母策略),`timing.py` 作可复用资产保留;找第 2 个母策略需换思路——找本身回撤就可控的正交 alpha**(详见 LESSONS)。
- 当前结论:`candidate_batch.json` 仍为空;**尚未满足 ≥2 个非 small-cap 低相关候选母策略**。
- 下一焦点:用 1.12 的 `incubation_pool.json` 跑自进化,定向优化 `fund_profit_growth_delta`、行业 BP 价值和估值分位组合;`debt_ratio` 和两融因子需等批量数据稳定落表后再接。
