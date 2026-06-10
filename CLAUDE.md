# A股全市场因子量化研究

> 给 AI 的**操作宪法(精简)**。系统设计/架构 → [SPEC.md](SPEC.md);分阶段路线 → [ROADMAP.md](ROADMAP.md);当前进度 → [STATUS.md](STATUS.md);踩过的坑 → [LESSONS.md](LESSONS.md)(+ auto-memory)。代码与操作手册在 `factor_research/`。数据基础设施详情 → `factor_research/docs/data_infrastructure.md` + `factor_research/data_lake/README.md`。
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
```

## 工作约定
- 新母策略先 `register_family(...)` 声明假设/失效信号,再 `register(family, version, ...)` 登记版本(两层 schema 见 SPEC)。
- 回测交付三段:样本内(2018-2026)/ 样本外(2023-2026)/ 压力测试(2010-2026)。
- 实盘折扣:费率见上表;另评估 小盘容量、停牌/涨跌停、组合换手。
- 已 git 化:重要阶段改动用提交固定;数据湖和大体量运行产物不入库。
- 改了架构/进度,顺手更新 SPEC.md / STATUS.md;踩了坑记 LESSONS.md。

## 架构铁律(模块解耦,违反 = CI 报错)
单向依赖链:`data(lake) → factors → core.engine → {strategies, factory/workflow} → registry → production`。
- **回测唯一权威 = `core.engine.BacktestEngine`**。`core.backtest` 已退场(`core/_deprecated_backtest.py.bak`),禁止再 import;用 `strategies.small_cap` / `factors.small_cap` / `engine.metrics` / `factors.utils` 的 canonical 路径。
- **配置走 `app_config/settings.yaml`**(`get_settings()`),勿散落硬编码。
- **台账唯一写入口 = `strategy_registry.register_family/register`**(即 `workflow/phase4_register`);任何代码不得直写 `strategy_versions.json`。
- **候选→登记唯一通道 = `workflow` phase1~4**。factory(`factory/lines`)负责生成+L0~L3 廉价筛选;L3_PASSED 经 `workflow/promote.py`(或 `python3 apps/factory_cli.py promote`)走 phase1 合成防未来审计 → phase2/3 → phase4 登记。`phase1_synthetic` 是防未来铁律的唯一机械执行点。
- **生产层(run_daily 等)禁止 import `factory.*`/`scripts.research.*`/`workflow.*`**。
- 守卫:`python3 scripts/ci/check_layer_deps.py`(已接入 `scripts/test_all.sh`)。
