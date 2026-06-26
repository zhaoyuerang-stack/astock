---
name: probe-signal-source
description: 验证一个"新信息源"或候选因子是否携带正交、能泛化的增量信息(A股因子研究)。当要接入新数据源(北向资金/业绩修正/股东户数/龙虎榜/资金流/筹码…)、或在投入研究算力前体检一个候选因子时用。走"定位数据→建因子族→正交性+IS/OOS体检→(够好才)接工厂→island search→walk-forward"闭环。只产 L0-L3 证据,绝不宣布 alpha、不自动入册(入册走 workflow)。
---

# probe-signal-source —— 新信息源 / 候选因子验证闭环

> 本仓 = A股全市场日频因子量化研究系统。本 skill 把"验证一个新信息源是否值得投入"固化成可复现闭环。
> 上游:`CLAUDE.md`(宪法)、`DECISION_COCKPITS.md`(为什么做正交源:打破"研究引擎一直坍缩到小盘")、
> `LOOP_ENGINEERING.md`(9-Gate)、`factor_research/scripts/research/signal_source_probe.py`(本 skill 的核心工具)。

## 这个 skill 解决什么

研究引擎默认会**坍缩到小盘/流动性簇**(因子取材几乎全是 pe/amount/turnover/illiq)。
破局靠**换正交信息源**。本 skill 是验证"某个新源是否真的正交且能泛化"的标准流程——
而不是每次即兴写一堆一次性脚本。

## 铁律(违反则本次结论作废)

1. **只编排,不裁决**(`R-LLM-001`):本流程只**算 + 报**;"是否有效/可入册"由确定性门禁
   (DSR/PBO/holdout/9-Gate)+ workflow 决定。任何一步不得用语言代替统计检验。
2. **只产 L0-L3 证据,不是 alpha**:IC / 残差 IC / IS-OOS 是**便宜筛证据**,不扣成本、无 DSR/
   容量/9-Gate。**禁止**据此宣布"找到 alpha"。
3. **不自动入册**(`R-WF-001`):有希望的候选**交还 human + workflow**(`factory/candidates →
   L0-L3 → promote → phase1 防未来 → phase2/3 → phase4 入册`),本 skill 不写台账、不晋级。
4. **PIT 优先**(`R-DATA-003`):因子取数必须按公告日/披露日对齐;用 canonical loader
   (`lake.load_lake`,如 `load_capital_panel` 已内置 shift(1)),不自己拼可能泄露的口径。
5. **按"正交增量"排序,不按裸 IC/收益**:高回测收益默认疑似过拟合(见 DSR 教训)。
6. **复用 canonical 工具**:IC 用 `engine.factor_analysis.calc_ic/newey_west_icir`;搜索用
   `services.actions.autoresearch_search`(自动 `record_trials` 记账,DSR 诚实惩罚)。不另造回测(`R-BT-001`)。

## 闭环步骤

### 步骤 1 — 定位数据(便宜)
- 在 `data_lake/` 找该源:`ls data_lake/`,确认有无落盘 + schema + PIT 关键列(公告日/交易日)。
- 注册表:`lake/schema.py::TUSHARE_DATASETS`(统一 PIT 加载);资金面走 `load_capital_panel`。
- **若未落盘**:停下,报"未 ingested",这是数据工程任务,不在本 skill 内伪造。

### 步骤 2 — 建 / 定位 canonical 因子族(便宜)
- 模板:`factors/capital_flow.py` / `factors/northbound.py`(标注"与价量簇正交的独立数据族")。
- 签名:`def factor(close, window=N, **_) -> 宽表 date×code`,返回 `safe_zscore(mad_clip(...))`(截面)。
- PIT:用 canonical loader(`load_capital_panel` 等已 shift),因子内不再额外 shift;否则自己 shift 并注明。

### 步骤 3 — 正交性 + IS/OOS 体检(核心,便宜)
```bash
cd factor_research
python scripts/research/signal_source_probe.py \
  --factor factors.<族>:<函数> --param window=20 \
  --universe northbound --start 2018-01-01 --cutoff 2022-12-31 --end 2024-12-31
```
读四件事:
- **① 原始 rank-IC** —— 有无预测力。
- **② 残差 IC(去 size/流动性)** —— `正交保留率 ~100%` = 真正交于小盘/流动性簇;大幅缩水 = size/流动性代理。
- **③ 风格相关** —— 对 size/流动性/动量 |值| 大 = 某风格的伪装。
- **④ IS vs OOS 留存** —— OOS/IS 留存高且不翻负 = 能泛化;塌掉/翻负 = 过拟合。

**便宜判据(advisory,非裁决)**:正交保留率低 或 风格相关高 → 是已知风格代理,丢弃;
OOS 翻负/塌缩 → 过拟合,丢弃;**正交 + OOS 不塌(哪怕 modest)** → 有希望,继续。

### 步骤 4 — 接进工厂候选生成(中等)
仅当步骤 3 显示"正交且 OOS 不塌"。三处同步加(与"独立数据族隔离岛"holder/capital_flow 同组):
- `factors/autoresearch_dsl.py::_FACTOR_CALLS` —— `name: (module, fn, {"window":"window"})`(可计算)。
- `factory/autoresearch/registry.py::ALLOWED_FACTORS` —— `FactorSpec(name, {"window":(lo,hi)}, ("data/dep",))`(变异+白名单)。
- `factory/autoresearch/generator.py::_SEEDS` —— 加 1-2 条种子并**置顶**(islands 用小 limit 采种,置底取不到)。

### 步骤 5 — 小规模 island search(中等)
```python
from services.actions.autoresearch_search import run_autoresearch_island_search
resp = run_autoresearch_island_search(islands=2, generations=2, population=6,
    final_stage="l0", use_llm=False, sample_dates=120, rng_seed=7)  # use_llm=False=确定性+免联网
```
看冠军里有无该源、有无 `keep`(过 L0)、`corr_to_book`(对在册相关,低=正交)。

### 步骤 6 — walk-forward IS vs OOS(贵,最接近真相)
```python
from services.actions.autoresearch_search import run_autoresearch_walk_forward
resp = run_autoresearch_walk_forward(cutoff="2022-12-31", oos_end="2024-12-31",
    islands=2, generations=2, population=6, final_stage="l3", use_llm=False)
```
演化只见 ≤cutoff,冠军在 (cutoff, oos_end] **一次性 OOS**,forward_ret 由截断面板重算(防泄露)。
**注意**:进化复合常 OOS 翻车(blending 过拟合);更可信的是步骤 3 对**核心单因子**的干净 IS/OOS 切分。
此步会跑几分钟,用后台(`run_in_background`)。

### 步骤 7 — 诚实结论 + 交还(便宜)
- 报告用模板:`正交性 / IS-OOS 留存 / 是否过 L0 / OOS 是否塌`,每条标"L0-L3 证据,非 alpha"。
- **有希望的候选 → 交 human + workflow** 走完整 9-Gate/DSR/成本/容量;本 skill 到此为止。

## 反模式(禁止)
- 按裸 IC / 年化排"最佳因子"(诱导过拟合)。
- 据 IC/OOS 宣布"找到 alpha"或"可上线"。
- 自动写台账 / 晋级(绕过 `R-WF-001`)。
- 自己拼数据口径绕过 PIT loader。
- 用本 skill 替代确定性门禁做有效性判断。

## Worked example(2026-06,北向资金)
- 数据:`data_lake/capital/northbound_all.parquet`(已落盘,`load_capital_panel` PIT)。
- 因子:`factors/northbound.py::northbound_accumulation`(Δhold_pct)。
- 体检(步骤3):原始 IS IC=0.0255 → OOS 0.0165(**留存 65%、不塌**);正交保留率 **103%**;风格相关 size 0.05/流动 0.03 → 真正交。
- 工厂(步骤4-5):接入后 island search 6 冠军 5 含北向,1 个过 L0。
- walk-forward(步骤6):核心信号 OOS 不塌,进化复合三正三负(blending 过拟合)。
- 结论:**第一个 OOS 不塌的正交信号**——真实、可投、modest,**非达标 alpha**(待 9-Gate/DSR/成本)。
