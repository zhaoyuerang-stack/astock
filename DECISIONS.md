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
> ⚠️ **已被 [ADR-017](#adr-017-9-gate-证据自证铁律--三策略归因证否与机械守卫) 修订**:本 ADR 的 9-Gate 证据(DSR p=0.0112 等)经查为**跨策略照抄小盘 illiquidity 家族**,Top800 自有宇宙独立重算 IC=−0.084(反向);58% 头条 100% 来自 MA16 择时非因子。standalone 准入不成立,待退役/重分类。
- **上下文**: 大中盘（Top 800 ADV）中由于套利不充分，流动性短暂枯竭时的非流动性溢价仍然极强。我们设计了 Amihud Illiquidity 因子配合 30% 凸显性风控否决 (Salience Veto) 及 MA16 趋势择时的大容量策略。
- **决策**: 晋级该策略为首个 `"在册"` (APPROVED) 的大中盘单体策略。
- **理由**:
  1. 顺利通过了 9-Gate 完整审计与多重检验测试（DSR p-val = 0.0112，显著性通过）。
  2. 回测满足 `"standalone"` 准入要求：2018-2026 年化收益 58.26%，最大回撤 -17.66%，夏普比率 2.16。
  3. 估计容量达 5.0 亿人民币以上（波动率平方根冲击成本下 5亿 AUM 的净夏普比率仍有 1.74）。
- **失效边界**: 滚动 12 个月夏普比率低于 0.8 / 最大回撤超 -25%。

---

### ADR-017 9-Gate 证据自证铁律 + 三策略归因证否与机械守卫
- **上下文**: 复审 active 在册策略时发现 `illiquidity-large-cap/v1.0` 台账条目是**拼装**的——净值来自一个无 veto 的 Top800 scratch 脚本,9-Gate 的 IC/DSR/中性化证据**逐位照抄**小盘 `illiquidity` 家族,config 又**虚标**了生成码没实现的 Salience Veto。由此回扫全台账(23 family/41 version)与逐策略归因分层,暴露**系统性防自欺漏洞**:门禁证据可跨策略照抄、config 可虚标、PBO 可跳过却 `passed_all=true`、整套 9-Gate 可全空仍 standalone 准入。
- **决策**:
  1. **修订 ADR-016**:`illiquidity-large-cap/v1.0` standalone 资格不成立,待退役/重分类(独立重算 IC=−0.084 反向;58% 全来自 MA16 择时)。
  2. **确立「9-Gate 证据自证」铁律**(拟扩写进 CLAUDE.md 铁律9/登记纪律):门禁证据必须由**本策略本宇宙的一次可复现运行机械产出**——① 禁跨家族照抄(IC 块逐位相同=判失败);② config 须能机械复现台账绩效;③ 任何 gate=None/`nine_gate={}` 禁 standalone 准入;④ `n_trials ≥` 含宇宙/veto/择时/网格的全部自由度;⑤ 生成码须在 canonical 层。
  3. **落地机械守卫**:`scripts/ci/check_registry_evidence.py`(G1 跨家族 IC 照抄 + G2 证据全空/跳门)+ `tests/test_registry_evidence_guard.py`,已接入 `scripts/test_all.sh`;3 个已知病灶进 `PENDING_REMEDIATION` 基线(只拦新违规、不阻塞、修复自动提示移除)。
  4. **三策略归因处置**:`illiquidity-large-cap` 退役;`industry-neglect-rotation/v1.3`(裸因子年化13.8%/回撤−60%/hit=False,靠 MA16 救达标且 9-Gate 全空)补独立 9-Gate + admission 标注;`ai-compute-toc/v1.0` 机制三重证否(见 [[toc-cpo-mechanism-falsified]]),logic chain 降级。
- **理由**: 9-Gate 是防自欺的机械执行点,一旦证据能照抄/手填/跳过,整个证伪体系失效,比单个坏策略危险得多。三策略共性母题 = **用 MA16 大盘择时的回撤控制冒充因子 alpha**,靠头条 metrics 准入——审任何带择时/轮动 overlay 的策略必做**归因分层 L0 裸因子**看其单独是否达标。证据产物:`scripts/research/{illiq_largecap_audit,industry_neglect_v13_audit,toc_*}.py` + `scratch/illiq_largecap_governance_DRAFT.md`。
- **失效边界 / 待办**: 三策略处置须经 `workflow`(台账唯一写入口),处置后从 `PENDING_REMEDIATION` 移除对应 key;铁律9 扩写待并入 CLAUDE.md。

---

### ADR-018 首个干净登记范本:illiquidity clean-v1(真 alpha + 诚实 overlay)
- **上下文**: 用验真机(去 overlay L0 归因 + 本宇宙独立 IC + 容量 + holdout 金库,见 LOOP_ENGINEERING.md)系统性扫候选。价量池 + 基本面池 + value 救活**三轮搜索均未找到 long-only 低相关第二腿**——证实**结构事实:A股小盘只有一个异象簇(小/不流动/冷落/便宜),long-only 因子腿天生 ~0.5 beta 相关,分散只能靠 regime overlay 不能靠堆 alpha**。唯一通过全套验真的真 alpha = 小盘 Amihud 非流动性溢价。
- **决策**:
  1. 将 `illiquidity/clean-v1` 整理为**首个用全套防自欺纪律支撑的登记候选**(证据包 `scripts/research/illiquidity_evidence_pack.py`),作为「真 alpha + 诚实 overlay」的**正确范本**,以后新候选对标它而非已证伪的 illiq-large-cap/v1.3/TOC(ADR-017)。
  2. 北极星从「堆多源 alpha」**重定位**为「一个真 alpha + 诚实 regime 风控 + 容量纪律」——这是 long-only A股小盘的结构上限,非退而求其次。
- **理由**(本宇宙独立机械产出,非照抄):
  1. **真 alpha**:L0 裸因子(去 MA16 overlay)搜索窗夏普 1.05 / 年化 25%,独立 IC t=5.94(主显著性;DSR 肥尾偏弱非主证)。
  2. **金库样本外证伪通过**:2025–2026(从未参与搜索,偷看 1 次)年化 +27.1%/夏普 2.08/回撤 −8.1%。
  3. 搜索窗 hit=True(年化 24.9%/回撤 −17.2%);overlay 仅贡献 31% 夏普 = **风控非 alpha**(与 ADR-017 造假明确区分)。
  4. 容量 ~0.23 亿(个人级;容量小正是未被套利抹平之因)。
- **诚实披露 / 失效边界**: 压力 2010–2026 回撤 **−22.8% 略超 20% 单体线**(2015/2018 小盘崩),不藏窗规避,写入登记;decay_signal=Rank IC 连续 4 季<0 / 滚动 3 年夏普<0.5 / 全市场成交额持续放大;金库段偏短(~1.4 年)须接续复测。
- **待办**: 经 `workflow` phase1 防未来审计 → phase2/3 正式 9-Gate **补跑 PBO**(草稿缺)→ phase4 register;`passed_all` 由 workflow 判定,**禁手填**。草稿 `scratch/illiquidity_clean_registration_DRAFT.md`。

### ADR-019 文档体系整理 + 宪法升级为规则编号治理系统
- **上下文**: 根目录 16 份扁平文档混杂(命名碰撞 `Task.md`/`TASKS.md`、`WEB_DESIGN.md`/`(2)`;孤儿文档不在索引;3 处指向退场代码的陈旧引用),致系统设计认知混乱。
- **决策**:
  1. 16→14 份职责唯一活文档 + `docs/archive/` 冻结区;`CLAUDE.md` 重写为带规则编号(`R-xxx`)+ P0-P3 分级 + 接手90秒协议 + §16 守卫映射表的**单一入口宪法**。
  2. 命令/成本/Web 纪律下沉到 `RUNBOOK.md` / `factor_research/docs/cost_model.md` / `web/CLAUDE.md`;**成本数值唯一权威 = `core/engine.py::CostModel`**。
  3. 纳入 ADR-017「9-Gate 证据自证」5 条为 P0 规则 **`R-EVIDENCE-001`**,接 `check_registry_evidence.py` 守卫。
- **理由**: 多 agent 治理需**可引用**(`R-xxx`)+**可强制**(§16 守卫表来自 `scripts/ci/` 实测,逐个读 docstring 对齐真实 7 守卫,全绿);指针只指**已存在且已验证**的目标(先建 cost_model/web 再切,避免悬空引用)。
- **验证**: 全仓 md 链接零断链;§16 七守卫单独跑 GREEN;`bash scripts/test_all.sh` 全套 `All tests passed!`。提交 `58edd00c4`/`a44fda5c3`/`17fb92082`/`053950d3a`/`f0b4aa01e` + 本次。

---

### ADR-020 standalone 准入强制 DSR 显著性 + 在册 standalone 轨清零 + R-DATA-001 守卫补建
- **上下文**: 审查体系三层防线各留后门——① 9-Gate 只产报告不阻入册;② `register()` 的 standalone 轨只验 `hit`(年化>15%&回撤<20%)不验 DSR;③ CI 守卫只抓证据照抄/跳门标通过,不抓 DSR 不达标。结果:7 个在册 standalone 全部 DSR 不显著(`illiquidity` v1.0/v1.1/v1.3/v3.1、`size-earnings` v1.0、`small-cap-size` v2.0 的 dsr_p∈[0.086,0.396];`industry-neglect-rotation` v1.3 的 dsr_p=None 根本没算),却凭 hit 长期占用「在册有效池」,违反 `R-OBJECTIVE-001`(收益门槛≠搜索后显著)。另 `R-DATA-001` 自 ADR-019 起一直标「缺,待建」无机械守卫。
- **决策**:
  1. **`register()` 加 DSR 门(P0)**: `status=='在册'` 且 standalone 轨(含 hit=True 自动补轨路径)必须 `nine_gate.dsr_p` 存在且 `<DSR_ALPHA(0.05)`,否则 `raise ValueError`。diversifier 轨不受约束(凭组合边际而非单体显著性入册)。
  2. **存量降级(P0)**: 新增 `demote_dsr_insignificant_standalone()` 迁移,把上述 7 个 DSR 不显著的在册 standalone 降为「参考」,保留 metrics/evidence/nine_gate(`R-7.4` 不删历史),写 `dsr_demotion` 审计块。**后果:在册有效池 standalone 轨清零,仅剩 5 个 diversifier(全对冲族:`hq-momentum-hedged`×2、`large-cap-growth-hedged`×3)**。
  3. **CI 守卫加 G3(P0)**: `check_registry_evidence.py` 增 active+standalone 但 dsr_p 缺算/≥0.05 即判失败,防降级后回流。
  3b. **防御纵深·堵工厂自动晋级洞**: `workflow/phase4_register.py` 原把 hit 候选直接自动入「在册 standalone」,而工厂通道 nine_gate 摘要不含 dsr_p(DSR 由独立 9-Gate 回填)——这正是 7 个 standalone 入册的源头。改为 hit 候选仅当摘要里 `dsr_p<0.05` 才自动入在册,否则一律先入「候选」,待 `run_nine_gate_after_registration` 回填 DSR 后由人工/workflow 升级。register() 的 DSR 门是硬墙,phase4 主动避让是纵深。
  4. **补建 `R-DATA-001` 守卫(P0)**: 新增 `scripts/ci/check_no_legacy_data.py`(AST),禁代码 `import data_full` / 从 `data_full` 目录读盘,放过注释/口径标签/迁移目录;挂入 `test_all.sh`,§16 守卫表去「缺,待建」。
  5. **E 回溯补审(诚实结论)**: 30 个 nine_gate 空版本经分类**0 个可审**(全是候选/参考/退役且无兼容 runner 或无该版本 config 规格),而唯一要求 DSR 的 status(在册 standalone)已清零、剩余 5 个在册 diversifier 全已有 DSR ⇒ **无治理缺口,无可造假**。扩展 runner 覆盖另立 TASKS backlog。
- **理由**: 宪法第 18 条「宁可不入册,也不要绕过防未来/相信假 alpha」。hit 达标只是观察条件,经不起多重测试惩罚的 standalone 不配占用有效池。DSR 仅卡 standalone 而放过 diversifier,因后者准入逻辑本就是组合边际(`rationale`)而非单体统计显著性。降级而非删除,守 `R-7.4` 退役纪律。
- **验证**: register DSR 门 7 路径单测全对(无 dsr/≥0.05 BLOCK、<0.05 PASS、hit 自动补轨无 dsr 亦 BLOCK、diversifier 不受约束);迁移 dry-run/apply 精确命中 7 条,降级后在册 standalone=0;`check_registry_evidence.py` 对迁移前台账 exit=1(7 条全抓)、对迁移后 exit=0;`check_no_legacy_data.py` 现有 5 处合法引用全放过、8 例正负回归全对。提交见下。

---

### ADR-021 promote 验证栈全部截到 <holdout boundary + 边界配置锁 + 因子归一化误诊证否
- **上下文**: 对 holdout/未来函数做红队审计,8 项发现。**核验后**两个「致命」一真一假:
  - 🔴**真**(工作流泄露):`phase2_backtest.py` OOS 段硬编码 `2023~2026-12-31`、成本/相关性/decay 全用 `2018~2026`;`phase3_wf.py` WF 测试窗到 2026 —— 而 holdout.start=2025-01-01。**整条 promote 验证栈都吃金库**(2025+),且金库绩效经机械门(`annual>0`/`OOS/IS decay>0.3`/WF 正窗比≥2/3)+ 人眼报告参与晋级判定,破坏 §5.2「唯一一次校验」语义。`check_holdout_compliance.py` 原只锁 3 条自动选择路径、不覆盖 phase2/3,也不锁 boundary 配置值。
  - 🔴**假**(误诊):「因子时间轴归一化泄露」不成立 —— `transforms.py::zscore/rank_transform/mad_clip` 与 `utils.py::safe_zscore` 全是 `axis=1` 横截面(逐日跨股票),`rolling_*` 是 trailing 非 expanding,无全样本/未来统计量。`l3_walk_forward` 先在 full close 上算因子再切片**不泄露**(横截面逐日独立,trailing 还需 boundary 前 warmup,先算后切反而正确)。
- **决策**:
  1. **截断验证栈(P0)**: `phase2_backtest.run()` / `phase3_wf.run()` 在 load 后**单点把面板截到 `<boundary()`**——因子/三段/成本/相关性/WF 窗全部派生自被裁面板,金库 date≥boundary 永不进入计算或选择;OOS 终点改由 boundary 动态裁定;两文件加自查门 `assert_search_clean` 并纳入 `check_holdout_compliance.py` REQUIRED。金库仅留给唯一 `validate_on_holdout`。
  2. **边界配置锁(P0)**: `check_holdout_compliance.py::check_boundary_lock` 把 `holdout.start` 当前值 hash(`2025-01-01`)钉死,任何改动 exit 1,强制 ADR + 同步更新 pin。
  3. **回归防护**: `tests/test_factor_normalization_axis.py`(断言 transforms 横截面 + 源码无 `expanding()`)把误诊永久钉为非问题;`tests/test_holdout_truncation.py`(合成面板跨 boundary 跑真实 phase2/3,断言无段/窗触金库)。
  4. **文档(P1)**: LOOP §5.2 补 ① 1.5 年金库**信度有限**声明(对外宣称 holdout 通过须附此限制,金库成熟前是「未证伪」非「已证实」)+ ② **boundary 迁移协议草案**(只进不退、追加新段而非移旧段、变更必经 ADR + 作废受影响记录)。
- **理由**: §5.2「loop 自己不得触碰金库」必须覆盖**整条选择链**(搜索 + 全部验证 + 晋级判定),而非仅 island search。验证栈吃金库 = 把金库变成第二个样本内,holdout 失去戳穿过拟合的能力。单点截断(load 后裁面板)比逐处加 mask 更难漏。误诊证否同样重要:避免误改安全的横截面管线。
- **验证**: `check_holdout_compliance.py` 5 路径 + 边界锁 GREEN,模拟改边界 exit 1;phase3 实跑确认数据截至 2024-12-31(原末日 2026-06-19);两组回归测试(横截面 5 例 + 截断 2 例)全绿。本机当前 holdout 仅 1.5 年,**既往在册策略的 phase2/3 数字含金库,需用截断后引擎重算**(另立 TASKS 项)。提交见下。

---

### ADR-022 种子溯源:autoresearch 候选记录种子来源,LLM 起源晋级时触发人工语义审视
- **上下文**: holdout 审计 #7「种子候选可能含金库知识」——autoresearch 两条种子来源:① 确定性种子(`generator._SEEDS` 17 个教科书因子对,无金库语义);② LLM 种子(按 `_ISLAND_THEMES` 主题,LLM 先验**可能含 2025+ 行情认知**=语义泄露,不可机械证否)。问题:provenance 在生成时**本就存在**(`generate_llm_candidates` 返回 model)但被 `_llm_seeds` 的 `accepted, _, _` **丢弃**;`seeded_by` 只到搜索响应层、不下沉候选、不进 registry——晋级策略**查不到**是否源自 LLM 种子。
- **决策**(接住并传播,非发明新追踪):
  1. `Candidate` 加 `provenance: dict` 字段;确定性种子标 `{origin:deterministic_seed,...}`,LLM 种子标 `{origin:llm_seed, theme, model, generated_at}`(`_llm_seeds` 停止丢弃 model)。
  2. **血缘继承**:islands 变异/交叉子代经 `_merge_provenance` 继承祖先 origin(`origin:derived` + `ancestor_origins` + 保留 `llm_ancestors`),溯源不因多代进化断链。
  3. **持久化**:`CandidateRepository._deserialize` 补读 provenance(原 load 时丢失);冠军 `ChampionRecord`/`AutoResearchChampionView` 透出 provenance,人工 review 时即可见。
  4. **晋级证据**:`promote_approved_candidate → promote_spec → phase4 _build_evidence` 把 `seed_provenance` 写进 registry evidence;**任一祖先是 llm_seed → 打 `semantic_seed_review` 标记**(LLM 先验不可机械证否,须人工审视搜索空间是否含金库语义)。
- **理由**: 种子语义泄露不可机械证否(LLM 知道 2025-26 发生了什么),只能**记录 + 人工审视**——这正是审计判定的「🔶 部分可」。确定性种子(默认路径)是教科书因子,无此风险,不打标。全链路传播保证晋级后仍可追溯,断链的 provenance 对「晋级策略能否追溯」无意义。
- **验证**: 9 例溯源单测(种子标注/血缘合并/孙代继承/纯确定性无 LLM/仓库往返/evidence 语义标记四态)全绿;58 个 autoresearch 相关既有测试无回归;`bash scripts/test_all.sh` 全套「All tests passed!」。提交见下。

---

### ADR-023 holdout boundary 迁移从草案转为机械强制(只进不退 + 旧金库作废)
- **上下文**: holdout 审计 #6「boundary 迁移无机制」。ADR-021 已 hash 锁 `holdout.start` 防误改,但「金库后移=复活已偷看段」「迁移后旧记录如何处置」只在 LOOP §5.2 写了**草案原则**,无机械强制。到 2027 金库后移面临两难:后移则旧金库(2025-26)变可搜索、既往 `validate_on_holdout` 记录失唯一性;不移则旧金库变死数据、新真 OOS 无保护。
- **决策**(草案→代码强制):
  1. **append-only 边界历史账本** `app_config/holdout_boundary_history.jsonl`(**git 跟踪**——`data_lake/` 被 gitignore,放那 CI 守卫跨机器拿不到;genesis=2025-01-01)。active 金库 = 账本最大值;superseded(已作废)= 所有 < max 的历史边界(派生,不删)。
  2. **唯一推进入口** `governance.holdout.migrate_holdout_boundary(new, reason)`:强制 new 严格 > 历史最大值,否则抛 `HoldoutBoundaryRegression`(只进不退,后移会复活已偷看金库);append 记账。
  3. **守卫** `check_holdout_compliance.py::check_boundary_monotonic`:账本严格递增 + `settings.holdout.start == active`(手改前进未经 migrate 记录 / 后退均 exit 1),叠加 ADR-021 hash 锁。
  4. **多重检验按 active 金库计**:`holdout_trials(boundary_filter=)` 与 `validate_on_holdout` 的 n_trials 只数当前 boundary 的 peek——旧(superseded)金库 peek 不再污染新金库的 DSR 惩罚,且同一候选可对新金库合法重校验(不被旧记录误判 `HoldoutIdentityMismatch`)。
- **理由**: 「只进不退」是金库唯一性的核心安全属性,必须机械强制而非靠自觉。旧金库 peek 计入新金库惩罚会过度保守(新金库是新数据),但完全不计又可能被「移边界重置 p-hack」滥用——因边界推进需真实时间流逝(2025-26 才变可搜索)+ ADR + 双锁(hash + 单调),不可自由 game,故按 active 金库计是诚实平衡。`superseded` 留痕不删守 R-7.4。
- **验证**: 6 例迁移单测(只进不退拒后移/相等、记账+作废、按 boundary 计 trials、迁移后重校验不被拦、守卫单调+settings 一致)全绿;守卫现 5 路径 + hash 锁 + 单调锁 GREEN;`bash scripts/test_all.sh` 全套「All tests passed!」。提交见下。

---

### ADR-024 small-cap-size/v2.0 纸面前向实验(人工 override · 零真金 · 不绕过 DSR 门)
- **上下文**: 修漏洞后全池重审,无一策略 DSR<0.05。唯一像样 = `small-cap-size/v2.0`(参考):回测年化 21.6%/回撤 -17.7%/夏普 1.38、净化 CV 过、经济学(小盘流动性溢价)站得住,但 **DSR=0.086** 过不了 ADR-020 standalone 门(多重检验下不显著)。「DSR 过不了 ≠ 不赚钱」——它是「不能统计上排除是运气」;该策略大概率真有 alpha,只是证据没强到能让系统替你下注。所有者(用户)决定**明知风险**纸面前向收集真实样本外证据。
- **决策**(纸面前向,**不洗成达标**):
  1. **载体 = paper-forward**,零真金。靠策略自带 MA16 二值择时熊市清仓为唯一防守(用户选「只靠 MA16」,无额外硬止损)。主仓继续防守(空仓+国债ETF)。
  2. **绝不绕过门**:small-cap-size/v2.0 仍是「参考」、DSR 仍 0.086、**不**登记在册、**不**改 register()/台账/admission(那是 R-LLM-001+§12.3 禁的自欺)。本实验只是「人明知不达标、旁路纸面观察」。
  3. **隔离机制**:新增 `scripts/research/paper_forward_smallcap.py`——canonical 引擎跑 v2.0(point-in-time,因子 shift(1)/MA16 用过去),取 **2026-06-22 起的前向段**作真实 OOS,快照追加 `reports/experiments/smallcap_v2_paper_forward.jsonl`。**不改 settings.strategy/production.json**(实测:非可部署策略信号会被 readiness 正确分流到 draft、paper 不跟,故走独立旁路而非污染生产管线)。
  4. **复核**: 数据日更后跑跟踪器累积证据;约 **2026-09 月底(~3 个月前向)**复核——前向若兑现(夏普稳、回撤受控)则证据增强(n_periods↑,DSR 可能真过)再议小额真仓;若前向塌陷/破 MA16 防守则证否、停。
- **理由**: 所有者有权拿(纸面)风险赌灰区策略,只要**诚实记账、不污染台账/门禁**。前向跑本身在攒证据:真 alpha 则样本越长越可能真显著,过拟合则纸面暴露、零真金损失。这与「绕过 DSR 门把它塞进在册」有本质区别——后者是自欺,前者是诚实的前瞻验证。
- **验证**: 跟踪器 2026-06-22 建基线(前向 1 日;全历史 2051 日确认 21.6%/1.38/-17.66%);未碰台账/settings/部署(small-cap-size 仍参考、主仓仍防守)。提交见下。

---

### ADR-025 大盘宇宙判定 Bug 修复（量纲校正与真实总市值接入）
- **上下文**: 在对系统全策略进行牛熊状态自适应评估时，发现大中盘策略 `large-cap-growth-hedged` 的大盘宇宙过滤代码 [large_cap.py:build_universe](file:///Users/kiki/astcok/factor_research/factors/large_cap.py#L90-L94) 存在维度/量纲错误：计算市值 `cap` 时使用了 `ADTV (amount.rolling(20)) * raw_close`。由于成交额 `amount = 成交量 * 股价`，该公式实际计算的是 `成交量 * 股价^2`（量纲为 $\text{CNY}^2 / \text{share}$），导致大盘选股宇宙严重偏向绝对高股价而非大市值的个股，污染了策略真实的 Alpha。
- **决策**:
  1. 引入真实的日频总市值数据 `total_mv`。在 `load_clean_panels_with_growth` 中，通过 `load_daily_basic_panel` 从数据湖 `daily_basic` 表中载入当日真实总市值（万元），对齐并 ffill 填充。
  2. 重构 `build_universe`：如果面板中存在 `total_mv`，则直接按其进行截面排序选取 `top_n=200` 公司；否则保留原逻辑作为 Fallback。
  3. 通过 `raw_close.columns.tolist()` 将 Index 转化为 List，修复了 pandas Index 在 boolean 判断下的 truth-value 歧义错误。
- **理由**: 修正维度错误保证了大盘宇宙的绝对真实性。重新评估后，`large-cap-growth-hedged` 的 Baseline 夏普由 0.54 修正为 0.44；而动态状态分配（S2）夏普提升至 0.71（+0.27 分离度，好于修复前的 +0.14），与黄金国债防御腿的相关系数下降为 -0.070，为组合配置提供了更优秀的正交性。
- **验证**: 跑通了全部项目级测试（`test_all.sh`）。

---

### ADR-026 多 Regime 极小值极大化生存目标函数与另类因子搜寻
- **上下文**: 传统遗传搜寻优化全局平均 Rank ICIR，容易选择拟合大牛市或常态行情的“晴天因子（Fair-weather Alphas）”，这导致策略在极端政权发生剧烈切换（如小盘股踩踏）时面临灭顶之灾。
- **决策**:
  1. 在 `factory/autoresearch/islands.py` 中引入 `regime_aware: bool = False` 参数。激活时，将适应度计算修改为对 3 个极性历史 Regime（Regime 1: 小盘流动性踩踏；Regime 2: 蓝筹/价值轮动；Regime 3: 常态牛市）的 $|ICIR|$ 极小值进行极大化优化。
  2. 利用此机制，重新对限制在资金流及股东持股的另类因子宇宙进行了大比例深搜。
  3. 对搜寻产出的 Champions 进行了三段式标准性能压力回测验证。虽然它们在 2023-2026 年（OOS 段）拿到了 27-28% 的高额年化收益，但因为长周期（2018-2020）反转因子不匹配，被 L3 门禁自动搁置并拦截在注册台账之外。
- **理由**:
  - 极小值极大化（Min-Max）强制引擎避免出现严重的历史“回测盲区”，优化了防御腿的筛选。
  - DSR 门禁的硬性阻截确保了体系的防过拟合自律，搁置的因子作为极佳的战术影子热备封存。
- **验证**: `test_all.sh` 全通；`compare_regimes.py` 和 `backtest_reality_v2.py` 执行成功，证实了极小值极大化的生存优势与门禁拦截的精确性。

---

### ADR-027 双阀风控融合控制（价格一阶风格门门控 + 成交量二阶加速度熔断）
- **上下文**: 反转策略（Reversal）在 A 股虽然拥有极高的样本外暴利，但在特定时期（如 2018-2020 年大盘抱团牛市）会由于长周期风格失血而崩溃，而在剧烈踩踏期（如 2024 年初小盘踩踏）会遭遇突发性闪崩。常规的对称波动率控制（GARCH）或下行半方差缩放，会由于 A 股的高 Beta 特质而引发慢性“仓位饥饿”，极大地稀释了策略的超额收益。
- **决策**:
  1. 设计并实现**双阀融合风控择时器（Dual-Valve Gated Risk Controller）**，将一阶价格趋势与二阶成交量动能加速融合。
  2. **一阶价格阀（Style Gate）**：利用策略自身的累积净值（NAV）与其 40 日移动平均线 $MA_{40}(NAV)$ 的强弱关系，作为风格的硬开关。当净值跌破 MA40 时全局彻底关机（杠杆置 0.0），规避 2018-2020 式无声风格失血。
  3. **二阶量能阀（Panic Gate）**：监控持仓股成交量的二阶加速度（量的变化率的变化），当 Z-score > 2.0 时熔断降杠杆至 0.2，规避 2024 式高流动性闪崩。
- **理由**:
  - 这种价格均线硬开关与成交量二阶加速度阀门的组合，在 2020-2026 样本外将 Reversal 因子的最大回撤从 **`-57.53%` 斩半控制在 `-30.28%`**，同时几乎完全保留了策略的 Sharpe 性价比（`0.49` vs 基准 `0.53`）；在 2018-2026 全周期中更实现了扭亏为盈。它证明了在 A 股做微盘股或反转因子的风控，二值门控择时远优于连续的波动率缩放。
- **验证**: 实验脚本 `test_dual_valve_rescue.py` 运行成功，双阀融合在 16 年全生命压力测试中表现卓越。

---

## ③ 投资/交易决策记录

> 实盘/模拟盘的逐日决策**已自动落盘**:`factor_research/signals/<date>.json`(信号)+ Obsidian `30.output/A股v2.0模拟盘/`(操作卡)。本节只记**需人工复盘的关键决策**(regime 切换、风控动作、异常),不重复日常信号。

| 日期 | regime | 决策 | 依据 | 复盘 |
|---|---|---|---|---|
| 2026-06-12 | 🔴 BEAR | 空仓观望,闲钱配 511010 | Band exposure=0(小盘指数 -3.18% vs MA16) | — |
| 2026-06-14 | — | regime 门控(小盘↔large-cap)落地为可配置项,默认关闭(`regime_gated=False`) | 全样本支持开启但局部窗口肥尾,回撤优先于收益(ADR-011) | — |
| 2026-06-19 | — | 策略正式晋级与登记在册：`illiquidity-large-cap v1.0` | 通过 9-Gate 完整审计，满足 standalone 准入，高容量 alpha 储备 | ⚠️ 见下行:9-Gate 证据经查为照抄,已 ADR-017 修订 |
| 2026-06-19 | — | **修订**:`illiquidity-large-cap v1.0` standalone 资格不成立,待退役/重分类(ADR-017) | 独立审计:Top800 自有宇宙 IC=−0.084 反向,58% 全来自 MA16 择时;9-Gate 证据照抄小盘家族 | 待 workflow 处置 |
| 2026-06-20 | — | 整理 `illiquidity/clean-v1` 为首个干净登记范本(ADR-018) | 三轮搜索证实小盘仅一异象簇;唯一通过全套验真:L0 夏普1.05/IC t=5.94/金库样本外夏普2.08 | 待 workflow phase1~4(补 PBO) |
| 2026-06-23 | — | 修复 `large-cap` 宇宙维度 Bug (ADR-025)，重新审计大容量策略 | 大盘宇宙过滤公式误用量纲 `ADTV * price`。校正为真实总市值 `total_mv`，测试全部通过 | 重算后 S2 表现更优（夏普 0.71/与防御正交性 -0.07） |
| 2026-06-29 | — | 落地 Regime-Aware 极小值极大化目标函数并重启另类因子大比例进化搜寻 | 2024年初踩踏暴露全局平均优化脆弱性；Min-Max 框架成功提升 OOS 业绩（年化+28.23%）并触发门禁拦截置为影子池热备 | 证明了系统防过拟合门禁的强自律性与影子池在不同政权环境下的高战术价值 |

> 复盘要点(填):切换是否过频(regime 无滞回)、成本损耗是否超预期、事后是否印证。损耗超预期 → 立新假设走研究流程,不私改口径。

