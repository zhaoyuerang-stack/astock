# ROADMAP — 实战路线图

> 完整分阶段计划(去哪、分几步)。当前在哪 → [STATUS.md](STATUS.md);为什么这么设计 → [SPEC.md](SPEC.md)。
> 原则:先夯地基再上花活;一切在真实口径下证伪;追求低相关多母策略而非单一最优;可解释优先于黑箱。

## 阶段 0 — 工程地基 ✅(已关闭)
| # | 动作 | 要点 |
|---|------|------|
| 1 | **git 化** | ✅ 已在 `main` 初始化;数据湖和运行产物走 `.gitignore`。 |
| 2 | **统一回测内核** | ✅ `core/backtest.py`;`strategy_lake` / `run_daily` / `simulate_2025` / `cost_sensitivity` 统一走 data_lake + 真实成本。 |
| 3 | **evolve 真实化** | ✅ 旧 `evolve.py` 移除主线;旧口径 `data_full+data` 约 513M 已清理;后续工厂从 `core/` 重建。 |

**验收**:同配置真实成本后落到 v2.0 年化约 21.2% / 回撤 -16.2%;三套回测归一;旧数据清理完成。

## 阶段 1 — 工厂化:多目标产出多母策略 ⭐(当前焦点)
- ✅ 1.1 最小骨架:`factory/` 候选空间 + 多目标评估 + Pareto 排序。
- ✅ 1.2 批量扫描:`factory/run_factory.py --mode grid` 确定性候选网格 + 基础质量门槛 + Pareto 前沿报告。
- ✅ 1.3 最小 NSGA-II:`factory/run_factory.py --mode nsga2` 支持种群、代数、变异率、随机种子和 generation history。
- ✅ 1.4 生态位搜索:`--niche non_size/reversal_liquidity/quality_location` + `*_review.json` 复核清单,避免只产出 small-cap 变体。
- ✅ 1.5 复核审计 + 孵化池:`factory/review_shortlist.py` 对 shortlist 做 2018/2023/2010 三段复测 + 成本上浮敏感性 + 台账预审/孵化标记。
- ✅ 1.6 岛屿编排:`factory/run_islands.py` 每岛独立 niche/seed/种群/输出,可选 git worktree;只聚合 `registry_precheck=true`。
- ✅ 1.7 扩因子池:新增流动性冷却/低 beta/波动压缩/趋势稳定因子,新增 defensive/trend 岛,扩大低换手 top_n/rebalance 搜索空间。
- 输出 **Pareto 前沿 = `reports/islands/candidate_batch.json` 候选母策略批**;弱候选进入 `reports/islands/incubation_pool.json`,不直接入册。
- **隔离进化(岛屿模型)**:每个母策略独立种群 / 可选 git worktree,生态位差异化(不同数据源/因子族/regime);岛间不迁因子基因,只共享方法。
- **验收**:≥2 个逻辑不同、收益低相关的候选母策略(非 small-cap 变体)。当前小规模搜索未满足;孵化池已有弱候选,需继续降频/组合贡献/正交数据源。

## 阶段 2 — 有效管理:入册闸 + 失效监控
- **三道入册闸**:绝对门槛(15%/20%)+ VIF 收益低相关 + `hypothesis` 逻辑独立。
- **失效监控**:`decay_signal` 定量化 + 滚动绩效跟踪 → 自动衰减预警/退役;衰减未死的用近期数据再校准。
- **验收**:台账自动吐「当前有效母策略」+ 衰减预警。

## 阶段 3 — 应用:组合 → 展示 → 调度
- **组合层**:有效母策略 regime-aware 动态加权,冲项目级 35%/15%。
- **展示层**:真实(扣成本)收益看板;受众(投资者/内部)定了再设计。
- **中央调度层**:数据事件 → 启停策略/组合 + 定时拉取。

## 阶段 4 — 远期增强(有触发条件才做)
- LLM 当进化算子(补「逻辑独立」判定)。
- 新正交数据源母策略(两融已有 / 北向 / 新闻情绪;先不上 FinBERT/GNN)。
- GPU 张量化(多目标算力成瓶颈时)。
