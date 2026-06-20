# DECISIONS — 决策文档

> 三节:① 决策框架(怎么做新决策)② 架构/研究决策记录 ADR(过去的 why,append-only)③ 投资/交易决策(指向 signals/ + 复盘)。
> 与 [CLAUDE.md](CLAUDE.md)(宪法)、[STATUS.md](STATUS.md)(进度)、[LESSONS.md](LESSONS.md)(坑)互补——这里记**为什么这么决策**。

---

## ① 决策框架(playbook:怎么做新决策)

> 不重抄别处的事实——只给本文唯一增量(决策前必问)+ 指针。
- **优先级排序**(冲突时)、**门槛/满意线/卓越线数字**、**各铁律** → 见 [CLAUDE.md](CLAUDE.md)。
- **研究→入册→LIVE→退役 生命周期 + 各步谁干 + 各闸门** → 见 [WORKFLOW.md](WORKFLOW.md) #1。

**决策前必问(本节唯一增量)**:
1. 过拟合 / 幸存者偏差 / 特定行情依赖?
2. 真实成本扣了吗(往返≈0.47% + 融资)?
3. 实盘可交易吗(容量 / 停牌 / 涨跌停 / 投资者门槛)?
4. 判断在代码还是在 LLM?**必须代码**。

---

## ② 架构/研究决策记录(ADR,append-only)

> 格式:上下文 / 决策 / 备选(为何否决)/ 复审信号。新决策往下加,不改旧的(超越则标 superseded)。

### ADR-001 口径 = data_lake + core/,绝不 data_full
- **上下文**:data_full 旧缓存只含沪市主板,有幸存者偏差水分(~40%)。
- **决策**:全市场口径以 data_lake + core 统一内核为准;门槛锚定真实口径(原 35%/15% 退役)。
- **复审**:口径若再变,门槛同步重锚。

### ADR-002 按母策略组织 + 默认会失效
- **决策**:策略按独立 alpha 家族(母策略)组织,持续 发现→证伪→替换;任何策略默认会失效。
- **理由**:单一策略必衰减;真资产是 数据+工厂+有效策略管理,不是某条曲线。

### ADR-003 LIVE 日信号 = illiquidity v3.1(非小盘)
- **上下文**:小盘与 illiquidity 都吃量价。
- **决策**:LIVE 日信号用 illiquidity(Amihud)+ Salience Veto + Band timing。
- **理由(2026-06-14 外部坐实)**:CNE6 风格中性化下,小盘=纯 size 押注(相关 -0.70,残差可忽略),**唯 illiquidity 有真特质 alpha**(+0.017 REAL)。
- **复审**:若 illiquidity 特质增量消失,或更优特质信号出现。

### ADR-004 真实成本固化(禁乐观值)
- **决策**:`core/backtest.py::CostModel` 固化 买 0.225%/卖 0.275%/融资 6.5%(往返≈0.47%+融资);冲击 0.2% 不下调。
- **复审**:费率变动须同步台账备注。

### ADR-005 tushare 付费 over akshare 免费
- **上下文**:无市值/股本 → 建不了干净 Barra Size,small_cap 自循环无法证伪;akshare 东财被代理拦、逐只封禁。
- **决策**:付费 tushare(2000 积分),取真市值/换手/财务。
- **理由**:真市值破除 small_cap 自循环审计(代理版半定义性 + 高估 illiquidity edge 一倍);一次回填补齐市值/换手/估值/杠杆/质量/成长多维。
- **复审**:积分/成本与数据价值再权衡;5000 积分可解锁 vip 按期批量。

### ADR-006 科创板从小盘 universe 排除
- **上下文**:688 amount bug 修复后会选入小盘。
- **决策**:`exclude_star=True` 默认排除。
- **备选**:纳入(+0.3pp 但降夏普 1.85→1.65);保持 bug 隐式排除(不诚实)。
- **理由**:纳入≈零 alpha + 降夏普;50万门槛/20cm 实盘不可交易。
- **复审**:若做 50万+ 账户专用组合,或 688 流动性结构变化。

### ADR-007 便宜模型干苦力,判断归确定性代码
- **决策(规则)**:见 CLAUDE「LLM 分工铁律」。
- **理由**:苦力的错被代码廉价筛掉(实测 1/5 漏斗);判断的错代价高,留代码/强模型。判断交 LLM = 毁证伪体系。
- **复审**:便宜模型可信到能做判断时(目前不信)。

### ADR-008 多 agent 按「时间形态×可用性」分工
- **决策(规则)**:见 [MULTI_AGENT.md](MULTI_AGENT.md)。
- **理由**:订阅有额度限制,常驻依赖订阅 agent = 到期停摆;判断恒为代码不随 agent 变。

### ADR-010 文档矩阵 = 单一真相源(每个事实一个家)
- **决策**:每个事实只有一个 home,其余文档**链接不重抄**。home 映射:规则/铁律/门槛/优先级→CLAUDE;静态架构/schema→SPEC;端到端流程(谁干每步)→WORKFLOW;agent 分工→MULTI_AGENT;决策理由→DECISIONS(本文 ADR);进度→STATUS;**开放任务 backlog→TASKS**;坑→LESSONS;每日操作→RUNBOOK;数据层细节→docs/data_infrastructure.md;**评价指标定义/状态机/准入流程**→`factor_research/docs/strategy_evaluation.md`;**本体层/命名术语映射**→`factor_research/docs/ontology_glossary.md`。
- **备选**:每文档自洽全抄(读着方便)——否决,内容耦合改一处忘另一处即矛盾(文档版未来函数)。
- **复审**:新增文档前先确认它占一个**无主的轴**,否则并入现有。

### ADR-009 防未来两口径,按数据集声明
- **决策**:价格衍生当日量(市值/换手/资金流)对齐交易日**不 shift**(T 日收盘已知);财务/事件按 **ann_date 公告日 ffill**(T 日只用已公告)。口径写进 `TUSHARE_DATASETS` 注册表,加维度强制声明。
- **理由**:混用任一口径引入前瞻或丢信息。

### ADR-011 regime 门控(small-cap↔large-cap)默认关闭
- **上下文**:小盘失宠时(PT-MA16 dist_lagged<=0,占比39%)切换到 large-cap v1.1 + 30% 防御腿。equity-only 2018-2026:年化29.7%→34.1%、夏普1.88→2.01,但回撤-15.8%→-19.5%、卡玛1.88→1.75。全样本2010-2026:门控全面优于static(年化+3.9pp/夏普+0.13/卡玛+0.18,回撤亦略好-29.2% vs -30.6%)。
- **决策**:落地为可配置项 `portfolio/regime_gate.py::live_returns(regime_gated=False)`,默认**关闭**;现行 capped 30%(23.3%/2.08/2.05/-11.4%)行为不变。
- **备选**:默认开启——否决,因 2018-2026 局部窗口回撤变差(尾部更肥,深回撤段5次 vs 1次),且 large-cap 独立 edge 弱(夏普-0.02),门控收益来自"借用 large-cap 的条件 edge"而非新增 alpha,是风险偏好选择不是免费午餐。
- **理由**:回撤优先于收益(CLAUDE.md 排序);全样本数据支持但局部窗口的肥尾不确定性足以让默认值保持保守。
- **容量备注**:门控给收益不给容量——受宠期资金仍困在小盘 ~2700万 上限;真要扩容量需纯 large-cap(~8亿,但弱edge)。收益(门控可得)与容量(需纯large-cap)是互斥杠杆。
- **复审**:若小账户(<2700万)且能承受偶发-15~-20%尾部回撤,或 large-cap 独立 edge 改善,可考虑开启。

### ADR-012 本体单一真相源 = factory.ontology;台账正式锚定证据链
- **上下文**:`contracts/models.py` 曾把 `Hypothesis/Experiment/ExperimentResult` 与 `factory.ontology.*` 重复定义(Phase 0 按 SPEC §7 预声明,实际零 import),是"两套语言说同一件事";且 `strategy_registry.register()` 只写 config/metrics/notes,**没有 hypothesis_id、没有促成晋级的 L0-L3 实验 ID**——策略退役后无法机器回溯"当初哪个假设、哪条实验支撑了入册",证据是隐性的(违背"登记纪律"+"默认会失效→可回溯")。
- **决策**:① `Hypothesis/Experiment/ExperimentResult` 运行时本体唯一定义在 `factory.ontology`(内容哈希冻结 dataclass),`contracts.models` 删除这三个重复 DTO 并加指针注释;② 版本登记新增 `evidence={hypothesis_id, experiment_ids}` 字段,`promote.py` 经 `ExperimentLog.list_by_hypothesis(hyp.id)` 回查 L0-L3 实验 ID 锚定到台账。
- **备选**:(a) 删全部 6 个零引用 DTO——否决,`FactorDefinition/Strategy/PortfolioState` 是后续 Phase 待接线的产品 write-schema 占位,删了丢 SPEC 脚手架;(b) 一个不删只加注释——否决,重复定义仍共存,没真正落实单一来源;(c) 把 Hypothesis 也升级为注册实体(胖本体)——否决,当前无 Agent 自动查询需求,违背简单优先。
- **理由**:`contracts.models` 那三个是死镜像(精确核实零 import),删之零风险;证据链是接线工作而非造数据(日志早按 hypothesis_id 归档 389 条,缺的只是登记时回查)。活跃 DTO `AgentOutput/AgentTask/ControlAction` 原地保留。
### ADR-013 不复权原始价(daily_raw)以 Tushare 批量为主,mootdx 逐股降级为辅
- **上下文**:每日运行中,不复权原始价 `daily_raw` 增量拉取耗时在 7~20 分钟以上,阻塞后续结算和信号推送。其根源是依赖 `mootdx` 逐股（5207只）进行串行网络请求。
- **决策**:重构更新算法,使用 Tushare `daily` 接口每个交易日仅 1 次批量拉取全市场原始 OHLC 价格数据，在本地以内存 Pandas `groupby` 拆分合并并增量写入各 parquet 文件，并重建 `daily_raw_all.parquet` 大表；同时将 `mootdx` 逐股串行更新通道作为降级备份（Failover），捕获任何 Tushare 异常自动降级。
- **理由**:将网络请求从 5200+ 次缩减至 1 次，数据更新由 7~20 分钟缩短到秒级（5~10秒），极大改善了盘后结算时效性和系统可靠性。
- **复审**:由于 Tushare `daily` 数据在收盘后（一般15:30-17:00）才可获取，需与交易日历（trade_calendar）更新节奏及 plist 调度时间相匹配。

### ADR-014 Gate 6 冲击成本与容量评估升级为波动率平方根与多日分拆执行模型
- **上下文**:此前 Gate 6 采用简化的线性滑点惩罚模型（0.05 * participation），高 AUM 下大额调仓滑点虚高，直接误杀高换手与中大盘策略（如 500M 规模下 Sharpe 直接因冲击成本暴跌至负），忽视了买方多日拆单的常态。
- **决策**:
  1. 将冲击成本公式升级为非线性平方根模型：$\text{Slippage} = Y \cdot \sigma_i \cdot \sqrt{\text{Participation}_i}$（$Y=1.0$），引入个股滚动 20 日波动率 $\sigma_i$。
  2. 嵌入自适应拆单优化器：对每个交易日的每只股票，在 $N \in [1, 2, 3, 4, 5]$ 中选择最佳拆单天数以最小化 $\text{Cost}(N) = \frac{\text{Slippage}}{\sqrt{N}} + (N - 1) \cdot \text{alpha\_decay}$（每日 Alpha 延迟衰减设为 10 bps）。
- **理由**:
  1. 精准区分小盘与大盘策略的容量：小盘股高 Vol 会在平方根下加重惩罚，卡死其 2000万 容量限制；大中盘股低 Vol + 高 ADV 使得平方根冲击极小，合理释放其亿级大容量特性。
  2. 实盘映射：计算输出的 $N$ 值直接映射为交易台在调仓日的算法拆单参数（如 3 日/5 日分批交易），实现“策略研发与交易执行算法”的直接闭环。
- **复审**:若市场微观结构发生剧烈变化，或者 A 股 tick 规则发生变动。

### ADR-015 行动桌面三大独立看板激活与全站导航重组
- **上下文**: 原有的 `/candidates` 和 `/signals` 页面处于“建设中”状态（ready: false）。交易员需要随时审计策略选出的 25 只因子推荐候选股，并看清底层择时判定与杠杆偏离度的核心数学依据。原来的“股票候选”网格由于缺少页面被塞在“今日总览”页，打破了总览页极简交易台面（Checklist + Today's Signals）的设计原则。
- **决策**:
  1. 激活并独立重构 `/candidates` (股票候选) 页面，无条件显示 25 只策略候选股，在 `BEAR` 行情下显示防御性避险提示，并说明 Veto 过滤机制；
  2. 激活并独立重构 `/signals` (策略信号) 页面，展示小盘均线趋势偏离度、Regime 极性判定、动态杠杆与影子系统对照，提供决策诊断；
  3. 激活并独立重构 `/trade-plans` (交易计划) 页面，支持交易指令审查、交易员电子签名与委托 HASH 锁定、Broker CSV 委托单导出；
  4. 恢复 `overview/page.tsx` 页面使其专注极简交易台面，移除临时的候选股票卡片，保证低噪音决策。
- **理由**: 实现了完整的 Ops Desk 工作流闭环，并在视觉上彻底收敛了交易台面噪音，将复杂的底层数据核算与高密度股票池合理划分到专属页面，确保交易员在开盘决策时能有极低认知负载与极高确定性。

### ADR-016 大中盘非流动性溢价策略 (illiquidity-large-cap v1.0) 晋级登记在册
- **上下文**: 大中盘（Top 800 ADV）中由于套利不充分，流动性短暂枯竭时的非流动性溢价仍然极强。我们设计了 Amihud Illiquidity 因子配合 30% 凸显性风控否决 (Salience Veto) 及 MA16 趋势择时的大容量策略。
- **决策**: 晋级该策略为首个 `"在册"` (APPROVED) 的大中盘单体策略。
- **理由**:
  1. 顺利通过了 9-Gate 完整审计与多重检验测试（DSR p-val = 0.0112，显著性通过）。
  2. 回测满足 `"standalone"` 准入要求：2018-2026 年化收益 58.26%，最大回撤 -17.66%，夏普比率 2.16。
  3. 估计容量达 5.0 亿人民币以上（波动率平方根冲击成本下 5亿 AUM 的净夏普比率仍有 1.74）。
- **失效边界**: 滚动 12 个月夏普比率低于 0.8 / 最大回撤超 -25%。

---

## ③ 投资/交易决策记录

> 实盘/模拟盘的逐日决策**已自动落盘**:`factor_research/signals/<date>.json`(信号)+ Obsidian `30.output/A股v2.0模拟盘/`(操作卡)。本节只记**需人工复盘的关键决策**(regime 切换、风控动作、异常),不重复日常信号。

| 日期 | regime | 决策 | 依据 | 复盘 |
|---|---|---|---|---|
| 2026-06-12 | 🔴 BEAR | 空仓观望,闲钱配 511010 | Band exposure=0(小盘指数 -3.18% vs MA16) | — |
| 2026-06-14 | — | regime 门控(小盘↔large-cap)落地为可配置项,默认关闭(`regime_gated=False`) | 全样本支持开启但局部窗口肥尾,回撤优先于收益(ADR-011) | — |
| 2026-06-19 | — | 策略正式晋级与登记在册：`illiquidity-large-cap v1.0` | 通过 9-Gate 完整审计，满足 standalone 准入，高容量 alpha 储备 | — |

> 复盘要点(填):切换是否过频(regime 无滞回)、成本损耗是否超预期、事后是否印证。损耗超预期 → 立新假设走研究流程,不私改口径。
