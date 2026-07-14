# PLAN — paper 多账户并行实测闭环(WS-D 执行侧,R-PROD-001 落地)

> 状态:owner 已指示执行(2026-07-10)。对应 TASKS.md「【WS-D 执行侧】paper 多账户并行实测绑定」。
> 目标:补上产品形态最后一块建设型拼图——**排名靠前的 top-N 策略自动并行模拟盘 + 桌面端并排展示实测净值/回撤/回测偏差**(「不下单 ≠ 不实测」,R-PROD-001)。
> 铁边界:零真金、T+1、永不自动真实下单;排名只消费后端持久化产物,不得前端重算(R-PROD-001);**绝不发明第二套信号/回测引擎**(R-BT-001)。

---

## 0. 现状事实(2026-07-10 核实)

| 组件 | 现状 | 对本计划的含义 |
| --- | --- | --- |
| `portfolio/paper_engine.py`(394行) | 单账户:模块级 `ACCOUNT_FP = paper/account.json`;但成交原语已齐(`get_fill_price` T+1 开盘价/涨跌停 `buyable_open`/`sellable_open`/`execute_to_target`/`valuation`/`upsert_nav`/`append_trades`) | 原语**参数化复用**(注入账户路径),不重写;legacy 单账户入口保持行为不变(生产机有真实 paper 状态) |
| `reports/research/portfolio_recompose.json` | 周度持久化,含 `paper_candidates`(top-N version key 列表,RANKING_VERSION 锚定,>14 天过期口径已有) | 多账户 provisioning 的**唯一名单来源**;stale 则 fail-closed |
| `strategies/executable.py::build_executable_strategy(spec, prices)` + `strategies/catalog.py` | canonical 逐日信号路径,`run_daily.py` 生产同款;`UnsupportedStrategyComponent` 对不可执行配置显式抛错 | 每账户信号**只走这条路**;台账 config → spec 不可执行的版本 = 显式 `blocked(no_executable_spec)`,不发明旁路 |
| `services/read/paper.py` | 单账户三视图(trade_plan/paper_trades/nav_curve),web PlanCard/dashboard 已消费 | 多账户读层**另立新文件**,不动既有契约(latest_signal 等命名域是前端契约,勿改名) |
| worktree 环境 | 无数据湖价格、无 paper 真实状态 | 全部测试 hermetic 合成面板;真实流验收留生产机(见 T6) |

## 1. 任务分解(每 T 一个独立 commit)

### T1 — 引擎原语参数化(不改行为)
`paper_engine.py` 把模块级 `ACCOUNT_FP`/nav/trades 路径重构为可注入参数(默认值=现路径),legacy 调用方(`scripts/ops/paper_trade.py`、`run_daily.py` 若有)零改动。
**对抗验收**:既有 paper 相关测试零修改全过;对 legacy 入口做行为 parity(合成账本上重构前后输出逐字段相同)。

### T2 — 多账户管理器 `portfolio/paper_accounts.py`
- 账户 = 一个策略版本,状态目录 `paper/accounts/<family__version>/{account.json,trades.csv,nav.csv}`(复用单账户文件格式)。
- `provision_from_recompose()`:读 recompose 持久化名单;**stale(>14天)/缺失 → 拒绝 provision 并给可读状态**;新上榜开户(初始资金统一常量);下榜**冻结不删**(退役纪律:历史账本/NAV 永久保留,状态=frozen)。
- `update_all(date)`:每活跃账户经台账 config → `build_executable_strategy` 出目标持仓 → 复用 T1 原语 T+1 成交与估值;版本配置不可执行 → 账户状态 `blocked(no_executable_spec)`,不产假 NAV;缺价数据 → `degraded` 显式降级。
- 与部署解耦:不读 `deployments/production.json`,不碰生产信号。
**对抗验收**:① stale 名单真拒(provision=0+状态可读);② 账本隔离(A 账户成交不得改变 B 的现金/持仓/NAV——共享状态注入变异必须被测试抓住);③ 无规格版本诚实 blocked;④ 确定性(同输入两跑账本逐字节同);⑤ 下榜冻结后历史不可变。

### T3 — 日更入口 + 调度旁路
`scripts/ops/paper_accounts_update.py`:provision + update_all + 状态摘要落 `paper/accounts/summary.json`;挂 `scheduled_daily_update.py` **研究旁路**(失败不标日更 failed,与既有旁路同款)。分层守卫若需 registry 只读例外,按 `decay_monitor`/`scheduled_portfolio_recompose` 既有先例留痕。

### T4 — 读层 + API
`services/read/paper_accounts.py`(新,不动 `paper.py`):每账户 NAV 序列/回撤/持仓摘要/状态(active|frozen|blocked|degraded)+ **回测偏差**(paper NAV vs 台账该版本回测收益同窗对比:累计偏差、跟踪差,窗=账户存续期);契约进 `contracts/`;API 新 router `GET /paper-accounts`。三态诚实:有账户 / 名单健康但空 / 名单不可读禁称无事。
**对抗验收**:偏差计算对合成数据手算核对;源不可读显式 error 态(不静默空数组)。

### T5 — 桌面端并排展示
先读 `web/CLAUDE.md` + `WEB_DESIGN.md` + `DECISION_COCKPITS.md`,按决策归属放置(预期落点:dashboard 今日操作台或 strategy-registry,以 DECISION_COCKPITS 判定为准;若新增区块须服务「该不该把某策略推向真仓」这个决策)。
- 并排卡片/表:每候选实测 NAV 曲线、回撤、回测偏差、状态徽章;**顺序=后端产物顺序,禁前端重排名**(R-PROD-001)。
- 页首 StatusBanner 综合裁决(既有约定);空名单/stale → 诚实空态(「无可实测策略/名单过期」),禁假绿禁硬凑。
**对抗验收**:web 组件测试含——前端重排名必失败(顺序断言)、stale 显式呈现、空态不渲染假卡片;tsc/lint/既有测试零新增失败(开发期不跑 build)。

### T6 — RUNBOOK 生产机验收清单 + 收账
- `RUNBOOK.md` 增「paper 多账户上线验收」小节:生产机步骤(真实 recompose 名单 provision → 连续 2 个交易日日更 → 核对 legacy 单账户 paper 流零 diff → web 实数据目检),明确**人验收**。
- STATUS.md 一句话;TASKS.md WS-D 执行侧条目更新(代码侧完成,生产机验收待人)。

## 2. 显式非目标
- 不改 recompose 排名口径(RANKING_VERSION 不 bump)、不改成本/回测/入册规则、不碰 `deployments/`、不动 legacy 单账户契约与 `services/read/paper.py`。
- 不在本 worktree 跑任何真实数据;不自动安装 launchd/cron(命令写 RUNBOOK 留人执行)。
- 收益门槛/排名不得为「让某策略上榜」调整(R-OBJECTIVE-001)。

## 3. 停止条件
- T1 legacy parity 做不平(生产 paper 状态兼容风险)→ 停,不硬改。
- canonical 执行规格对现候选名单**多数**版本不可用 → 完成 fail-closed 表达后停,报告缺口(补规格是研究侧任务,不得自造引擎)。
- 同错两次/循环超 5 次/他人未提交改动出现。

## 4. 预估
T1 1h → T2 3h → T3 1h → T4 2h → T5 3h → T6 30min,合计 ~10h。完成后产品建设期封顶,后续工时按元系统冻结令归研究产出。
