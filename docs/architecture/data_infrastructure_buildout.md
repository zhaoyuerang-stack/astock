# 数据基础设施搭建说明

> 版本: 2026-07-03  
> 范围: `factor_research/data_lake/`, `factor_research/lake/`, `factor_research/scripts/data/`  
> 定位: 解释本系统的数据基础设施是如何从"可下载数据"搭成"可研究、可复测、可审计的数据地基"的。  
> 相关文档: `CLAUDE.md`, `factor_research/docs/data_infrastructure.md`, `factor_research/data_lake/README.md`

## 1. 第一性目标

数据基础设施要解决的不是"把行情拉下来", 而是让后续研究结论有资格被相信。

量化研究里, 数据层一旦出错, 后面所有 alpha、回测、9-Gate、Web 看板都会变成精致错误。因此本系统的数据层从一开始按四个目标搭建:

1. **全市场口径**: 正式研究必须覆盖 A 股全市场, 包括主板、创业板、科创板、中小市值、停牌、ST、上市时间和退市历史。
2. **点时间可用性**: T 日信号只能使用 T 日当时已经可知的信息。财务、公告、资金面都必须有明确可见日。
3. **统一事实源**: 正式研究只认 `data_lake/` + `lake/load_lake.py` 的 canonical 加载路径, 不允许从旧缓存或临时 CSV 直接得出正式结论。
4. **写入可审计**: 落盘前要做 schema、单位、截面异常、质量报告和 manifest 记录; 数据问题应 fail closed, 不能静默换口径。

一句话: 数据湖不是文件夹, 是一组受控的口径、加载、校验和血缘约束。

## 2. 分层架构

当前数据基础设施按五层组织:

```text
外部数据源
  -> 抓取/更新脚本
  -> data_lake 原始与标准化存储
  -> lake 统一加载与对齐层
  -> 质量、指纹、守卫
  -> 因子 / 回测 / workflow / Web 消费
```

### 2.1 外部数据源

系统不是依赖单一数据源, 而是按数据类型选择源:

| 数据类型 | 主要来源 | 用途 |
| --- | --- | --- |
| 后复权价量 | Tencent / 历史湖路径 | 收益率、动量、技术类因子、回测净值 |
| 不复权 OHLC | 通达信 / Tushare daily 优化路径 | 估值、真实价格展示、模拟盘口径 |
| 财务批量 | Eastmoney yjbb / Tushare financials | 基本面、质量、成长、杠杆 |
| 市值/换手/估值 | Tushare daily_basic | 真 Barra Size、估值、换手、股息 |
| 资金面 | 交易所、东财、Tushare moneyflow | 两融、北向、主力资金 |
| 交易状态 | Tushare stk_limit / suspend_d / meta | 涨跌停、停复牌、可交易性 |
| 事件与持有人 | Tushare forecast/express/holder/share_float/top_list | 事件、业绩、筹码、机构行为 |
| ETF / 跨资产 | cross_asset ETF 更新脚本 | 防守资产、组合腿、闲置资金管理 |

设计取舍:

- 后复权数据适合收益率和技术指标, 但不能直接用于 PE/PB 等估值。
- 不复权价格必须独立保存, 防止估值量纲错误。
- 财务类数据必须按公告日对齐, 不得按报告期结束日直接 forward fill。
- 有硬配额的数据源宁可 fail-fast, 不要伪装成网络重试问题无限等待。

## 3. data_lake 目录设计

核心目录:

```text
factor_research/data_lake/
├── price/
│   ├── daily/              # 逐只后复权价量 parquet
│   ├── daily_all.parquet   # 合并大表, 优先加载
│   ├── daily_raw/          # 逐只不复权 OHLC
│   ├── daily_raw_all.parquet
│   ├── weekly/
│   └── monthly/
├── fundamental_batch.parquet
├── capital/
│   ├── margin_all.parquet
│   └── northbound_all.parquet
├── daily_basic/
├── financials/
├── moneyflow/
├── market/
├── event/
├── holder/
├── index/
├── meta/
│   ├── trade_calendar.parquet
│   ├── codes.parquet
│   ├── st_history.parquet
│   └── list_date.parquet
├── _manifest.json
└── tushare_manifest.json
```

目录设计原则:

- **逐只文件保留可修复性**: 单只股票坏值可以局部重抓或隔离。
- **大表保留加载性能**: 正式加载优先读 `*_all.parquet`, 避免每次扫描数千文件。
- **meta 独立**: 交易日历、股票池、ST、上市日是 universe 和可交易性判断的根。
- **manifest 单独记录**: `_manifest.json` 和 `tushare_manifest.json` 记录数据集 vintage、行数、末日、更新时间, 方便对账。

## 4. Schema 和字段标准化

`lake/schema.py` 是字段口径中心。它定义:

- 标准价量字段: `open/high/low/close/volume/amount`
- 不复权字段: `raw_open/raw_high/raw_low/raw_close`
- 财务字段: `roe/eps/bps/revenue/net_profit/gross_margin/...`
- 资金面字段: `margin_balance/northbound_hold_value/...`
- Tushare 扩展字段: `daily_basic`, `fina_indicator`, `moneyflow`, `stk_limit`, `forecast`, `holdernumber`, `index_daily` 等。
- 原始源字段到标准字段的 rename 映射。

这样做的原因很简单: 字段名一旦散落在脚本里, 数据源换列名或单位时就会出现"某条路径悄悄错、另一条路径还对"。schema 集中后, 新维度接入要先声明字段和口径, 再进入加载层。

## 5. 统一加载层

正式代码通过 `lake/load_lake.py` 读数据, 不应直接读 parquet。

关键接口:

| 接口 | 作用 | 关键口径 |
| --- | --- | --- |
| `load_prices()` | 后复权价量 date × code 面板 | 优先读 `daily_all.parquet`, 自动清洗隔离 |
| `load_raw_close()` | 不复权收盘价面板 | 估值专用, 避免复权价量纲错误 |
| `load_fundamental_panel()` | Eastmoney 财务面板 | `avail_date` 生效并 ffill 到交易日 |
| `load_fina_indicator_panel()` | Tushare 财务指标 | `ann_date` 公告日生效 |
| `load_daily_basic_panel()` | 市值/换手/估值面板 | by_date 当日收盘已知, 不 shift |
| `load_capital_panel()` | 两融/北向资金面 | T 日盘后发布, 统一 `shift(1)` |
| `load_tushare_panel()` | Tushare 扩展统一入口 | 按注册表自动选择 by_date 或 anndate 口径 |

加载层的核心不是便利函数, 而是把防未来规则固化:

- **财务/公告**: 以 `ann_date` 或 `avail_date` 为生效日, 之后交易日才可见。
- **资金面**: 盘后发布, T 日数据从 T+1 起可用, 所以 pivot 后 `shift(1)`。
- **价格衍生量**: close、amount、daily_basic 市值换手等属于 T 日收盘后可知, 与 T 日回测信号的使用时点由策略/引擎的 `shift(1)` 和 T+1 执行语义控制。
- **估值**: PE/PB 等只能用不复权价或源定义一致的估值字段。

## 6. 增量更新机制

基础更新入口:

```bash
cd factor_research
python3 scripts/data/update_lake.py --all
python3 scripts/data/update_lake.py --prices
python3 scripts/data/update_lake.py --validate
```

日常运行由更上层的 `scripts/ops/scheduled_daily_update.py` 串起:

```text
数据增量 -> 质量校验 -> 信号生成 -> 模拟盘 -> 状态/告警
```

Tushare 扩展由 `scripts/data/update_tushare.py` 负责。它采用 registry 驱动:

```text
INTERFACES[name] = {
  mode,
  keys,
  store,
  fields,
  date_param / index_codes / params
}
```

新增一个维度通常不是写一份新抓取逻辑, 而是在 `INTERFACES` 里补声明。通用 `backfill()` 根据 `mode` 自动决定怎么补:

- `by_date`: 每个交易日一次, 一次拿全市场。
- `by_period`: 每个报告期一次, 适合财报三表。
- `by_stock`: 每只股票一次拿全史。
- `by_index`: 每个指数一次拿全史。
- `once`: 一次性元数据。

`update_tushare.py` 的工程点:

- token 从 `TUSHARE_TOKEN` 或 gitignored 配置读取, 不入库。
- 读已有 parquet 的 key, 自动跳过已完成单元。
- 分批 flush, 支持长任务中断后继续。
- 每个 dataset 更新后写 `tushare_manifest.json`。
- 对 "X 次/天 / X 次/小时" 这类硬配额直接抛错, 不把配额墙伪装成可重试网络问题。

## 7. Tushare 扩展层如何搭起来

Tushare 层的目标不是替代所有基础价量, 而是给研究系统补上多维度横截面信息:

| 类别 | 数据集示例 | 研究价值 |
| --- | --- | --- |
| 市值/估值/换手 | `daily_basic` | 真市值 Size、估值、换手、股息 |
| 复权因子 | `adj_factor` | 校验和补强复权链 |
| 财务指标 | `fina_indicator`, `income`, `balancesheet`, `cashflow` | 质量、成长、杠杆、现金流 |
| 公司行动 | `dividend`, `share_float` | 分红、解禁、供给压力 |
| 事件 | `forecast`, `express`, `block_trade`, `top_list`, `top_inst` | 盈利惊喜、大宗、龙虎榜 |
| 资金流 | `moneyflow` | 主力、大中小单资金行为 |
| 交易约束 | `stk_limit`, `suspend_d`, `limit_list_d` | 涨跌停、停牌、情绪 |
| 持有人 | `stk_holdernumber`, `stk_holdertrade`, `top10_holders` | 筹码集中、内部人、机构持仓 |
| 指数/行业 | `index_daily`, `index_classify` | 基准、申万行业、风格审计 |
| 风险 | `pledge_stat` | 股权质押、暴雷预警 |

关键口径:

- `by_date` 数据是当日横截面观测, 例如 `daily_basic`, `moneyflow`, `stk_limit`。
- `anndate` 数据是公告日生效, 例如 `fina_indicator`, `forecast`, `express`, `holdernumber`。
- 大体量或硬配额接口如 `cyq_perf`, `limit_list_d` 不能强行并发硬跑, 要单独规划或接受覆盖边界。

## 8. 质量控制: 从事后检查到写路径闸门

系统曾经发生过一次典型数据事故: 后复权源缺失时静默混入不复权价, 导致末两日全市场出现假崩盘, 污染 OOS 回测 NAV 指标。

事故后, 数据层从"事后可选校验"升级成"写路径强制闸门"。

关键机制:

### 8.1 截面异常不变量

`lake/invariants.py::assert_price_panel_sane()` 检查末 N 日截面收益分布:

- 个别股票大涨跌可以正常。
- 如果全市场大比例股票同时出现 `|r| > 30%`, 更可能是复权断裂或口径混入。
- 默认阈值: 最近 5 日、跳变阈值 30%、截面异常占比不得超过 5%。

### 8.2 价量单位不变量

`validate_price_amount_units()` 检查:

```text
amount ≈ volume(shares) × raw_close(CNY/share)
```

它用于防止 volume 单位在股/手之间错 100 倍, 尤其是科创板等特殊口径。系统会按板块检查中位比率和 P95 相对误差, 不满足则拒绝落盘。

### 8.3 隔离与修复

`load_prices()` 在加载时会调用:

- `apply_quarantine(df)`: 排除已知坏数据区间。
- `repair_ohlc(df)`: 做确定性 OHLC 自洽修复。

### 8.4 数据指纹

`lake/fingerprint.py` 把 vintage 从"自报日期"变成"内容凭证":

```text
vintage = 日期标签 + 面板内容 sha256 截断指纹
```

同一日期如果数据被重写, 指纹会变。实验日志和回测证据可以靠指纹识别是否复现到同一份数据。

### 8.5 全量质量报告

`validate_final.py` 产出 `data_lake/quality_report.json`。Web 的数据健康页和 readiness 逻辑应读取真实质量结果, 不应硬编码绿灯。

## 9. 数据湖写入纪律

写核心数据湖不是普通文件写入。当前纪律:

1. 正式写入路径必须在 `lake/` 或 `scripts/data/` 的受控入口。
2. 运行产物、报告、模拟盘、信号路径应经 `runtime.artifacts.ArtifactPaths` 或 service 层访问, 不在 API 里 open-code 路径。
3. 受保护输出如 `data_lake/version_returns` 已采用 canonical writer + AST 守卫模式。
4. `scripts/ci/check_lake_writers.py` 用于检查非法直接写 lake 的路径。
5. `scripts/ci/check_no_legacy_data.py` 禁止正式代码从旧 `data_full` 读数据。

可靠模式是:

```text
先建立 canonical writer / loader
  -> 迁移调用方
  -> 加 AST-aware CI 守卫
  -> 增加负例测试
```

## 10. 性能优化

数据层做过几类性能优化:

### 10.1 大表优先加载

`load_prices()` 和 `load_raw_close()` 优先读 `daily_all.parquet` / `daily_raw_all.parquet`, 并尽量用 parquet filters 做日期 pushdown, 避免每次读完整 15M+ 行。

### 10.2 逐只文件保留 fallback

如果大表不存在, loader 仍可回退到逐只 parquet。这样全量重建、大表损坏或局部恢复时不会彻底停摆。

### 10.3 不复权 raw 日更优化

原始不复权 OHLC 曾经依赖通达信逐股请求, 5200+ 只股票会变成 5200+ 次外网请求, 日更耗时 7-20 分钟。

优化后用 Tushare `daily` 全市场单日批量接口:

- 每个缺失交易日只发 1 次请求。
- 返回后本地按 `code` groupby 拆分追加。
- 网络请求从 5200+ 次降到 1 次。
- 增量耗时从分钟级降到秒级。
- 保留通达信逐股路径作为 failover。

### 10.4 Tushare 单 token 顺序限速

Tushare 源在 `lake/sources/tushare.py` 里实现单线程节流。虽然跨接口并行在某些情况下可行, 但同 token 同接口不并发是更稳的默认纪律。重响应接口使用指数退避; 硬配额直接 fail-fast。

## 11. 与研究层的接口

数据层向上提供的是面板, 不是策略结论。

典型消费链:

```text
load_prices / load_tushare_panel
  -> factors 计算因子
  -> core.engine BacktestEngine 统一回测
  -> factory / workflow 做候选筛选与晋级
  -> registry / production / Web 读取证据
```

关键边界:

- 数据层不得依赖 factors、strategies、factory、workflow、services 或 API。
- 因子层可以消费数据, 但不允许直接判定入册。
- 正式回测只能通过 `core.engine.BacktestEngine`。
- Web/API 不应该直接读写 `data_lake`; 应经 services read/action 层。

## 12. 当前已知边界和风险

这套数据基础设施仍有明确边界:

1. **Tushare 积分墙**: `cyq_perf`, `limit_list_d` 等接口存在日/小时硬配额, 不能靠重试解决。
2. **公告日语义依赖源字段质量**: 财务/事件 PIT 对齐依赖 `ann_date` / `avail_date` 真实可靠。
3. **旧历史口径迁移债**: 旧 `data_full` 或历史脚本只能做迁移/对照, 不得作为正式依据。
4. **大体量维度需要专门设计**: 筹码分布、研报、分钟级行情等不能简单塞进日频 parquet 大表。
5. **数据新鲜度和生产 readiness 需分开**: 数据到最新交易日不等于策略可部署; 部署还要看台账、DSR、衰减和风控。

## 13. 如何复现搭建路径

新机器或重建时, 推荐顺序:

1. 准备环境和 token:

```bash
cd /Users/kiki/astcok/factor_research
export TUSHARE_TOKEN=...
```

2. 建基础 meta 和价量湖:

```bash
python3 scripts/data/build_lake.py
python3 scripts/data/fetch_raw_close.py
python3 lake/compact.py
```

3. 建基础财务和资金面:

```bash
python3 scripts/data/build_fundamental_batch.py
python3 scripts/data/update_lake.py --all
```

4. 回填 Tushare 扩展:

```bash
python3 scripts/data/update_tushare.py --interface daily_basic --start 20100101
python3 scripts/data/update_tushare.py --interface fina_indicator
python3 scripts/data/update_tushare.py --all
```

5. 校验:

```bash
python3 validate_final.py
python3 scripts/ci/check_lake_writers.py
python3 scripts/ci/check_no_legacy_data.py
```

6. 日常运行:

```bash
python3 scripts/ops/scheduled_daily_update.py
```

注意: 上述是搭建路径说明, 不是建议在当前工作树立即全量重跑。全量重跑会产生大量数据湖产物, 应单独排期并确认 token、磁盘、网络和数据源配额。

## 14. 判断这套数据基础设施是否健康

不要只看"文件存在"。健康标准应是:

- 最新交易日覆盖合理, manifest 可对账。
- `validate_final.py` 无 severe 质量问题。
- 价量单位不变量通过。
- 近期截面收益无系统性假崩盘。
- 财务和事件数据按公告日可见。
- 资金面数据按披露延迟处理。
- 正式研究路径不读 `data_full`。
- Web 展示的数据新鲜度来自真实 manifest / quality report, 不是硬编码。
- 任一回测证据能追到数据 vintage 和内容指纹。

## 15. 总结

这套数据基础设施的搭建顺序可以概括为:

```text
先定义不可违反的研究口径
  -> 再设计 data_lake 存储布局
  -> 用 schema 固化字段和单位
  -> 用 loader 固化 PIT 对齐
  -> 用增量脚本固化抓取和 manifest
  -> 用 invariants / quality report / fingerprint 固化可信度
  -> 用 CI 守卫禁止旁路
```

它的价值不在于"数据多", 而在于数据能经得起复测、审计和失败时的追责。

