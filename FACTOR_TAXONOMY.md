# FACTOR TAXONOMY — 因子分类体系

> 所有因子的正式分类。新增因子必须先归类。agent 接任务时按此表选工具。

---

## 分类定义

| 类别 | 英文 | 用途 | 独立 IC | 评估路径 | 示例 |
|------|------|------|:--:|------|------|
| **Alpha** | Stock Selection | 截面排序选股 | ✅ 必须有 | L0-L3 factory → 9-Gate → register | size60 |
| **Veto** | Orthogonal Filter | 排除特定股票, 挂在 Alpha 上 | ❌ 不需要 | 边际贡献协议 (ΔSh) | pledge |
| **Timing** | Exposure Control | 仓位缩放/开关 | ❌ 不需要 | 叠加在 Alpha 上测 ΔSh | MA16 |
| **Cross-asset** | Non-A-share | 跨资产防御/轮动 | N/A | 组合层面评估 | 国债 ETF |
| **Falsified** | Proven Invalid | 测过无效, 存档防重试 | — | 已归档 | alpha101 |

---

## Alpha（选股因子）

> 必须能独立产生截面 IC，走完整 L0-L3 + 9-Gate + register 流程。

| 因子 | 公式 | ICIR | 状态 | 备注 |
|------|------|:---:|:--:|------|
| **size60** | `-log(amount.rolling(60).mean())` | 0.59 | 核心 | A 股唯一确认 alpha |
| Amihud illiq | `\|ret\|/amount, rolling(20)` | 0.47 | 参考 | 与 size60 MI 距离 1.34, 同一信息源 |
| size-low-vol | `0.5*size60 + 0.5*lowvol` | 0.60 | 参考 | size 权重碾压 lowvol, ≈size60 换皮 |
| small-cap-size 家族 | size60 多窗口 (20/30/45/60/90/120/252) | 0.59 | 参考 | 7 个变体全是同一因子换窗口 |
| size-earnings | `0.5*size60 + 0.5*npy_yoy` | — | 参考 | DSR 不显著 |

## Veto（正交否决器）

> 截面相关 < 0.1，不能 standalone，只能挂在 Alpha 上做排除。评估用边际贡献协议（同引擎同成本、带/不带、只报 Δ）。

| 否决器 | ΔSh | 截面相关 | 逐年 | OOS | 排除逻辑 |
|--------|:---:|:------:|:---:|:--:|------|
| **pledge 高质押30%** | **+0.27** | -0.03 | 5/6年正 | +0.19 | 排除 pledge_ratio top 30% |
| 行业景气度 Z<-1 | +0.10 | 0.01 | 6/6年正 | +0.10 | 排除 60日资金流 z-score < -1 的行业 |

## Timing（仓位控制）

> 不选股，只控制 exposure。直接叠加在 Alpha 收益上测 ΔSh。

| 增强件 | ΔSh | 原理 | 参数 |
|--------|:---:|------|------|
| **MA16 PureTrend** | +0.12 | 价格跌破 16 日均线 → 空仓 | MA window=16 |
| **Band 连续缩放** | Calmar +13% | dist 偏离度 → 连续仓位 0~1.5x | `1+dist×8, clamped [0,1.5]` |
| **波动率加速度** | +0.05 | 波动率飙升 → 降仓 | 63d vol diff(21d) z-score |
| **突破20日高5d** | +0.35 (微盘) | 指数突破20日高点后持5天 (T+1修正后) | hold=5d, idx+1起始 |
| **国债 ETF 511010** | +0.68 | 熊市空仓时资金进国债 | 年化~3% |

## Cross-asset（跨资产）

| 资产 | 作用 | 相关 |
|------|------|:--:|
| 国债 ETF 511010 | 防御腿, 熊市替代现金 | -0.2~0.3 |
| HK 港股 | corr 0.25, 但单腿 Sh<0.5 → 拖累组合 | 0.25 |

## Falsified（已证伪, 勿重试）

## 里程碑 (2026-07-02)

**size60+pledge+MA16 首次通过 Gate 5** (2026-07-01) — DD=-17.5% 首次压到 20% 入册线以下，8/10门通过。

**突破20日高修正** (2026-07-02) — 初版含未来函数(`signal[idx]`当天生效)，修正后改善缩水，跨宇宙通用不成立。微盘仍有效(+0.35 Sh)但量级大幅缩水。

| 因子/增强件 | 测试结果 | 死因 |
|------------|:------:|------|
| alpha101 全部 32 因子 | Sh=0.26-0.38 standalone | alpha 在双尾价差, long-only 无法收割 |
| alpha101 否决器 | ΔSh=+0.03 | 边际太小, 无效 |
| block_trade 大宗折价排除 | ΔSh=-0.13 | 反向 — 折价大宗=买入机会 |
| inst 龙虎榜机构净卖排除 | ΔSh=-0.62 (PIT 修正后) | look-ahead 假象 |
| holders 机构减持排除 | ΔSh=-0.07 | 反向 — 机构卖=微盘抄底信号 |
| loser_veto_reversal | ΔSh=-0.06 | 杀掉了宿主自己的 alpha |
| ST 排除 | 负效果 | ST 溢价是 alpha 来源, 排除=砍 alpha |
| 大盘 illiq / 成长 / 质量 / 动量 | Sh<0.35 | A 股大盘池无 alpha |
| roc-yc | ICIR≈0 | 无预测力 |
| d-le-sc-hedged | 因子为空 | 不可复现 |

## 待评估

| 因子 | 数据源 | 待做 |
|------|--------|------|
| top10_holders | tushare (128万行) | PIT 否决器测试 |
| block_trade | tushare (11万行) | PIT 否决器测试 (已初步证伪, 需确认) |

---

## 使用规则

1. **新增因子必须先归类** — Alpha / Veto / Timing / Cross-asset 四选一
2. **Veto 不能单独评估** — 必须遵守边际贡献协议 (同引擎同成本、带/不带、只报 Δ)
3. **Falsified 里的不要再试** — 除非有新的数据源或方法突破
4. **Agent 接任务时按分类选工具**：
   - "找新 alpha" → 走 Alpha 流程 (L0-L3 factory)
   - "改善现有策略" → 先查 Veto + Timing 表, 找未试过的增强件
   - "问某个因子能不能用" → 查 Falsified 表, 已死直接回答"已证伪"
