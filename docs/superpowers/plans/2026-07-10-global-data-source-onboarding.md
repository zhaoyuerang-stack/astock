# 全球数据源接入与清洗任务

## 结论与边界

当前 global-data 仅完成 catalog、写入边界、PIT loader 和状态探测。它没有
真实 provider endpoint mapping，也没有 source-specific 清洗；因此任何
`data_lake/global` 记录在本任务完成前都不得作为生产因子或策略输入。

本任务把“新增一个数据源”定义为一个完整闭环：授权核验 -> 原始快照 ->
标准化 -> 数据质量校验 -> PIT 对齐 -> canonical lake -> manifest/coverage ->
可重复回放。不能只接通一个 HTTP 调用或写出一个 parquet 就宣布数据已可用。

不改变 A 股 canonical lake、`BacktestEngine`、strategy registry、holdout 或
9-Gate。全球数据默认 research-only、daily update auxiliary；只有完成本计划
所有 acceptance criteria 并由配置显式设为 required，才可影响生产 readiness。

## 交付优先级

### Wave 1: 可验证的低风险数据

| source_id | canonical datasets | 初始范围 | 用途与限制 | 进入条件 |
| --- | --- | --- | --- | --- |
| `alfred_macro_v1` | `macro_daily`, `macro_monthly`, `rates_daily` | 美国利率、收益率曲线、CPI、就业、工业生产等固定 series allowlist | 宏观状态/研究候选；必须保留 vintage 和实际可见时间，不能用今天修订后的历史值回测过去 | provider 能提供 observation、vintage/release 和单位字段；授权通过 |
| `global_etf_price_v1` | `etf_daily`, `market_price_daily` | 固定的美国上市全球风险代理 ETF/index ETF allowlist，例如 SPY、QQQ、IWM、EFA、EEM、TLT、HYG、LQD、GLD、DBC、UUP | 跨资产 regime/相关性研究；仅盘后可见；未确认 corporate-action 语义前不得生成交易收益 | provider 能提供交易所、币种、session close、OHLCV 与 adjustment 标识；授权通过 |

ALFRED/FRED 的历史 vintage 数据需要 direct/native adapter；除非 OpenBB 能逐字段保留
`observation_date`、`realtime_start`、`realtime_end` 和 release timestamp，否则不能经
OpenBB 的简化结果落入 canonical macro lake。ETF price provider 可以是 OpenBB extension
背后的 provider，也可以是 native adapter，但不能以“免费且能返回 DataFrame”作为准入依据。

### Wave 2: 在 Wave 1 稳定后增加

| source_id | canonical datasets | 最小范围 | 额外风险 |
| --- | --- | --- | --- |
| `fx_spot_v1` | `fx_daily` | USD major pairs 的 EOD closing rate | 货币对方向、纽约切日、holiday calendar 和 rate convention |
| `commodity_curve_v1` | `commodity_daily` | 连续主力/现货 proxy 的固定 allowlist | 合约换月、roll rule、currency/quantity units |
| `option_eod_v1` | `derivatives_daily` | 单一美国 ETF 的 EOD option chain | 合约静态字段、行权/到期、OI revision、survivorship 与昂贵授权 |

### Wave 3: 仅作为事件研究候选

`news_events` 和 `regulatory_filings` 仅在可拿到原始发布时间、修订版本和唯一事件 ID
后接入。v1 不得成为 production factor 依赖，更不得由网页抓取时间代替 `published_at` /
`accepted_at`。

## Task 0: Source Admission Record

为每个 `source_id` 新建一条 machine-readable source admission record，扩展
`lake/global_catalog.py` 或新增同层 registry，字段至少包括：

- `source_id`、provider adapter、provider endpoint/version、owner、授权状态、API key env；
- `allowed_use`（research_only / production_candidate / prohibited）、license_checked_at、
  redistribution/storage restriction；
- dataset、allowlist、frequency、calendar、timezone、currency、units、update watermark；
- raw schema version、canonical schema version、primary key、dedupe policy；
- `observed_at`、`available_at`、`retrieved_at` 的定义和可信等级；
- revision/vintage policy、corporate-action policy、quality thresholds、fallback policy；
- `required=false` 初始状态和 owner-approved promotion condition。

验收：缺少任一字段的 source 不得被 `--all-enabled` 选中；缺 key、无授权或未知 PIT
语义必须返回明确的 `missing_credentials`、`entitlement_denied` 或 `pit_metadata_missing`，
不得静默切换另一个 provider。

## Task 1: 建立原始快照和标准化边界

现有 `write_global_dataset()` 会把 provider DataFrame 原样写进 canonical parquet。将它改成
两段式写入，并保持所有路径由 `lake/` canonical writer 拥有：

```text
adapter response
  -> global raw snapshot (immutable, source schema)
  -> normalizer (source schema -> canonical schema)
  -> validation / quarantine
  -> canonical writer (data_lake/global/<dataset>.parquet)
  -> manifest + coverage + quality report
```

### Raw snapshot contract

- 路径使用 `data_lake/global_raw/<source_id>/<dataset>/<ingest_id>/`；数据湖产物不进 git。
- 每次 fetch 写 source payload、请求参数的非敏感摘要、retrieved_at、provider endpoint/version、
  row count、content hash、schema hash、watermark 和 ingest_id。
- 原始快照只追加，不允许被当期“修订数据”覆盖；重跑同一 `ingest_id` 必须幂等。
- token、完整 header、账号、URL query 中的 secret 绝不写 manifest、report 或 log。

### Canonical common columns

所有标准化记录必须具备：`source_id`、`provider`、`dataset_id`、`retrieved_at`、
`ingest_id`、`schema_version`、`source_timezone`、`currency`、`available_at`。任何未知或
不可解析的值必须失败或进入 quarantine，不能填充为当前时间。

`available_at` 是唯一允许 loader 判断可见性的时间列；`observed_at` / `date` 只表示经济或
市场发生时间。对无法获得可信 `available_at` 的宏观、新闻和监管数据，v1 必须拒绝入 canonical
lake，而不是套用日历日推断。

### Dataset-specific canonical schema

| dataset | 额外必填列 | 清洗/标准化规则 |
| --- | --- | --- |
| `macro_daily`, `macro_monthly`, `rates_daily` | `series_id`, `observation_date`, `value`, `unit`, `frequency`, `vintage_start`, `vintage_end` | 数值转 float64；单位、季调口径和频率不得混在同一 series；同一 observation 保留不同 vintage，禁止 latest-wins 覆盖历史 |
| `market_price_daily`, `etf_daily` | `symbol`, `exchange`, `session_date`, `session_close_at`, `open`, `high`, `low`, `close`, `volume`, `is_adjusted` | 统一 symbol mapping；金额/成交量转到声明单位；OHLC 一致；raw close 与 adjusted close 分列，禁止混写 `close` |
| `fx_daily` | `pair`, `base_currency`, `quote_currency`, `rate`, `fixing_at` | 明确 quote direction；统一到 `base per quote` 或反向并固定为一条规则；按 fixing timestamp 切日 |
| `commodity_daily` | `instrument_id`, `contract`, `expiry`, `roll_rule`, `settlement`, `unit` | 连续合约必须带 roll rule/version；不允许把不同合约直接 ffill 成一个 series |
| `derivatives_daily` | `underlying`, `option_symbol`, `expiry`, `strike`, `right`, `bid`, `ask`, `last`, `volume`, `open_interest`, `as_of` | contract key 唯一；strike/expiry/right 不可缺；OI 修订需保留 as_of 版本 |
| `news_events`, `regulatory_filings` | `event_id`, `published_at` 或 `accepted_at`, `source_url`, `version` | timestamp 统一 UTC；以 source event id + version 去重；网页下载时间不能作为事件可见时间 |

## Task 2: 实现清洗与质量闸门

新增 `lake/global_normalizers.py`、`lake/global_validator.py` 和 quarantine writer；每个 source
adapter 只负责网络请求和原始响应，不能私自 rename、drop、ffill 或落 parquet。

### 通用检查

1. schema：列完整、类型可解析、无未知必填枚举、canonical primary key 唯一。
2. 时间：所有 timestamp timezone-aware；`available_at >= observed_at`；不得晚于 `retrieved_at`
   的不合理容差；session date 与 source calendar 一致。
3. 数值：NaN/inf、负数、零值和尺度错误按 dataset rule 分类为 reject、quarantine 或 info。
4. 增量：watermark 只能向前推进；重跑同一窗口的输出 content hash 必须稳定；旧有效数据不被
   空响应、部分响应或 schema drift 覆盖。
5. 覆盖：按 allowlist 计算 expected/received，输出缺失 series/symbol、最新可用日、staleness、
   revision count；未达阈值只标记 `partial_ok`，不伪报 available。
6. provenance：每一个 canonical row 能通过 `ingest_id` 回查 raw snapshot；manifest 保存
   raw/canonical hash、schema version、quality status 和 quarantine count。

### Wave 1 特有检查

ALFRED macro：

- 相同 `(series_id, observation_date, vintage_start)` 只能一条；`vintage_end` 必须晚于 start。
- historical replay 以 `available_at <= signal_date` 选择当时最新 vintage，不能读 today latest。
- 旧的固定 M+2 只可作为没有 release metadata 的 research safety lag；有 `available_at` 后必须
  由 timestamp 规则替代，并增加前后边界测试。
- unit/frequency/seasonal-adjustment 变化视为 schema drift，拒绝自动拼接。

Global ETF price：

- `(symbol, exchange, session_date, adjustment_version)` 唯一；重复项只允许同值重复，否则 quarantine。
- `low <= min(open, close) <= max(open, close) <= high`，价格必须正，volume 不得负。
- session_close_at 必须属于 source exchange timezone；交易日缺失需由该交易所 calendar 判断，
  不能使用 A 股交易日历。
- 调整价格和未调整价格必须字段分离；corporate action 缺失或 adjustment flag 不明时只保留
  research-only raw series，禁止计算 total return。
- 对固定锚点 symbol 进行第二源收益率抽样对账；超过阈值进入 data issue triage，且不能覆盖旧
  canonical batch。

### Quarantine / failure policy

- 结构、PIT、单位、primary key、OHLC 和 corporate-action 语义错误：reject batch，不写 canonical。
- 少量单行解析错误：raw 保留，将错误行与 reason 写入 `data_lake/global_quarantine/`，manifest
  标记 `partial_ok`；超过阈值则 reject batch。
- 网络、授权、provider mapping、schema drift：保留上次健康 canonical 数据，更新 status 和
  `last_error`；不得写空表覆盖。
- 任何 global failure 保持 auxiliary，除非该 source/dataset 明确 required；required failure
  才能让 daily readiness failed。

## Task 3: Adapter 与增量任务

1. 为 `alfred_macro_v1` 新建 native adapter，先实现一个配置化 series allowlist；单元测试用
   fixture/raw snapshots，不在测试中联网。
2. 为 `global_etf_price_v1` 新建 provider-neutral adapter protocol；实现一个已授权 provider
   mapping，保留 OpenBB adapter 作为 probe/可选实现，不能把 OpenBB DataFrame 直接写入 lake。
3. 更新 `scripts/data/update_global_data.py`：增加 `--source`、`--from-watermark`、
   `--replay-ingest`、`--validate-only`、`--quarantine-report`；保留 `--probe` 与 `--dry-run`。
4. 增量窗口至少向前回看五个来源自然日或一个 revision window；合并按 canonical key 去重；
   成功后才推进 watermark。
5. manifest 新增 `source_id`、latest_observation、latest_available、watermark、coverage、
   quality_status、quarantine_count、raw_hash、canonical_hash、schema_version、last_good_ingest_id。
6. scheduler 先更新 A 股 ETF/Tushare，再运行 Wave 1 sources；report、triage、alert body 必须
   列出哪个 source/dataset 失败及其 last-good date。

## Task 4: Loader、API 与研究边界

- `load_global_macro()` 必须按 `available_at` 做 point-in-time as-of join，并提供
  `as_of_date` 参数；没有 availability metadata 时显式失败。
- `load_global_price_panel()` 必须要求 `field` 与 `adjustment_basis`，拒绝含混的默认价格口径。
- API `/data/global/sources` 和 `/data/global/coverage` 展示 source、授权状态、coverage、
  latest observation/available、last-good date、质量状态与 quarantine 数；不显示“可交易”。
- `/experiments/global-data/probe` 只允许探测可用性/样本 schema/coverage；写入审计结果，
  不注册 hypothesis、不生成策略、不修改 registry。
- Wave 1 验收后，全球数据只能作为 hypothesis 的外部输入候选。进入因子研究仍要经
  availability audit、holdout 和 9-Gate；跨市场信号不得直接混入现有 A 股 production signal。

## Task 5: Tests、guards 与验收

### 必须新增的测试

1. Source admission record 缺授权、缺 PIT 字段、未知 unit 或未知 calendar 时 fail closed。
2. Raw snapshot 可重放；相同 input/ingest id 幂等；manifest 能回查 hash。
3. 正常化测试：raw column mapping、timezone/units、symbol mapping、重复与 schema drift。
4. Macro vintage test：在 revision 后 replay 历史日期，得到当时可见数值而不是当前修订值；
   `available_at` 前一刻不可见、后一刻可见。
5. ETF price test：OHLC/volume/adjustment conflict、交易所 holiday、跨日时区、公司行动和
   second-source return divergence。
6. Batch rejection test：坏 batch 不得覆盖 last-good canonical dataset；quarantine 阈值越界
   必须 rejected。
7. Loader PIT test：每种 dataset 必须证明 signal date 不能看到未来 observation/event。
8. Scheduler test：non-required global source failure => A 股 signal can be `partial_ok`；
   required source failure => readiness failed。
9. API contract/client test：覆盖状态展示和 probe job；前端不得以 `available` 暗示可交易。
10. Guard test：任何 `scripts/`、`workflow/`、`services/` 对 `data_lake/global*` 的直接
    parquet 写入必须被 `check_lake_writers.py` 拦截。

### 验收门槛

Wave 1 的每条 source 必须同时满足：

- 已保存授权/用途记录，配置和日志不泄露凭证；
- 至少一次全量小样本与连续五次 idempotent 增量运行通过；
- expected allowlist coverage >= 98%，缺失项目逐项可解释；
- latest available 的 staleness 符合 dataset SLO，且 last-good batch 可被回放；
- zero PIT violations、zero unresolved schema/primary-key/OHLC/unit error；
- 质量报告、quarantine 报告、manifest 与 `/data-health` 一致；
- focused tests、`check_layer_deps.py`、`check_lake_writers.py`、`check_no_legacy_data.py` 通过；
- 最终运行 `bash factor_research/scripts/test_all.sh`、Web `npm run lint` 和
  `npx tsc --noEmit`。任何既有失败须单独归因，不得掩盖。

## Commit Plan

1. `feat(global-data): add source admission and canonical schemas`
2. `feat(global-data): add raw snapshots and validation quarantine`
3. `feat(global-data): ingest vintage-aware macro data`
4. `feat(global-data): ingest global ETF price data`
5. `feat(global-data): surface source quality and update health`
6. `docs(global-data): document source operation and PIT evidence`

每个 commit 只包含该意图的代码、测试和必要文档。共享工作树中只允许显式
`git add <paths>`；提交前必须查看 `git diff --cached --stat` 与 `git diff --cached`。

## 明确不做

- 不把 OpenBB、Yahoo 类便利源或当前网页抓取结果当作无条件生产真相源。
- 不用 observation date、下载时间或今天的修订值冒充历史 `available_at`。
- 不在 v1 接入新闻、监管、期权全链或把全球数据直接用于交易信号。
- 不以“有 parquet 文件”替代质量、授权、PIT 和可回放验收。
