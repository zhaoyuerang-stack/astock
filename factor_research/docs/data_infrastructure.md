# 数据基础设施架构

> 数据湖 + 统一加载层 + 质量校验 + 增量更新

## 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                        数据源层                               │
│  腾讯(fqkline)  新浪(akshare)  东财(yjbb_em)  交易所(两融)   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        原始存储层                             │
│  price/daily/*.parquet  price/daily_raw/*.parquet           │
│  fundamental_batch.parquet  capital/*.parquet               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        处理层                                 │
│  lake/compact.py          (逐只→大表合并)                    │
│  lake/aggregate.py        (日线→周线/月线)                   │
│  lake/validator.py        (8层质量校验)                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        统一加载层                             │
│  load_prices()  load_fundamental_panel()  load_capital_panel()│
│  load_raw_close()  load_panel()                              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                        消费层                                 │
│  core.engine.BacktestEngine  factory/evaluator.py            │
│  run_daily.py  factors/*.py  scripts/research/*.py           │
└─────────────────────────────────────────────────────────────┘
```

## 核心设计原则

1. **单一事实源**: `data_lake/` 是生产与研究的唯一数据源，旧 `data_full/data` 已清理
2. **防未来函数**: 财务按 `avail_date` 对齐，资金面 shift(1)，T 日只用 T 日前已披露数据
3. **统一接口**: 所有数据通过 `lake/load_lake.py` 加载，不直接读写 parquet
4. **增量更新**: `update_lake.py` 基于 `last_date` 只抓新增，避免全量重下
5. **质量校验**: `validate_final.py` 8 层校验，产出 `quality_report.json`

## 模块职责

| 模块 | 职责 |
|------|------|
| `lake/schema.py` | 集中式字段名、rename 映射、目录定义 |
| `lake/load_lake.py` | 统一数据加载接口（价量/财务/资金面/不复权） |
| `lake/base.py` | Fetcher 基类 + RateLimiter（所有数据源继承） |
| `lake/validator.py` | 8 层数据质量校验 |
| `lake/compact.py` | 逐只 parquet → 大表合并 |
| `lake/aggregate.py` | 日线 → 周线/月线聚合 |
| `scripts/data/update_lake.py` | 统一增量更新入口 |
| `scripts/data/build_lake.py` | 全市场日线下载 + 校验 |
| `scripts/data/build_fundamental_batch.py` | 批量财务下载 |
| `scripts/data/fetch_raw_close.py` | 不复权 OHLC 下载 |

## Schema 规范

详见 `lake/schema.py`。所有数据源原始列名 → 标准列名的映射集中定义，避免散落在各文件中。

## 更新流程

```bash
# 每日盘后
python3 scripts/data/update_lake.py --prices --fundamental

# 每周
python3 scripts/data/update_lake.py --weekly-monthly --validate

# 全量重建（首次或数据损坏时）
python3 scripts/data/build_lake.py
python3 scripts/data/build_fundamental_batch.py
python3 scripts/data/fetch_raw_close.py
python3 lake/compact.py
python3 validate_final.py
```
