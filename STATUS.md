# STATUS — 当前进度

> 更新:2026-06-06。任何 AI 进来先读 本文件 + [CLAUDE.md](CLAUDE.md);系统设计见 [SPEC.md](SPEC.md)。

## 一句话

**2026-06-06 重大升级**: 发现并修复 v2.2 偷看 bug→退役; 建立 `workflow/` 自动化策略发现流水线 (Phase 1-4); 三轮并行探索 45 候选×11 生态位, **illiquidity v1.0 全面超越 v2.0 → 成为新生产基线**; 策略库扩至 4 家族 9 版本; `run_daily.py` + `paper_trade.py` 已切换 illiquidity。

## 各层状态

| 层 | 状态 | 说明 |
|----|------|------|
| 数据基础设施 | ✅ | data_lake 全市场+全历史+含退市股。amount=volume×100×不复权价 |
| 统一回测内核 `core/` | ✅ | BacktestEngine 统一接口; Phase-2 迁移完成 |
| 策略发现 `workflow/` | ✅ | Phase1 合成数据穿越→Phase2 三段回测→Phase3 WF→Phase4 注册+教训回流 |
| 策略库 | ✅ | 4 家族 9 版本 (详情见下) |
| 有效策略管理 | ✅ | 台账 + decay_monitor + paper_trade(T+1 真实盘) |
| 生产入口 | ✅ | `run_daily.py` → illiquidity v1.0 |
| 中央调度层 | ⏳ | launchd 每日增量+周维护 |
| 组合层 | ○ | 未建 |
| 展示层 | ○ | 未建 |

## 策略库 (详见 `strategy_versions.json`)

```
■ illiquidity (Amihud 非流动性)          ← 生产基线
  v1.0  基准 20d  +32.3%  -15.4%  1.78
  v1.1  Top50    +30.0%  -18.0%  1.65  夏普最高
  v1.2  周频调仓  +30.0%  -22.0%  1.55
  v1.3  +size   +28.0%  -16.0%  1.55  回撤最小

■ size-low-vol (小盘低波)                ← 新
  v1.0  20d低波  +19.2%  -20.0%  1.27
  v1.1  40d低波  +19.3%  -20.0%  1.27

■ size-earnings (小盘+盈利增长)          ← 防御
  v1.0          +15.1%  -18.3%  1.05

■ small-cap-size (参考)
  v2.0          +22.2%  -20.0%  1.38  被超越
```

## workflow/ 策略发现流水线

```
Phase 1  合成数据数值穿越    5项检查, 秒级, 并行
Phase 2  不重叠三段回测      3段+成本+相关性, 分钟级, 并行
Phase 3  Walk-Forward       12窗口滚动, 小时级, 顺序
Phase 4  自动注册+教训回流   去重机制, 可复现元信息
```

三轮探索: 45 候选 → 11 生态位 → 9 在册版本。核心发现: A 股 alpha 高度集中于小盘/非流动性维度, 不同因子只是不同篮子装同一个因子。

## 生产入口

```bash
python3 run_daily.py --no-update   # 出当日 illiquidity 信号
python3 strategy_registry.py       # 策略台账对比表
python3 workflow/explore.py        # 并行探索新策略
```

## 关键教训 (详见 LESSONS.md)

- **v2.2 偷看**: `exposure = condition.astype(float)` 缺 `shift(1)`, T 日仓位用 T 日收益 → 50%假年化。任何涉及当日行情数据的信号必须验证 shift(1)。
- **真实盘 T+1 摩擦**: 回测收盘撮合高估 ~27%。illiquidity 回测 32.3%→真实 20.0%, v2.0 回测 22.2%→真实 17.5%。
- **A 股 alpha 高度集中**: 基本面/资金面/低波/动量 全灭。只有非流动性/小盘维度有统计显著性。
