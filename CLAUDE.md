# A股全市场因子量化研究

> 给 AI 的**操作宪法(精简)**。系统设计/架构 → [SPEC.md](SPEC.md);分阶段路线 → [ROADMAP.md](ROADMAP.md);当前进度 → [STATUS.md](STATUS.md);开放任务 → [TASKS.md](TASKS.md);踩过的坑 → [LESSONS.md](LESSONS.md)(+ auto-memory);多 agent 系统级分工 → [MULTI_AGENT.md](MULTI_AGENT.md);决策框架/记录(为什么这么决策)→ [DECISIONS.md](DECISIONS.md);端到端流程(谁干每步)→ [WORKFLOW.md](WORKFLOW.md)。代码与操作手册在 `factor_research/`。数据基础设施详情 → `factor_research/docs/data_infrastructure.md` + `factor_research/data_lake/README.md`。
> 每次接手先读本文件 + `STATUS.md`。

## 定位
全市场、日频因子量化。真正的资产 = **数据基础设施 + 策略工厂 + 有效策略管理**;**任何策略默认会失效**,按**母策略**(独立 alpha 家族)组织,持续 发现 → 证伪 → 替换。
- **口径**:以 `data_lake` + `core/` 统一回测内核为准,绝不用 `data_full` 旧口径(幸存者偏差水分)凑达标。
- **门槛**:单母策略入册 年化>15% / 回撤<20%;项目级(组合后)**满意线** 年化≥20% & 夏普≥1.0,**卓越线** 年化≥28% 或 卡玛≥1.6(原 35%/15% 锚定 data_full 水分 40%,已退役)。

## 铁律(违反 = 回测结果作废)
**数据**
1. **口径**:全市场(含创业板300/科创板688/小盘),警惕幸存者偏差;退市、停牌正确处理。绝不用只含沪市主板的旧缓存。
2. **防未来函数**:财务按公告日对齐到交易日 ffill;T 日只用 T 日前已披露的财务。
3. **复权陷阱**:估值(PE/PB)必须用不复权价(后复权价算估值量纲不匹配、虚高数倍)。
4. **接口封禁**:东财逐只下 40-50 只就封 → 换批量/聚合接口(如 `yjbb_em`),绝不加多线程。
5. **akshare hang**:唯一可靠超时 = daemon 线程 + join(timeout);ThreadPoolExecutor / socket timeout 都无效。
6. **联网**:需 `dangerouslyDisableSandbox`;clash 代理(7897)下新浪源可用、东财 push2 被拦。
7. **质量判定**:区分真问题(OHLC错/负价/跳变>50%)与 A股正常现象(停牌/新股首日/一字板)。

**策略生命周期(默认会失效)**
8. **先证伪再相信**:漂亮回测先假设是 过拟合 / 幸存者偏差 / 特定行情依赖(如 2025 极端行情不可重复),用 样本外 + 压力测试 + 成本敏感性 去打。
9. **登记纪律**:每个版本必须 口径透明 + 配置 + 绩效 + 核心假设与失效信号;失效就退役,台账标记退役而非删除。

## 交易成本(回测/进化必须按此扣,禁用乐观值)
| 费用 | 比例 | 收取方式 |
|------|------|----------|
| 佣金 | 0.0065%(万0.65) | 买卖双边 |
| 印花税 | 0.05% | 仅卖出(2023.8 起减半) |
| 过户费 | 0.001%(万0.1) | 买卖双边 |
| 冲击/滑点 | 0.2%(小盘审慎,大盘可 0.1%) | 买卖双边 |
| 融资利率 | 5%/年(1.25x → 拖累 ~1.25%/年) | 持仓日,仅杠杆部分 |

**单边**:买 0.208% / 卖 0.258% → **往返 ≈ 0.47%**(另加融资)。冲击/滑点 0.2% 维持审慎,不下调。
当前代码默认在 `core/backtest.py::CostModel` 固化真实成本近似:买 0.225% / 卖 0.275% / 融资 6.5%;若调整费率,必须同步台账备注。

## 常用命令(均在 `factor_research/` 下)
```bash
python3 run_daily.py --no-update   # 出当日信号(不联网);去掉 --no-update 先增量更新
python3 strategy_lake.py           # 真实口径复测(2018-2026 + 2010-2026 压力测试)
python3 strategy_registry.py       # 母策略台账对比表
python3 validate_final.py          # 数据质量校验 → data_lake/quality_report.json
python3 scripts/research/cost_sensitivity.py  # 成本敏感性
python3 scripts/research/run_nine_gates_all.py --strategy size_earnings  # 运行 9 道门禁审计
bash scripts/test_all.sh           # 一键测试器:分层依赖守卫 + 数据湖写入守卫 + 全部 test_*/tests
```

## Web 工作台命令(在 `web/` 下,Next.js 项目 `quant-research-web`)
```bash
npm run dev                        # 启动开发服务(默认 :3000);开发期间禁跑 build(见前端纪律)
npx tsc --noEmit                   # 类型检查(dev 期的首选验证)
npm run lint                       # ESLint(next lint)
npm run test                       # node --test lib/*.test.mjs(非 vitest)
npm run build                      # 仅在 dev 已关闭时跑;CI/部署用
```

## 工作约定
- 新母策略先 `register_family(...)` 声明假设/失效信号，再 `register(family, version, ...)` 登记版本（两层 schema 见 SPEC）。
- 新因子或策略入册前必须通过 9-Gate R2P 流水线进行中性化与 DSR 多重测试惩罚审计，确保无数据泄露和交易成本超限风险。
- 回测交付三段：样本内(2018-2026)/ 样本外(2023-2026)/ 压力测试(2010-2026)。
- 实盘折扣:费率见上表;另评估 小盘容量、停牌/涨跌停、组合换手。
- 已 git 化:重要阶段改动用提交固定;数据湖和大体量运行产物不入库。
- **提交纪律(多 agent 共享工作树,违反 = 卷走别人改动/无法 revert)**:
  1. **一个 commit = 一个完整、可独立 revert 的意图**。宁可拆成几个小而自洽的 commit,不要一个"什么都做了"的大杂烩。
  2. **绝不 `git add -A` / `git add .`** —— 本仓库多 agent 并发,一锅端会把别人半成品改动卷进你的 commit。**只用显式路径** `git add <file>...`,且只 stage 你 trace 得清、属于本次意图的文件。
  3. **提交前必 `git diff --cached --stat` + `git diff --cached` 核对范围**:每个文件、每一行都要 trace 到本次目的;别人的改动留在工作树,不碰。
  4. **不擅自切分支 / reset / rebase 共享分支**;动 git 历史前先看 `git status` 有无他人正在改的文件。
  5. **message 讲"为什么"**:`type(scope): 标题` + 正文写根因(diff 看不出的)和验证证据(守卫绿/测试 N/N);提交前先跑守卫+测试,绿了再提。
  6. 尾注固定加 `Co-Authored-By:` 与 `Claude-Session:`(claude)。
- **搜索/回测默认思维**: 先问能否 `预计算 / 复用 / 并行 / 拆分`，再问能否改变实现顺序；只能加速计算，不能改样本、公式、成本、`shift(1)`、T+1 或任何真实口径。
- **前端开发纪律**: 严禁在开发服务运行（`npm run dev`）时跑生产打包（`npm run build`），防止 Webpack 缓存污染导致全站 404/500 崩溃。`build` 不可作为 dev 运行时的常规验证步骤；先看 `npx tsc --noEmit` 和 `npm run lint`。若出现缓存损坏（ENOENT/Cannot find module 等），须强制关闭 dev 任务、用 `lsof -ti :3000 | xargs kill -9` 释放端口、运行 `rm -rf web/.next web/node_modules/.cache` 清空双重缓存、再重启并指引浏览器硬刷新（⌘+Shift+R）。
- 改了架构/进度,顺手更新 SPEC.md / STATUS.md;踩了坑记 LESSONS.md。

## 机器与并行
本机 = **Apple M5(10 核:4 性能 + 6 能效)/ 24GB**。**凡可并行的都并行**,别串行干等(本节=并行**规则**;4 个 agent 平台间的分工见 [MULTI_AGENT.md](MULTI_AGENT.md)):
- **跨独立单元并发**:不同 tushare 接口(限速按接口,实测 9 并发零退避)、多因子回测、多策略复测、多 agent 审计(Workflow 编排)——各跑各的,用 `&`+`wait`(启动器守着才不变孤儿/能收完成通知)或 run_in_background,墙钟从 N×T 压到 ≈T。
- **不与现有铁律冲突**:封禁类单一来源(东财)仍**绝不并发抓**(铁律4);**同 token 同一接口顺序**(共享限速);akshare 超时仍 daemon+join(铁律5)。并行只用于**本质独立**的工作。
- **先判瓶颈再定并行维度**:抓取是 API/限速 bound(只有跨接口并发才有效,堆核无用);计算(回测/审计/截面回归)才是 CPU bound(吃多核 + pandas 向量化)。
- **内存是高并发真约束**:大数据回填把累积 DataFrame 全程留内存(单接口可达数 GB),并发前看 `memory_pressure`,吃紧(free<15%)就降并发或改增量 append。

## LLM 分工铁律(违反 = 防自欺失效)
- **苦力归便宜模型,判断归代码**:候选生成 / 批量抽取(研报-NLP)/ 打标 等大批量低风险活,默认走配置的便宜模型(`app_config/settings.yaml::ai_model`,现 DeepSeek v4-flash;统一入口 `services/agent/llm_adapter.py::get_adapter()`,无 key 退规则式)。
- **防自欺判断恒为确定性代码,禁交 LLM**:Alpha Audit(NW+RidgeCV+置换)、L0-L3 筛选、回测、入册门槛——一律代码。任何时候**不得让 LLM 代替这些判断**(便宜或强模型都不行)。LLM 只提议候选,代码处置去留。
- **LLM 不越权**(承既有):只做路由/解读/生成候选,永不执行工具/下单(不越权门在 planner)。
- **三者不串**:强模型(Claude)做研究编排/推理;便宜模型干苦力;确定性代码做判断。把判断塞给 LLM = 毁掉整个证伪体系。

## 架构铁律(模块解耦,违反 = CI 报错)
单向依赖链:`data(lake) → factors → core.engine → {strategies, factory/workflow} → registry → production`。
- **回测唯一权威 = `core.engine.BacktestEngine`**。`core.backtest` 已退场(`core/_deprecated_backtest.py.bak`),禁止再 import;用 `strategies.small_cap` / `factors.small_cap` / `engine.metrics` / `factors.utils` 的 canonical 路径。
- **配置走 `app_config/settings.yaml`**(`get_settings()`),勿散落硬编码。
- **台账唯一写入口 = `strategy_registry.register_family/register`**(即 `workflow/phase4_register`);任何代码不得直写 `strategy_versions.json`。
- **候选→登记唯一通道 = `workflow` phase1~4**。factory(`factory/lines`)负责生成+L0~L3 廉价筛选;L3_PASSED 经 `workflow/promote.py`(或 `python3 apps/factory_cli.py promote`)走 phase1 合成防未来审计 → phase2/3 → phase4 登记。`phase1_synthetic` 是防未来铁律的唯一机械执行点。
- **生产层(run_daily 等)禁止 import `factory.*`/`scripts.research.*`/`workflow.*`**。
- 守卫:`python3 scripts/ci/check_layer_deps.py`(已接入 `scripts/test_all.sh`)。

## 任务执行循环协议

每个任务作为循环运行，不是直线：
1. 写变更。
2. 运行检查：测试 + linter + 类型检查。
3. 有失败？读错误，找原因，修它，回到第 2 步。
4. 最多循环 5 次。

**停止条件：**
* 所有检查通过 → 报告“完成”，并附上通过的输出作为证明。
* 5 次用完 → 停下来，报告还剩什么没过。
* 同一个错误连续出现两次 → 立刻停。你在猜，不是在修。

**禁止行为：**
* 禁止：在没有检查输出的情况下报告“完成”。
* 禁止：通过删断言、弱化测试来让测试通过。修代码，不修记分牌。
