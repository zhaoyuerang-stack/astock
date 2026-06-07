# STATUS — 当前进度

> 更新:2026-06-07。任何 AI 进来先读 本文件 + [CLAUDE.md](CLAUDE.md)。

## 一句话

**2026-06-07**: 建 Strategy Factory 流水线(L0/L1/L2/L3 + regime-aware marginal eval),工厂自家流水线给出独立证据印证"A 股 alpha 单维度";**清理 LIVE 集合:size-low-vol/size-earnings 转 SHADOW**(边际负贡献-0.120/-0.277),组合 Sharpe 实测 1.60→1.89(+18%);MA16 grid 测试确认 plateau 不是 magic number;**Band timing 发现 — 连续 dist 信号代替 binary,Calmar 1.89→2.42 (+28%) Band SHADOW 跟踪中**。

**2026-06-06**: v2.2 偷看退役, 建 workflow 自动化流水线, 三轮探索 45 候选, illiquidity v1.0 成为生产基线, PureTrend MA16 证实为通用最优开关, A 股日频 alpha = 小盘/非流动单维度。

## 各层状态

| 层 | 状态 | 说明 |
|----|------|------|
| 数据基础设施 | ✅ | data_lake 全市场+全历史+含退市股 |
| 回测内核 | ✅ | BacktestEngine 统一接口 |
| 策略发现 | ✅ | workflow/ Phase1-4 + explore.py 并行探索 |
| 策略库 | ✅ | 4 家族 9 版本 |
| 生产入口 | ✅ | run_daily.py → illiquidity v1.0 |
| 模拟盘 | ✅ | paper_trade.py → illiquidity v1.0 |
| 失效监控 | ✅ | decay_monitor.py → illiquidity |
| 健康检查 | ✅ | health_check.py + 桌面通知 + Obsidian |
| 组合层 | ✅ | portfolio/ 3 算法 + 贡献分解 |
| 调度层 | ⏳ | launchd 待配置 |

## 今日核心结论

### 1. A 股日频 alpha 是单维度的

三轮探索 45 候选 × 11 生态位 → 全部收敛在小盘/非流动维度。
基本面/低波/动量/资金面/量价/行业内 → 全灭。
不同因子只是不同篮子装同一个因子。

### 2. PureTrend MA16 是生存必需，不是可选开关

8 策略在无择时下测试：回撤全部 43-86%。
PureTrend 用 ~2% 年化代价换 40+pp 回撤保护。
6 种备选开关（宏观 7 通道/早期退出/低波轮动/PT×Macro）全部不如 PureTrend。

### 3. 组合多元化在纯 A 股权益内不可行

4 策略相关性 0.81-0.997。等权组合夏普 1.33 < 单 illiquidity 1.35。
真正的多元化需要跨资产（债券/商品/港股）。

## 策略库 (2026-06-07 更新)

### ACTIVE — 进入组合
```
■ illiquidity v1.0        +32.3%  -15.4%  1.78  生产基线
  v1.1 Top50             +30.0%  -18.0%  1.65
  v1.2 周频              +30.0%  -22.0%  1.55
  v1.3 +size             +28.0%  -16.0%  1.55
■ small-cap-size v2.0    +22.2%  -20.0%  1.38  组合互补 (marginal +0.104)
```

### SHADOW — 不进入组合 (2026-06-07 实测组合层边际负贡献)
```
■ size-low-vol v1.0      +19.2%  -20.0%  1.27  marginal -0.120
  v1.1                   +19.3%  -20.0%  1.27  marginal -0.120 (同质)
■ size-earnings v1.0     +15.1%  -18.3%  1.05  marginal -0.277 (最严重)
```

### 当前组合 (2 ACTIVE)
```
LIVE 现在 : risk_parity(illiq + small-cap) Binary timing 1.25x
            annual +29.3% / Sharpe +1.89 / maxdd -13.7% / calmar +2.14

SHADOW    : 同 risk_parity 但用 Band timing 1.0x (dist 驱动 [0, 1.5])
            annual +28.5% / Sharpe +1.86 / maxdd -11.8% / calmar +2.42 (+13%)
            signals/ 含 shadow_band_exposure 字段 (since 2026-06-07)
            review : python3 scripts/research/band_shadow_review.py --update
            30 日后 NAV 实证后决定是否正式切换 LIVE timing
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

## 今日产出 (2026-06-07)

- `factor_research/factory/` — Strategy Factory 完整流水线 (本体+池+L0/L1/L2/L3+marginal)
- `factor_research/factors/microstructure.py` — 6 个新 alpha 类型
- `factor_research/portfolio/strategy_runners.py` — 加 status (ACTIVE/SHADOW) 字段
- `factor_research/apps/factory_cli.py` — 工厂主入口 12 命令
- `factor_research/apps/contribution_dashboard.py` — 组合贡献分解
- `factor_research/portfolio/regime.py` + `portfolio/marginal.py` (G 合并版本) — 5-regime + LIVE_D
- LIVE 集合清理: 4 → 2 ACTIVE，预期组合 Sharpe +18%
