# STATUS — 当前进度

> 更新:2026-06-02。任何 AI 进来先读 本文件 + [CLAUDE.md](CLAUDE.md);系统设计见 [SPEC.md](SPEC.md)。

## 一句话
阶段 0 已关闭:数据基础设施 + 统一 `core/` 回测内核 + 两层台账已建,旧 `data_full/data` 已清理。当前进入**阶段 1 多目标工厂化**;在册母策略仅 `small-cap-size`,真实成本口径未达项目级目标。

## 各层状态
| 层 | 状态 | 说明 |
|----|------|------|
| 数据基础设施 | ✅ | data_lake 全市场+全历史+含退市股,质量 ~99.9%;旧 data_full/data 已删 |
| 统一回测内核 `core/` | ✅ | data_lake + 小盘因子/择时 + 真实换手成本 + 融资成本 |
| 策略工厂 | ⏳ | 阶段 1.1 最小骨架;阶段 1.2 网格;阶段 1.3 NSGA-II;阶段 1.4 生态位;阶段 1.5 审计+孵化池;阶段 1.6 岛屿编排;候选验收未达 |
| 有效策略管理 | ✅台账 / ○监控 | 两层台账已建;失效信号还是文本、无定量阈值 |
| 中央调度层 | ○ | 未建 |
| 组合层 | ○ | 未建 |
| 展示层 | ○ | 未建 |

## 在册策略(详见 `strategy_versions.json`)
- `small-cap-size / v2.0`(data_lake 2018-2026,真实成本):年化 **21.2%** / 回撤 **-16.2%**,**未达 35%/15% 项目目标**,status=在册。
- v1.0(data_full)幸存者偏差水分 → 参考;v2.1 全历史压力测试 → 参考。

## 当前阶段
**阶段 1 — 多目标策略工厂化**。完整路线见 [ROADMAP.md](ROADMAP.md)。
- 已完成 1.1: `factory/` 最小策略工厂骨架,可评估候选并输出 `reports/factory_stage1_1.json`。
- 已完成 1.2: `factory/run_factory.py --mode grid` 可做确定性批量扫描,输出 `reports/factory_stage1_2.json`;Pareto 先过正收益/正 Sharpe/回撤/OOS 基础门槛。
- 已完成 1.3: `factory/run_factory.py --mode nsga2` 可跑最小 NSGA-II 多目标搜索,输出 `reports/factory_stage1_3.json` 和 generation history。
- 已完成 1.4: `--niche non_size/reversal_liquidity/quality_location` 支持生态位搜索,并输出 `*_review.json` 复核清单。
- 已完成 1.5: `factory/review_shortlist.py` 可对 review shortlist 做 2018/2023/2010 三段复测 + 成本上浮 50% 敏感性 + `registry_precheck`;同时标注 `incubate` 弱候选。
- 当前结论:`reports/factory_stage1_5_non_size_audit.json` 中 8 个 non-size 小样本候选均未通过台账预审,主要败在压力回撤和成本上浮。
- 已完成 1.6: `factory/run_islands.py` 可跑隔离岛屿,每岛独立 niche/seed/种群/输出,汇总 `registry_precheck=true` 为 `reports/islands/candidate_batch.json`,汇总 `incubate=true` 为 `reports/islands/incubation_pool.json`。
- 当前结论:两岛小规模搜索 `registry_precheck=0`,`candidate_batch.json` 为空,**尚未满足 ≥2 个非 small-cap 低相关候选母策略**。
- 下一焦点:扩大岛屿长跑和因子池,但继续只保留 `registry_precheck=true` 的候选。
