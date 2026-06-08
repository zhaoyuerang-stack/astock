# STATUS — 当前进度

> 更新:2026-06-08。任何 AI 进来先读 本文件 + [CLAUDE.md](CLAUDE.md)。

## 一句话

**2026-06-08**: 两日密集探索→架构重构(P1-P4)。
  · **Band LIVE + HMM 移除**: 回撤方差-19%, 极端回撤-44%, 年化+5.5pp
  · **国债 ETF 轮动发现**: 熊市不躺现金→换债券, 100万→1279万 vs 基线 806万(+59%)
  · **Composer 编排自动化**: 自动搜索最优 regime 组合, 输出 JSON 策略定义
  · **完整研究报告**: `reports/research/illiquidity_strategy_report.md` (公式+WF+IC+复现清单)
  · **策略哲学确立**: 不对称收益框架, 正收益端厚度 > 负收益端厚度

**2026-06-07 晚**: 专家审视 6 大盲区 → Phase 1 Quick Wins 双交付: Band 切 LIVE / 执行优化 PoC.

**2026-06-06**: v2.2 偷看退役, illiquidity v1.0 基线, A 股 alpha = 小盘/非流动单维度。

## 各层状态

| 层 | 状态 | 说明 |
|----|------|------|
| 数据基础设施 | ✅ | data_lake 全市场+全历史+含退市股 |
| 回测内核 | ✅ | BacktestEngine 统一接口 |
| **Regime 引擎** | ✅ | engine/regime.py 多维分类(trend/vol/liquidity/breadth) |
| **不对称性审计** | ✅ | factory/analysis/asymmetry_audit.py (gain/pain+up/down+sortino) |
| **Composer** | ✅ | engine/strategy_composer.py regime编排自动化搜索 |
| 策略发现 | ✅ | workflow/ Phase1-4 + Leg Factory MVP |
| 策略库 | ✅ | illiquidity v1.0 生产基线 + 债券轮动(v2.0候选) |
| 生产入口 | ✅ | run_daily.py → Band LIVE (动态0~1.5x), HMM已移除 |
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
■ illiquidity v1.0 (Band LIVE)    +25.0%  -17.7%  1.50  当前生产
  择时: Band exposure 0~1.5x (PureTrend MA16)
  权重: top-25 等权, 20日调仓
```

### CANDIDATE — 待验证上线
```
■ illiquidity + 国债轮动 v2.0     +25.7%  -12.5%  1.90  Composer最优
  bull→illiq_w60全仓, bear→511010国债ETF
  WF 7/8胜, 100万→1279万(2016-2025)
  待: P5生产集成 / 真实债券交易测试
```

### RETIRED
```
■ illiquidity + HMM             已移除  年化-5.5pp, 回撤无改善
■ size-low-vol/size-earnings    SHADOW  边际负贡献
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

## 关键产出 (2026-06-08)

### 架构重构
- `engine/regime.py` — Regime引擎 (多维分类: trend/vol/liquidity/breadth)
- `engine/strategy_composer.py` — 策略编排器 (regime组合自动化搜索)
- `factory/analysis/asymmetry_audit.py` — 不对称性审计 (gain/pain+up/down+sortino)

### 研究报告
- `reports/research/illiquidity_strategy_report.md` — 完整策略报告 (公式+WF+IC+复现清单)

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

### 生产改动
- `run_daily.py` — Band LIVE + HMM移除
- `app_config/settings.py` — HMM配置清理
