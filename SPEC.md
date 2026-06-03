# SPEC — 系统规格与架构

> 系统"应该长成什么样"。操作约定见 [CLAUDE.md](CLAUDE.md),当前进度见 [STATUS.md](STATUS.md)。

## 目标与哲学
- 真正的资产 = 数据基础设施 + 自进化发现(策略工厂)+ 策略生命周期管理。
- 具体策略是易逝品,**默认会失效**;不追求单一永久达标策略,而是 工厂持续产出 → 管理层持续汰换 → 组合分散衰减。
- 门槛两层:单母策略入册 15%/20%;项目级(组合后)35%/15%。

## 架构(自下而上;✅已建 / ⏳进行中 / ○未建)
1. **数据基础设施** `data_lake` ✅ — 全市场+全历史+含退市股的最全口径。
2. **统一回测内核** `core/` ✅ — `data_lake` 加载 + 因子/择时 + 真实买卖成本 + 融资成本 + 指标,作为生产与研究单一事实源。
3. **策略工厂** ⏳ — 已建确定性网格、最小 NSGA-II、生态位搜索、review audit、孵化池、岛屿编排、扩展非小盘价量因子池、fundamental 正交因子池、fundamental 因子工程升级和孵化池自进化;下一步围绕弱候选做本地规则化持续进化 + 自动证伪(过拟合/幸存者偏差/特定行情);**按母策略隔离进化(岛屿模型,见下「防同质化」)**。当前小规模搜索尚未产出 ≥2 个通过预审的非 small-cap 低相关候选。
4. **有效策略管理** ✅台账 / ○监控 — 母策略两层台账,跟踪 有效/衰减/退役。
5. **中央调度层** ⏳ — 最小 launchd 定时拉取已建;event-driven 编排待建:数据就绪 / 市场状态切换 / 失效信号触发 → 启动或停用 对应母策略/组合。
6. **组合层** ○ — 从「有效」母策略组合(低相关加权 / 轮换,机制待定)。
7. **展示层** ○ — 向用户展示各策略/组合的收益与对比。

- 核心循环:工厂产出 → 管理层汰换 → **只有「有效」策略才进组合与展示**。
- ⚠ 依赖顺序:组合/展示的收益必须建在 `core/` 真实成本口径上;旧 `data_full/data` 已清理,不得恢复为主线。

## 数据层设计
- **口径**:全市场+全历史+含退市股(`data_lake`);估值用不复权价、财务按公告日对齐(防未来函数)。
- **增量更新** ✅:`scripts/data/update_lake.py::update_prices()`,集成于 `run_daily.py` 第①步。
- **维护** ✅:`scripts/data/build_*`(建湖/财务/ST历史)、`scripts/repair/*`(日历/坏值修复)、`validate_final.py`(质量校验 ~99.9%)。
- **数据源** `lake/sources/`:tencent(主力后复权)、sina、em_fin(东财批量财务 `yjbb_em`)、exchange(两融)。
- **fundamental 因子池**:策略工厂使用 `fundamental_batch.parquet` 的 ROE、毛利率、经营现金流、收入/利润增速、EPS TTM、BPS、industry,按 `avail_date` 对齐;价值类收益率因子用不复权价计算,避免复权价估值量纲错误。工程化因子包括行业内排名、行业中性残差、财务变化率、估值时间分位、质量+价值 regime 过滤。
- **调度** ⏳:`scripts/ops/scheduled_daily_update.py` 每日盘后执行价量/财务增量 + stale gate + 信号生成;`scripts/ops/scheduled_weekly_maintenance.py` 做周/月线、不复权价、完整质量校验。完整事件驱动仍归入中央调度层。

## 母策略台账 schema(两层,`strategy_registry.py`)
- **母策略 family**:`id / name / hypothesis / regime / decay_signal / status`(active·paused·retired)
- **版本 version**:`version / desc / config / data_scope(源·区间·幸存者偏差) / metrics / status / notes`(版本 status:候选·在册·退役·参考)
- 数据口径是**版本属性**,不占版本号语义。API:`register_family()` 声明母策略 → `register()` 挂版本。

## 防同质化(逼出低相关母策略,三层)
- **岛屿隔离**(过程层):各母策略独立种群 / 输出目录 / 可选 git worktree,互不污染。**生态位差异化**(不同数据源/因子族/regime)是低相关的根 —— 隔离本身只防污染,不保证结果低相关。岛间不迁因子基因,只共享方法。
- **NSGA 多目标**(岛内层):多头 NDCG@k + 时序稳定 + 真实绩效,不退化成单目标。
- **review audit**(候选层):`*_review.json` 入围后必须过 2018/2023/2010 三段复测 + 成本上浮敏感性,再进入台账预审;未过预审但低相关/有逻辑/局部有效的候选进入孵化池,不得直接入册。
- **incubation evolution**(孵化层):`factory/evolve_incubation.py` 从孵化池候选出发,本地规则化变异参数/因子/权重,每代都重新走 review audit,只把 `registry_precheck=true` 输出到候选批。该程序不调用 LLM/OpenAI API,避免把本地长跑与模型限流混淆。
- **VIF + 逻辑闸**(入册层):跨策略收益 VIF 低相关 + `hypothesis` 逻辑独立。

## 成本模型
见 CLAUDE.md「交易成本」表。代码默认 `CostModel`:买 0.225% / 卖 0.275% / 融资 6.5%;佣金/融资可谈,冲击滑点维持审慎不乐观化。
