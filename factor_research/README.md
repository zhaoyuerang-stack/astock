# 因子研究系统操作手册

这个目录是一套 A 股因子研究、数据校验和策略运行系统。当前主线已经迁移到 `data_lake/` 真实口径：

- 策略：小盘 60 日成交额因子 + 小盘股等权指数择时 + 1.25 倍杠杆
- 目标：年化收益 >= 35%，最大回撤 <= 15%
- 旧口径结果：`data_full` 年化约 40.4%，但含幸存者偏差水分
- 真实成本基线：`data_lake` 2018-2026 年化约 21.2%，最大回撤约 -16.2%
- 阶段状态：阶段 0 已关闭；下一步进入阶段 1 多目标工厂化
- 版本登记：`strategy_versions.json`

## 目录说明

- `run_daily.py`：每日生产入口，更新数据、校验、生成信号和持仓 JSON。
- `strategy_lake.py`：真实口径策略复测入口。
- `validate_final.py`：全市场日线数据质量校验入口。
- `test_load_lake.py`：轻量验证数据湖加载层。
- `strategy_registry.py`：策略版本登记和对比。
- `core/`：统一回测内核，负责 `data_lake` 加载、因子、择时、真实成本、融资成本和指标。
- `factory/`：阶段 1 策略工厂骨架，负责候选空间、多目标评估和 Pareto 排序。
- `scripts/data/`：数据构建、拉取和增量更新脚本。
- `scripts/repair/`：数据修复和重校验脚本。
- `scripts/research/`：研究验证、模拟、成本敏感性和旧研究遗留脚本。
- `data_lake/`：新版数据湖，包含日线、周线、财务、交易日历和质量报告。
- `lake/`：数据湖加载、聚合、校验和数据源模块。
- `results/`：策略配置、净值图、进化历史等结果文件。
- `signals/`：每日信号输出。
- `reports/`：报告和导出文件。

## 日常查看信号

在项目目录运行：

```bash
cd /Users/kiki/astcok/factor_research
python3 run_daily.py --no-update
```

输出重点看：

- `最新交易日`：确认数据日期是否符合预期。
- `小盘指数 vs MA16`：确认当前是持仓还是空仓。
- `调仓判断`：确认今日是否需要调仓。
- `操作` 和 `持仓`：用于生成当日执行参考。

结果会保存到：

```text
signals/YYYY-MM-DD.json
```

如需联网增量更新数据后再出信号：

```bash
cd /Users/kiki/astcok/factor_research
python3 run_daily.py
```

## 复测真实口径策略

运行 `data_lake` 口径复测：

```bash
cd /Users/kiki/astcok/factor_research
python3 strategy_lake.py
```

输出会对比：

- 2018-2026：真实成本 + `data_lake` 口径
- 2010-2026：压力测试，包含 2015 股灾和 2017 小盘崩盘

## 校验数据质量

运行最终数据质量校验：

```bash
cd /Users/kiki/astcok/factor_research
python3 validate_final.py
```

结果会保存到：

```text
data_lake/quality_report.json
```

重点看：

- `clean_ratio`：干净数据比例。
- `issue_breakdown`：真实数据问题分布。
- `flagged`：需要排查的股票代码。

当前质量报告显示约 99.92% 数据干净，仅少数股票存在 `价格跳变>50%` 问题。

## 验证数据湖加载层

用于确认新版 `data_lake` 的价量、财务防未来函数对齐和估值自算是否正常：

```bash
cd /Users/kiki/astcok/factor_research
python3 test_load_lake.py
```

如果输出 `加载层验证通过`，说明数据湖加载层基础可用。

## 运行策略工厂

阶段 1.1 最小工厂入口：

```bash
cd /Users/kiki/astcok/factor_research
python3 factory/run_factory.py
```

结果会保存到：

```text
reports/factory_stage1_1.json
```

当前版本只做少量候选母策略的多目标评估和 Pareto 排序，不是完整 NSGA-II 搜索。

## 当前最重要的下一步

阶段 0 已收束到统一 `core/` 内核、`data_lake` 口径和真实成本模型。旧 `data_full/`、`data/` 缓存已清理。下一步是在此基础上进入阶段 1：多目标策略工厂化。

建议顺序：

1. 继续以 `strategy_lake.py` 和 `strategy_versions.json` 为准登记新版本。
2. 用 `run_daily.py --no-update` 验证每日信号流程。
3. 用 `scripts/research/cost_sensitivity.py`、`scripts/research/simulate_2025.py` 等脚本做交易成本、换手、融资和执行层验证。
4. 对新增版本补充样本内/样本外和压力测试说明。

## 常见结果文件

- `data_lake/quality_report.json`：数据湖质量报告。
- `signals/YYYY-MM-DD.json`：每日信号。
- `signals/state.json`：每日流程维护的真实持仓状态，包含当前仓位、上次调仓日和最近持仓。
- `strategy_versions.json`：策略版本登记。
- `reports/`：交易明细、执行层模拟等报告。
- `results/`：阶段 0 早期研究产物，仅作历史参考，不作为主线口径。

## 注意事项

- 这里不是 git 仓库，修改前后需要自己留意文件版本。
- 回测结果不是投资建议，实盘前还需要做更严格的交易成本、容量、停牌、涨跌停、滑点和组合换手验证。
- 当前最新数据日期需要以 `run_daily.py` 或 `strategy_lake.py` 输出为准，运行前应确认数据是否已更新到目标日期。
