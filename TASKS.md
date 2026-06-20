# TASKS — 开放任务 backlog

> 单一真相源:**所有未完成的可执行任务**。其余文档(STATUS/对话)只记历史/状态,开放任务一律落这里,防遗忘。
> 完成即移到「近期完成」或删除。新任务带:来源 + 上下文 + 谁能做。

## 🔴 进行中 / 优先
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
