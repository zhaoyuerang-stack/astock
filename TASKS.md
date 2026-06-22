# TASKS — 开放任务 backlog

> 单一真相源:**所有未完成的可执行任务**。其余文档(STATUS/对话)只记历史/状态,开放任务一律落这里,防遗忘。
> 完成即移到「近期完成」或删除。新任务带:来源 + 上下文 + 谁能做。

## 🔴 进行中 / 优先

### 引擎修复后的台账诚实性缺口(2026-06-21 发现;均待用户决定,我未碰部署清单)
- [ ] **生产部署清单指向一个从未真正过闸的策略** — `deployments/production.json` 唯一腿 `illiquidity/v3.1`,加载时报 `spec_hash 不匹配`(清单钉的哈希是修复前的)。但**根因更深**:`decide_nine_gate()`(部署严格闸,要求 `passed_all=True`)从 2026-06-19 到今天重审,从未对这条腿点头过——`migrate_deployment.py --apply` 会因此直接拒绝重新生成清单,不是改个哈希就能"修复"。是否换腿/降级/接受现状,需人决定。谁:用户。**新证据(2026-06-21 周度维护实跑发现)**:这个漂移现在还会连带炸穿 `scripts/ops/scheduled_cross_asset_leg_search.py`(经 `portfolio/cross_asset.py::search_cross_asset_legs()` 调用无保护的 `run_active()`),不是孤立的报告类脚本问题——拖得越久,卡住的下游越多。本轮我只修了"不该崩"的(decay_monitor/production_readiness 已加 try/except),没碰这条因为它的工作本身就需要在册组合真实收益,没法优雅降级,只能等部署决定。
- [x] **发现并验证 core.engine T+1 fill 修复(5ebcdde7c,06-20 21:04)使此前所有 9-Gate 审计失真** — ✅ 逐日比对 illiquidity/v3.1 修复前后收益序列,从第1天就有差异(最大单日差5.5pp);maxdd 从旧引擎算出的 -14.7% 纠正为真实 -29.3%(发生在2019-2020 COVID段,旧序列误判到2018年末)。已用修复后引擎重跑 illiquidity 全家族(v1.0/v1.1/v1.3/v3.0/v3.1/clean-v1)9-Gate + 持久化收益序列 + `lineage_pbo` 重算:**六个版本 passed_all 全为 False**,Gate4(DSR不显著)/Gate5(回撤超-20%线,v1.0/v1.1/v1.3 甚至-41%~-42%)/Gate6(成本衰减87%~110%)三道独立检验全部不过;家族 PBO=0.92(版本选择基本是噪音);v1.0 与 clean-v1 日收益 corr=1.0(数学同一序列)。衰减监控在新序列上仍判"未衰减"(滚动3年夏普2.20,逐年走高)——alpha本身没变差,是旧引擎一直在低估风险。结果存 `research_ledger`(run_id `30e5e8ed8a7d1b46`)。
- [x] **其余 4 个家族 7 个版本(8减1,large-cap-growth-hedged/v1.0-full 状态=参考未审)用修复后引擎重审完毕** — ✅ 全部 `passed_all=False`(13个版本里离显著最近的是 small-cap-size/v2.0,DSR p=0.086)。但 `decay_check` 在新序列上揪出真问题:`hq-momentum-hedged`(v1.0/v1.0-full)与 `large-cap-growth-hedged`(v1.0除外/v1.1/v1.1-full)**decayed=True**——长历史版本滚动3年夏普从2018年起连续7年为负,回撤-85.2%~-95.9%,触发 LOOP_ENGINEERING §5.4 机械退役复核条件,不是统计证据薄弱,是真衰减/可能从未起效。`size-earnings`/v1.0 与 `small-cap-size`/v2.0 健康未衰减,后者回撤-17.7%是当前台账唯一一个全历史回撤达标(<20%)的版本。结果存 `research_ledger`(run_id `859bb3e836dc7be9`)。
- [ ] **`hq-momentum-hedged`、`large-cap-growth-hedged`(对冲组合)走退役复核** — decay_check 机械触发(LOOP_ENGINEERING §5.4),非删除标退役。谁:走 workflow(人确认)。
- [x] **周度自动化三件套修复(解释器+decay_monitor范围/调度+9-Gate覆盖)** — ✅ 根因是 `scheduled_weekly_maintenance.py` 用系统自带 `/usr/bin/python3`(3.9.6,不支持 `int|None` 运行时语法)起子进程,导致9步里6步(`decay_monitor`/`tradability`/`live_readiness`/`factor_search`/`cross_asset_leg_search`/`audit_stale`)全部在 import 阶段就崩——改成 `/opt/homebrew/bin/python3` 后4步(`decay_monitor`/`tradability`/`factor_search`/`audit_stale`)实跑确认 `ok=True`。顺带把 `decay_monitor` cron 改指向现代版(`scripts/ops/decay_monitor.py`,旧的 `scripts/research/decay_monitor.py` 范围只到部署的1条腿+自身有语法错,不再调用),范围扩到全部12个在册版本(原来 `run_active()` 结构性碰不到 `hq-momentum-hedged`/`large-cap-growth-hedged` 的 `-full` 版本);`current_deployment_identity()` 解除无保护调用(同 production_readiness.py 已有修法)。`run_nine_gates_all.py::VERSION_OVERRIDES` 补 `hq_momentum/v1.0-full`(原3个疑似漏审,核实后只有这1个是真缺口)。**意外收获**:解释器修复让脚本第一次真正跑到深处,揪出2个之前从未暴露过的问题——① `live_readiness.py`/`health_check.py`/`paper_trade.py` 三个 `decay_status.json` 老消费者用的是已废弃的单策略IC schema(`d['ic']`等),改 schema 后直接 `KeyError`,已同步改成读新的多版本 `strategies[]` 数组,已修复验证;② `cross_asset_leg_search` 暴露出真实卡在上面那条"部署清单漂移"待决项上(见上一条)。`bash scripts/test_all.sh` 全绿。
- [x] **illiquidity clean-v1 入册** — ✅ 已登记 `status=候选`(非在册,留待人确认)。**但补跑 PBO 后发现它不是"干净范本"**:`lineage_pbo` 算出 clean-v1 与 v1.0 日收益 corr=1.0(数学上同一序列,只差 leverage 标量,并非独立配方);9-Gate 全套(n_trials=6/7)passed_all=False。脚本 `factor_research/scratch/register_illiquidity_clean_v1.py`。详见下方"illiquidity 全家族重审"。
- [x] **#5 独立数据族隔离岛(股东行为+资金流)** — ✅ 已接进 autoresearch:`factors/shareholder.py`(holder_count_chg/holdertrade_net)+`factors/capital_flow.py`(large_order_net_ratio),注册进 `factory/autoresearch/registry.py::ALLOWED_FACTORS`(变异/初始化/LLM播种三路径共用同一词表,已验证可达)+ 新 LLM 主题"股东行为与资金流"(`services/actions/autoresearch_search.py::_ISLAND_THEMES`,需 islands≥5 才轮到,已把 `scheduled_factor_search.py` 的 islands 从3调到5)。**验真结论**:全市场 top25 多头下三者都不是 real_alpha,且与 illiquidity/size 簇相关0.66-0.83(疑似小盘选股漏斗,非数据无信息);收窄到大中盘(u300/u800)后独立IC反而走强(0.02→0.04)但组合夏普仍弱——信息可能真实存在但分散在横截面,top25集中持仓吃不到。结果存 `research_ledger`(run_id `e6e655401623899d`)。**下一步留白,需用户决定是否投入**:试 top50-100 更宽持仓或多空结构(不是简单调参,是新的持仓结构设计,基因组目前不支持搜索 top_n/long-short)。
- [ ] **三假货台账处置(ADR-017)** — ① `illiquidity-large-cap/v1.0` 退役/重分类(独立 IC=−0.084 反向、9-Gate 证据照抄小盘);② `industry-neglect-rotation/v1.3` 补独立 9-Gate(L2 复合 DSR/PBO)+ admission 标注「裸因子年化13.8%/回撤−60% 不达标,standalone 靠 MA16 overlay」(**注:ADR-020 已因 DSR=None 把 v1.3 由在册 standalone 降为「参考」,重分类部分已落,独立 9-Gate 补审仍欠**);③ `ai-compute-toc/v1.0` logic chain `ai_compute_toc_bottleneck` 降级 + desc 失效标注(机制三重证否)。草稿 `scratch/{illiq_largecap_governance,toc_honest_conclusion}_DRAFT.md`。**处置后从 `scripts/ci/check_registry_evidence.py::PENDING_REMEDIATION` 移除对应 key**(守卫会提示)。谁:走 workflow。
- [ ] **扩展 9-Gate runner 覆盖(ADR-020 §E 后续)** — `run_nine_gates_all.py` 仅支持 5 家族特定版本;30 个 nine_gate 空版本(autoresearch_*/small_cap_factor__window*/industry-neglect/size-low-vol/d-le-sc-hedged 等)**全无兼容 runner 或缺该版本 config 规格,现 0 个可审**。补审须为这些家族写配置驱动适配器(类比 `ILLIQ_SPECS`)或补 `VERSION_OVERRIDES`。优先级:低——全是候选/参考/退役,**非在册 standalone,不构成 DSR 治理缺口**(唯一要 DSR 的 status 已清零)。谁:研究侧按需。
- [x] **CLAUDE.md 扩写(宪法)** — ✅ ADR-017 的「9-Gate 证据自证」5 条已落为新宪法 P0 规则 `R-EVIDENCE-001`(并接 `check_registry_evidence.py` 守卫);文档矩阵已含 `LOOP_ENGINEERING.md` 指针。详见 ADR-019(宪法升级为规则编号治理系统)。
- [x] **防自欺地基集成 follow-ups** — ✅ ① `record_trials` 钩进 `apps/factory_cli.py::cmd_generate`(记新增候选数;factory/lines 经此入口);② island search 搜索窗截到 `<boundary`(`scheduled_factor_search.py` 载面板截断后传 close/volume/amount/forward_ret → 演化不触金库)。**残留**:promoted 候选的 9-Gate eval 仍载全样本,理想也应截 <boundary(NineGatesEvaluator 自带 OOS 逻辑,深改,留续办)。
- [x] **Loop 地基续建(§5.3/§5.4)+ 接线** — ✅ §5.3 `governance/marginal.py::marginal_alpha`;§5.4 `governance/decay.py::decay_check`。**已接**:① marginal_alpha 残差法接进 `workflow/promote.py::_run_marginal`(补 line3 raw-corr 方法的洞,根因#2;残差判冗余即建议 SHADOW);② `scripts/ops/decay_monitor.py` 定时衰减复测(实跑在册4策略全健康,illiq 滚动3年夏普2.276)。**待办**:decay_monitor 接周度 cron/launchd(命令给用户,不自动装系统任务)。

### 根因分析修复(用户提供的 6 项修复顺序;多 agent 共享工作树,我只取独立文件避冲突)
- [x] **#1 禁 force-promote 硬闸** — ✅ `scripts/ops/bulk_promote.py` 改硬闸(`force=False`+`run_nine_gate=True`+`run_marginal=True`,blanket auto-approve 默认关须 `BULK_AUTO_APPROVE=1`)+ 防回归守卫 `scripts/ci/check_no_force_promote.py`(AST 扫自动晋级脚本禁 force=True/run_marginal=False,接 test_all)。注:**未运行 bulk_promote**(写台账,运行须 workflow+用户)。
- [x] **#4 alpha/overlay 分账** — ✅ `governance/alpha_overlay.py::split_alpha_overlay`(裸因子=唯一 alpha 记账;overlay=full−bare 只记风险贡献;裸≈0但完整高→判 overlay 造假拒)。已接验真机 `strategy_truth_screen` 每行输出 `alpha_overlay_split`。21/21 测试绿。
- [ ] **#2 适应度方向归一 + 扣市场/book residual** — 🔧 部分:并行 agent 已修方向错位(novelty 在 direction-applied 面板算)+ 用 L0 edge + 加 corr_to_book 罚(默认关 corr_weight=0)。**残差法**(扣市场/book beta)已有 `governance.marginal_alpha` 并接进 workflow 准入,但**搜索 fitness 的 corr 罚仍是 raw 相关**(corr_weight=0 时不激活);要激活须用残差相关,待。
- [x] **#3a NW-ICIR 参与筛选** — ✅ `islands.py` fitness edge 从 raw `ICIR` 换成 `ICIR_nw`(NW 重叠校正,~3.5x 诚实量级;raw 仅留报告)。修「raw ICIR 淹没 novelty/turnover 项」。**注**:edge 量级变了 ~3.5x,fitness 权重(novelty 0.25/turnover 0.15)需经 **#6 A/B 重验**;在此之前搜索探索效率可能偏移,但产出仍过 L0-L3/9-Gate/holdout 硬闸,不会让垃圾入册。
- [ ] **#3b 真元级 walk-forward** — 周度调度仍走 `run_autoresearch_island_search`,非 `run_autoresearch_walk_forward`(演化只见 ≤cutoff、冠军 (cutoff,oos_end] 一次性 OOS)。现搜索窗已 holdout 截断(止血),但真元级 WF 待切换。
- [x] **#5 按独立数据族建隔离岛(真出路)** — ✅ 已接股东行为+资金流(详见上方"防自欺治理"节同名条目,含验真结论与下一步)。report_rc 卖方预测修正仍卡限速(1次/分钟,全量92小时)未碰。
- [ ] **#6 固定预算 A/B(旧 vs 修正后适应度,同 trial 数,比真样本外 residual Sharpe)** — 待 #2 完成后做;若仍无候选=确认当前 DSL 信息空间耗尽。

- [x] **产业基本面子系统 Phase 1 缺数据:补摄取资负表科目** — ✅ 已用内置 token(`data_lake/agent/tushare_config.json`)全量重取 balancesheet(5207 股/255097 行,新增 应收/应付/存货/应收票据/应付票据 5 列,旧列与行数零变化)。途中修了 `lake/sources/tushare.py::call` 限速重试 bug(40203「频率超限(200次/分钟)」未被「每分钟」分支匹配 → 误当致命崩;现匹配「频率超限」/「分钟」→ sleep 60s 重试,所有接口受益)。并在 `services/read/fundamentals.py` 修了"存量÷季度累计流量未年化 → 周转天数虚高 4 倍"(按报告期 ×12/月份年化)。汇川 300124 实测:BPI +0.20、CCC -12 天、DSO/DIO/DPO 135/118/265 天、定价权 0.73。注:2000 积分档 balancesheet 必填 ts_code,不支持 period 批量(vip),只能 by_stock。
- [ ] **产业基本面子系统 Phase 2** — 接入行业分类(`index_classify`/`stock_company` → `data_lake/meta/industry.parquet`);扩 `report_nlp_pipeline.py` 让 DeepSeek 把研报拆成本体因果链 `TransmissionNode`(SUPPLY/DEMAND/PRICE/MARGIN…)写 `research_signals/`;搬迁修复 `core/analysis/{analyst_framework,industry_ontology,bom_chain,data_quality}`(4 个坏原型,模块级 `Path` 未导入 + industry_ontology 违反 core→factory 铁律)到 `factory/{fundamental,ontology}/`;届时把 `check_layer_deps` 扩到覆盖 `core/analysis/`。行业景气预测 + 预期差机会榜接入 Agent/页面。
- [ ] **产业基本面子系统 Phase 3** — 按 `scripts/research/incubation_policy.py` 设计:本体预测分/预期差注册为 SHADOW 因子(不参与实盘权重)→ 影子 NAV → 9-Gate + DSR 审计 → 达标走 workflow 入册。

## 🧱 积分墙(per-interface 权限,非通用额度)
> 2000 积分通用额度(200/分钟 + 100k/天 per API)对 17 个核心维度绰绰有余;但下列是 **per-interface 更高积分要求**的特色接口,2000 档只给试用配额。
- [ ] **cyq_perf(筹码胜率)= 试用 5次/天** — **较值得升积分**:获利盘/平均成本/胜率与量价/size 低相关,真候选分散源。需按接口文档升档(通常 5000)。
- [ ] **limit_list_d(连板)= 试用 1次/小时** — 较不值得:连板情绪短线/噪声,与日频因子契合度低。
- `call()` 已对硬配额(X次/天/小时)fail-fast(不再白等 6×60s)。决策:**为 cyq_perf 升积分,还是两个都放弃**。

## 🟡 待决策(等用户拍板)
- [ ] **size-low-vol 是否加 exclude_star** — SHADOW 策略持 4/25 科创板;tradability 口径上该排除,但 688 在它身上加收益、夏普持平(不像小盘降夏普)。建议:缓到促 LIVE 时一起处理。来源:CNE6/688 ripple 审计。

## 🟢 规划中 / 下一批
- [x] **数据日更全链路收敛(基础设施建设)** — 目标：每个 China 交易日收盘后 30 分钟内，全市场 5200+ 只股票价量数据完整入库，信号/模拟盘自动更新，web 自动反映。✅①价量源已换 tushare(5082只/日，2 API calls)；✅②时区修复(`expected_trade_date` -9h 偏移 + `update_prices` china_now)；✅③launchd plist 已补 Weekday=1(周一)；✅④监控告警落地(`scripts/ops/notify.py`：日更 failed/partial_ok 推 Obsidian[`30.output/2.[A]inbox/ai_data`，按月滚动]+桌面通知+可插拔 Bark/邮件，per-day 去重+失败恢复报平安；接在 `scheduled_daily_update.py::maybe_alert` finally；开关走 `settings.yaml::notify`，密钥走 gitignored `data_lake/agent/notify_config.json`)。
- [ ] **本体驱动重构(ontology-driven refactor)** — 据 `factor_research/docs/ontology_glossary.md` 命名冲突清单(veto/composer/signal/zscore/regime/timing/filter等),设计概念→命名 taxonomy 并逐步重命名/拆分模块。当前仅完成术语基线确认,本任务为后续工作。
- [ ] **研报-NLP 赛道** — 缺 PDF 源。流程见 WORKFLOW #5:AG 浏览器抓巨潮/东财研报 PDF → `data_lake/research_pdf/` → opendataloader 解析 → DeepSeek 抽取 → 因子。工具可行性已验证(需 Java 已装)。建议轨:Antigravity 取数 + 我做处理端(处理端可先建骨架)。
- [ ] **社融 cn_sf** — 接口名错(非 cn_sf),待查正确名补进宏观层。
- [ ] **第一批新维度接入** — `block_trade`(大宗折价)+`top_list/top_inst`(龙虎榜机构净买)+`repurchase`(回购)+`pledge_stat`(质押率)；写入 `data_lake/institutional/`；详见 `docs/data_dimensions.md` §3.1
- [ ] **ETF 价格源修复** — `cross_asset/etf/` 现用 eastmoney push2his(clash 代理拦截)；改为 tushare `fund_daily`；5 只 ETF 统一日更接入 launchd
- [ ] **北向个股持仓替代方案** — `hk_hold` 已下架(停更 2024-08-16)；评估 `hsgt_top10`(沪深港通十大)作为持仓结构代理，或直接放弃个股层保留 `moneyflow_hsgt` 汇总
- [ ] **daily_basic/moneyflow 接入 launchd** — 当前滞后价量 2 天；加入 `scheduled_daily_update.py` 自动触发

## 🧱 积分墙 / 受限(per-interface 权限,需升积分)
> 2123 档不可用或不实际;同 cyq_perf。
- [ ] **report_rc(卖方盈利预测修正)** — 强 event alpha,但 **1次/分钟**:全量 5524 股 ≈ 92 小时(4 天),2123 不实际。升积分提速,或只抓近 1-2 年。

## ⚪ 已推迟 / 阻塞
- [ ] **income/balancesheet/cashflow 派生因子** — 三表已入库(anndate),但派生 Leverage/Quality 因子(真 B/P、债务/权益)尚未建因子。fina_indicator 已覆盖大部分比率,优先级低。

---

## 近期完成(可清理)
- [x] **⚡ 行动桌面三大独立看板激活与重组 (Ops Desk Dashboards)** — 激活并独立重构了`/candidates`、`/signals`和`/trade-plans`页面。支持展示 25 只因子推荐候选股与泡沫过滤说明、展示底层趋势偏离与 Regimes 择时指标、交易员签名授权委托锁定、CSV 批量委托单导出，并重构了总览页以保持台面极简化。
- [x] **P2 Python 工程化收敛(pyproject/测试入口/依赖锁)** — ⚙️ 新增 `factor_research/pyproject.toml` 统一 `pytest`/`ruff`/`mypy` 配置,加入 Apple Silicon venv 安装说明,并把 `requirements.txt` 运行时 direct deps 全部 pin 到当前版本。验证:`python3 -c "import tomllib; ..."`、`python3 tests/test_services_phase0.py`、`python3 tests/test_risk_phase3.py`。
- [x] **P2 风控页有效杠杆口径统一** — `services/read/risk.py` 改为优先读取最新 `signals/YYYY-MM-DD.json` 的 `band_exposure/leverage`,无信号时回退静态配置并在 note 中说明;新增单测覆盖 latest signal → risk current。验证:`python3 tests/test_risk_phase3.py`、`python3 tests/test_api_contracts.py`、`python3 tests/test_services_phase0.py`。
- [x] **测试 warning 噪音清理** — `engine/factor_analysis.py::calc_ic` 对常量截面先返回 NaN,避免 `ConstantInputWarning`;`tests/test_action_jobs_phase7.py` 改用 `httpx.ASGITransport` 直连 ASGI app,避免 Starlette `TestClient` 的 `httpx2` deprecation warning。验证:`python3 test_engine.py`、`python3 tests/test_action_jobs_phase7.py`、`bash scripts/test_all.sh`。
- [x] **P1 回测固定 `leverage` 参数口径修复** — `/backtest/run`、Web 回测页和生产默认展示移除可调固定杠杆;v3.1 明确为 PureTrend MA16 Band 动态敞口(0~1.5x),内部 `BacktestConfig.leverage=1.0` 只作为引擎基准。验证:`npm test`、`python3 tests/test_api_contracts.py`、`python3 tests/test_services_phase0.py`。
- [x] **P1 前后端契约 smoke 自动化** — 新增 `factor_research/tests/test_api_contracts.py`,校验 `/backtest/run` 不暴露 `leverage` 且 AutoResearch action endpoints 返回 `ActionJobView`;`scripts/test_all.sh` 已纳入该 smoke。验证:`python3 tests/test_api_contracts.py`。
- [x] **P0 前端写/重任务 Action Token 缺失修复** — `web/lib/api.ts` 增加 `/settings/action-token` 读取与 protected POST;Settings/AutoResearch 写接口统一带 `X-Action-Token`;新增 `web/lib/api.test.mjs` 覆盖 token 不进 body。验证:`npm test`、`npm run lint`、`npm run build`、`python3 tests/test_action_jobs_phase7.py`、`python3 tests/test_settings_phase6.py`。
- [x] **P0 AutoResearch 异步 Job 契约错配修复** — `web/lib/types.ts` 增加 `ActionJobView`;AutoResearch run/promote/search 前端改为提交 job 后轮询 `/experiments/jobs/{job_id}` 并按 `job.result` 渲染。验证:`npm test`、`npm run build`、`python3 tests/test_action_jobs_phase7.py`。
- [x] **价量数据日增量源切换 Tencent→Tushare** — `lake/sources/tushare_price.py` + `update_lake.py::update_prices()` 完成；token 落 `data_lake/agent/tushare_config.json` + plist env；实测 5082 只/日，launchd 周一补齐，06-15 全量 5188 只验证通过
- [x] tushare 17 维度入库(daily_basic/财务/资金/市场/事件/股东/指数,71M 行)
- [x] 科创板 688 volume 修复 + 小盘 exclude_star + v2.0 重登记
- [x] CNE6 风格中性化审计(真 Barra Size)
- [x] 便宜模型干苦力(DeepSeek)接通 + 实测 1/5 漏斗
- [x] 多 agent 系统级分工(MULTI_AGENT.md)+ 文档矩阵正交化(ADR-010)
- [x] 宏观时序层(cn_cpi/ppi/m + shibor + moneyflow_hsgt,防未来 lag,`load_macro`)
- [x] large-cap 容量 688 连带重算:虚高 768亿→真 5.62亿(-99%,137x),漏网补做
