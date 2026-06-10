# STATUS — 当前进度

> 更新:2026-06-10。任何 AI 进来先读 本文件 + [CLAUDE.md](CLAUDE.md)。

## 一句话

**2026-06-10**: 全系统模块解耦收尾(architecture)。
  · **回测唯一权威**: `core.backtest` 兼容层退场(→`core/_deprecated_backtest.py.bak`),全仓 90+ 文件迁移到 `core.engine`/`strategies.small_cap`/`factors.small_cap`/`engine.metrics`/`factors.utils`,0 导入方残留。指标逐位不变(strategy_lake/test_engine/run_daily 全验证)。
  · **配置源**: `app_config/settings.yaml` 落地;`StrategyConfig` 默认值修正为 illiquidity v3.0(原 small-cap-size/v2.0 已脱节)。
  · **探索→登记唯一通道**: 新增 `workflow/from_factory.py`(factory Hypothesis→workflow builder 适配器)+ `workflow/promote.py`(L3_PASSED→phase1合成审计→phase2/3→phase4 唯一登记) + `factory_cli promote` 子命令。打通后 factory pool 有 **7 个 L3_PASSED 候选**待 promote 入册。
  · **死代码清理**: 删 `factory/evaluator.py`(v1孤儿)+ `scripts/research/portfolio_combo.py`。
  · **research 归档**: 29 个死变体族(hmm_*/state_transition_*/mkt_diffusion_*/breadth_dd20_*/abcd_*)→ `scripts/research/archive/`。
  · **依赖守卫**: `scripts/ci/check_layer_deps.py`(AST 分层依赖 + 台账唯一写入口 + 禁 import 退场模块),接入 `scripts/test_all.sh`。

**2026-06-09**: 因子升级 v3.0 (SizeProxy→AmihudIlliq) + 生产链路修复。
  · **AmihudIlliq v3.0 LIVE**: |ret|/amount 公式, 全区间 +37.8%/-16.6%/1.99
  · **Alpha 框架融合**: Personal Alpha 因子框架搬入(factors/alpha/)
  · **DSR+PBO 接入工厂**: 统计验证层, 52候选最优SR=1.93显著(p≈0)
  · **生产环境修复**: launchd Python路径/时区/数据freshness三修
  · **v3.0 完整报告**: `reports/research/amihud_rotation_strategy_report.md`

**2026-06-08**: Band LIVE + HMM移除 + 债券轮动 + Composer + 不对称性审计。
**2026-06-07**: 专家审视 6 大盲区, Band 切 LIVE。
**2026-06-06**: v2.2 偷看退役, illiquidity v1.0 基线。

**2026-06-06**: v2.2 偷看退役, illiquidity v1.0 基线, A 股 alpha = 小盘/非流动单维度。

## 各层状态

| 层 | 状态 | 说明 |
|----|------|------|
| 数据基础设施 | ✅ | data_lake 全市场+全历史+含退市股 |
| 回测内核 | ✅ | BacktestEngine 统一接口 |
| **Regime 引擎** | ✅ | engine/regime.py 多维分类(trend/vol/liquidity/breadth) |
| **不对称性审计** | ✅ | factory/analysis/asymmetry_audit.py (gain/pain+up/down+sortino) |
| **Composer** | ✅ | engine/strategy_composer.py regime编排自动化搜索 |
| **Alpha 因子框架** | ✅ | factors/alpha/ (Base+Blend+Search+Transforms) |
| **DSR+PBO 验证** | ✅ | factory/analysis/wf_validator.py |
| 策略发现 | ✅ | workflow/ Phase1-4 + FactorSpace 搜索 |
| 策略库 | ✅ | illiquidity v3.0 (AmihudIlliq) LIVE + 债券轮动候选 |
| 生产入口 | ✅ | run_daily.py → AmihudIlliq + Band LIVE + regime轮动信号 |
| 模拟盘 | ✅ | paper_trade.py → illiquidity v1.0 + band_exposure |
| 失效监控 | ✅ | decay_monitor.py → illiquidity |
| 健康检查 | ✅ | health_check.py + 桌面通知 + Obsidian |
| 调度层 | ⏳ | launchd 待配置 |
| 跨资产轮动 | ⏳ | P5 生产集成待做, 目前手动执行 |

## 核心结论 (2026-06-08 更新)

### 1. 不对称收益是策略哲学

整套策略的底层逻辑不是最大化夏普，而是构建不对称收益结构。
每个组件都是这个目标的实现手段:

| 组件 | 不对称机制 |
|------|----------|
| illiquidity 因子 | 流动性风险补偿 + ST彩票溢价 |
| PureTrend 择时 | 趋势跟踪截断左尾 |
| Band 连续曝光 | 强趋势全开、弱趋势收缩 |
| **国债ETF轮动** | **熊市不躺现金** |

### 2. Band 取代 Binary 是结构性升级

- 回撤方差 -19%，极端回撤(≤-15%)天数 -44%
- 正收益方差+6% vs 负收益+3% → 好的波动 > 坏的波动
- **已切 LIVE** (2026-06-07)

### 3. HMM 在 PureTrend 之上纯属有害

4场景对照实验: HMM 年化-5.5pp, 回撤几乎无改善(-19.4% vs -19.1%)。
38.2%空仓率表明频繁误报。**已从生产移除。**

### 4. 跨资产轮动突破纯A股天花板

| | 纯权益(基线) | +国债ETF轮动 |
|--|:--:|:--:|
| 年化 | +21.2% | **+25.7%** |
| 最大回撤 | -18.8% | **-12.5%** |
| 夏普 | 1.22 | **1.90** |
| 100万→(2016-2025) | 806万 | **1279万(+59%)** |
| Walk-Forward 胜率 | — | **7/8** |

### 5. 工厂架构盲区确认 + 重构方案

工厂搜74候选仅1存活 → 根因是"全时段不差"假设排除了regime-conditional因子。
新架构P1-P4: Regime引擎→不对称审计→Leg Factory→Composer编排自动化。

## 策略库 (2026-06-08 更新)

### LIVE — 生产运行
```
■ illiquidity v3.0 (AmihudIlliq + Band LIVE)     +37.8%  -16.6%  1.99  当前生产 (全区间2010-2026)
  因子: AmihudIlliq |ret|/amount (window=20)
  择时: Band exposure 0~1.5x (PureTrend MA16)
  权重: top-25 等权, 20日调仓
  轮动: BEAR→511010国债ETF (Obsidian信号含建议)
  容量: ~2700万 (中等估计)
```

### CANDIDATE — 待 P5 自动化
```
■ AmihudIlliq + 国债轮动         +29.0%  -11.4%  1.73  2016-2025
  bull→AmihudIlliq全仓, bear→511010国债ETF
  待: 债券自动交易/paper_trade ETF支持
```

### RETIRED
```
■ SizeProxy v2.1                因子公式已升级, 终值低74%
■ illiquidity + HMM             年化-5.5pp, 回撤无改善
■ size-low-vol/size-earnings    边际负贡献
```

## workflow/ 发现流水线

```
Phase 1  合成数据数值穿越    5 项检查, 秒级, 8 核并行
Phase 2  不重叠三段回测      3 段+成本+相关性, 分钟级, 4 核并行
Phase 3  Walk-Forward       12 窗口滚动, 小时级, 顺序
Phase 4  自动注册+教训回流   去重机制, 可复现元信息
```

## 生产入口

```bash
python3 run_daily.py --no-update        # 出当日 illiquidity 信号
python3 scripts/ops/paper_trade.py      # 模拟盘 T+1 执行
python3 scripts/ops/health_check.py     # 健康检查 + 通知
python3 scripts/research/decay_monitor.py  # 失效监控
python3 workflow/explore.py             # 并行探索新策略
python3 apps/portfolio_cli.py --analyze # 组合分析
```

## 关键教训 (详见 LESSONS.md)

- **v2.2 偷看**: 缺 shift(1), T 日仓位用 T 日收益 → 50%→2.2%。任何行情信号必须验证 shift(1)。
- **PureTrend 是生存必需**: 无 PT 任何因子 DD >43%。PT 通用最优, 无例外。
- **真实盘 T+1 摩擦**: 回测高估 ~27%。illiquidity 回测 32%→真实 20%。
- **A 股 alpha 单维**: 45 候选 + 工厂 55 hyp, 唯一赢家是非流动性/小盘。基本面/低波/动量/资金面全灭。
- **信息→行动断层**(2026-06-07): 知道组合负贡献一周以上没动 LIVE。组合管理纪律=边际负→立即 SHADOW，不删除但停止吸纳。
- **MA16 = plateau 不是 spike**(2026-06-07): MA10-20 都 work，MA16 不是 magic number。轻度 in-sample tuning，不是 v2.2 那样的 bug。

## 关键产出

### 架构重构 (P1-P4)
- `engine/regime.py` — Regime引擎
- `engine/strategy_composer.py` — Composer编排自动化
- `factory/analysis/asymmetry_audit.py` — 不对称性审计
- `factory/analysis/wf_validator.py` — DSR+PBO验证层
- `factors/alpha/` — Personal Alpha因子框架(base/blend/search/transforms/builtins)
- `core/analysis/walk_forward.py` — Purged WF + DSR + PBO

### 研究报告
- `reports/research/amihud_rotation_strategy_report.md` — **v3.0 完整策略报告**
- `reports/research/illiquidity_strategy_report.md` — v2.1 策略报告

### 生产链路
- `run_daily.py` — v3.0 LIVE (AmihudIlliq + Band + regime轮动信号)
- `scripts/ops/paper_trade.py` — Obsidian操作卡片(含regime轮动建议)
- `scripts/ops/prod_health_check.py` — 生产环境全链路健康检查
- `scripts/ops/scheduled_daily_update.py` — launchd定时入口
- `lake/base.py` — 数据freshness检查修复

### 实验脚本
- `scripts/research/mvp_leg_factory.py` — Leg Factory MVP (28腿)
- `scripts/research/run_composer.py` — Composer实战
- `scripts/research/verify_timing_scenarios.py` — 4场景验证(HMM/Band)
- `scripts/research/band_yearly_review.py` — Band历年对比
- `scripts/research/top_n_sensitivity.py` — top_n敏感性
- `scripts/research/experiment_ts_weighting.py` — 时序仓位
- `scripts/research/experiment_multi_period_ic.py` — 多周期IC
- `scripts/research/factor_eval_framework.py` — 因子评价框架
- `scripts/research/experiment_factor_timing_pairing.py` — 因子×择时配对
- `scripts/research/asymmetry_retrospective.py` — 不对称性回顾审计
