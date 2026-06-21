# Quant OS 系统一致性整改实施计划

> ✅ **DONE / 已收尾归档**（2026-06-20 收尾，2026-06-21 归档）：本整改计划已执行完毕，DoD 核对见 [`STATUS.md`](../../STATUS.md)。
> **执行状态以 STATUS.md / 代码 / 台账为准**，文内 checkbox 是计划期的静态痕迹、不代表当前状态。
> （原文件名 `Task.md` 与开放任务台账 [`TASKS.md`](../../TASKS.md) 大小写碰撞，归档时重命名消歧。）

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复价量数据量纲、统一可执行策略本体，并让研究、注册、部署、生产信号、模拟执行和监控共享同一组可验证、默认拒绝、可审计的系统不变量。

**Architecture:** 整改按“数据真实性 → 策略身份 → 治理事务 → 部署控制 → 执行语义 → 验证与可观测性”单向推进。新增不可变 `ExecutableStrategySpec` 和显式 `DeploymentManifest`，所有控制判断由确定性代码完成；注册表只保存通过完整证据门的版本，生产只执行已激活部署，任何缺失、陈旧、版本不匹配或执行异常均 fail-closed。

**Tech Stack:** Python 3.13、pandas、NumPy、Pydantic/dataclasses、pytest、JSON/JSONL、Next.js/TypeScript、Apple Silicon macOS、zsh。

---

## 0. 执行纪律

本文件是本次整改的专项目标和实施顺序；仓库开放任务的单一真相源仍是 `TASKS.md`。每完成一个阶段，应把完成证据同步到 `TASKS.md` 和 `STATUS.md`，但不得覆盖其他 agent 的未提交改动。

硬约束：

- 不改变真实样本、成本、`shift(1)`、T+1 或准入阈值来制造“通过”。
- 不直接编辑 `strategy_versions.json`、研究台账或数据湖运行产物。
- 禁止 `git add -A`、`git add .`、`git commit -a`。
- 每个提交只包含一个可独立回滚的意图，并显式列出 stage 文件。
- 每个任务先写失败测试，再写最小实现。
- P0 数据任务未验收前，不采信新的因子排名、回测、Nine-Gate 或生产信号。
- 任何迁移脚本默认 dry-run；写入必须显式传 `--apply`，写前备份并生成审计报告。
- 完整验证命令：

```bash
cd /Users/kiki/astcok/factor_research
PYTHONDONTWRITEBYTECODE=1 bash scripts/test_all.sh
```

---

## 1. 阶段与依赖

| 阶段 | 目标 | 前置条件 | 阶段退出条件 |
|---|---|---|---|
| P0-A | 修复价量单位契约 | 无 | 全市场 `amount/volume/price` 量纲一致 |
| P0-B | 重建污染数据并重算影响面 | P0-A | 干净数据指纹、影响报告、信号重算完成 |
| P0-C | 生产保持封锁直到证据恢复 | P0-B | readiness 能机械识别数据修复状态 |
| P1-A | 建立唯一策略本体 | P0-B | 同一 spec 驱动回测、注册和生产 |
| P1-B | 建立部署清单 | P1-A | 不再存在硬编码“LIVE”事实源 |
| P1-C | 注册和 Nine-Gate 原子化 | P1-A | 未通过完整门禁不可能成为“在册” |
| P1-D | Holdout 单次消费 | P1-C | 重复窥视被机械拒绝 |
| P1-E | 控制面 fail-closed | P1-B、P1-C | 生产与 UI 使用同一治理裁决 |
| P1-F | 反馈版本化 | P1-B | decay、paper、data report 与部署版本一致 |
| P2-A | T+1 执行语义对齐 | P1-A | 回测和模拟盘成交时点一致 |
| P2-B | 诚实的 WF/CV | P1-C、P2-A | 固定公式与可训练模型使用不同验证语义 |
| P2-C | 测试、日志和 UI 收敛 | 以上任务 | 全量发现测试通过，无默认演示污染 |

---

## Task 1：建立统一价量单位契约

**目的：** 明确数据湖 canonical 单位为 `volume=股`、`amount=元`、`raw_close=元/股`，删除按股票板块猜测单位的逻辑。

**Files:**

- Create: `factor_research/lake/units.py`
- Create: `factor_research/tests/test_price_unit_contract.py`
- Modify: `factor_research/lake/sources/tushare_price.py`
- Modify: `factor_research/lake/load_lake.py`
- Modify: `factor_research/strategies/small_cap.py`
- Modify: `factor_research/tests/test_star_exclude.py`

- [ ] **Step 1: 写单位契约失败测试**

测试必须覆盖主板、创业板、科创板，禁止再出现“仅 688 特殊除以 100”的规则。

```python
import pandas as pd

from lake.units import PriceUnitContract, implied_amount


def test_canonical_price_units_are_shares_yuan_and_yuan_per_share():
    assert PriceUnitContract.volume == "share"
    assert PriceUnitContract.amount == "CNY"
    assert PriceUnitContract.raw_close == "CNY_per_share"


def test_implied_amount_has_no_board_specific_branch():
    volume = pd.DataFrame(
        [[1000.0, 1000.0, 1000.0]],
        index=pd.to_datetime(["2026-06-18"]),
        columns=["000001", "300750", "688256"],
    )
    raw_close = pd.DataFrame(
        [[10.0, 20.0, 30.0]],
        index=volume.index,
        columns=volume.columns,
    )
    expected = pd.DataFrame(
        [[10000.0, 20000.0, 30000.0]],
        index=volume.index,
        columns=volume.columns,
    )
    pd.testing.assert_frame_equal(implied_amount(volume, raw_close), expected)
```

- [ ] **Step 2: 运行测试并确认失败**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest tests/test_price_unit_contract.py -q
```

Expected: FAIL，原因是 `lake.units` 尚不存在。

- [ ] **Step 3: 实现 canonical 单位模块**

`lake/units.py` 提供纯函数，不读写数据湖：

```python
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class PriceUnitContract:
    volume: str = "share"
    amount: str = "CNY"
    raw_close: str = "CNY_per_share"


def implied_amount(volume: pd.DataFrame, raw_close: pd.DataFrame) -> pd.DataFrame:
    return volume * raw_close.reindex(index=volume.index, columns=volume.columns)


def amount_ratio(
    volume: pd.DataFrame,
    raw_close: pd.DataFrame,
    amount: pd.DataFrame,
) -> pd.DataFrame:
    implied = implied_amount(volume, raw_close).replace(0.0, float("nan"))
    return amount.reindex_like(implied) / implied
```

- [ ] **Step 4: 删除板块特例并统一消费者**

实施规则：

- `tushare_price.fetch_new_day()` 保持 `vol * 100`，因为 Tushare `vol` 是手，写湖时转换为股。
- `load_lake.load_prices()` 不再调用 `_normalize_star_volume()`。
- 删除 `_normalize_star_volume()`。
- `strategies.small_cap.load_price_panels()` 优先加载湖内 `amount`；只有明确缺失时才用 `implied_amount(volume, raw_close)` 补值。
- 补值时不再乘 100。
- `test_star_exclude.py` 只测试科创板显式 universe 排除，不再测试虚假的 volume 特例。

- [ ] **Step 5: 运行单位与策略加载测试**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest \
  tests/test_price_unit_contract.py \
  tests/test_star_exclude.py \
  tests/test_data_layer.py \
  test_load_lake.py -q
```

Expected: PASS；测试中三个板块使用相同公式。

- [ ] **Step 6: 运行分层守卫**

```bash
cd /Users/kiki/astcok/factor_research
python3 scripts/ci/check_layer_deps.py
python3 scripts/ci/check_lake_writers.py
```

Expected: 两个守卫均 PASS。

- [ ] **Step 7: 原子提交**

```bash
git add \
  factor_research/lake/units.py \
  factor_research/lake/sources/tushare_price.py \
  factor_research/lake/load_lake.py \
  factor_research/strategies/small_cap.py \
  factor_research/tests/test_price_unit_contract.py \
  factor_research/tests/test_star_exclude.py
git diff --cached --stat
git diff --cached
git commit -m "fix(data): unify price volume and amount units

Remove board-specific volume normalization and establish shares/yuan
as the canonical lake contract so amount-derived factors use one
physical unit across all A-share boards."
```

---

## Task 2：增加数据湖量纲写入不变量

**目的：** 在错误数据落盘前阻断，而不是依靠研究结果异常后人工发现。

**Files:**

- Modify: `factor_research/lake/invariants.py`
- Modify: `factor_research/scripts/data/update_lake.py`
- Create: `factor_research/tests/test_price_amount_invariant.py`
- Modify: `factor_research/scripts/test_all.sh`

- [ ] **Step 1: 写失败测试**

```python
import pandas as pd
import pytest

from lake.invariants import PriceAmountInvariantError, validate_price_amount_units


def _frame(amount_multiplier: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2026-06-18"] * 3),
            "code": ["000001", "300750", "688256"],
            "raw_close": [10.0, 20.0, 30.0],
            "volume": [1000.0, 1000.0, 1000.0],
            "amount": [
                10_000.0 * amount_multiplier,
                20_000.0 * amount_multiplier,
                30_000.0 * amount_multiplier,
            ],
        }
    )


def test_price_amount_invariant_accepts_canonical_units():
    report = validate_price_amount_units(_frame(1.0))
    assert report["passed"] is True
    assert report["median_ratio"] == pytest.approx(1.0)


def test_price_amount_invariant_rejects_hundredfold_error():
    with pytest.raises(PriceAmountInvariantError):
        validate_price_amount_units(_frame(100.0))
```

- [ ] **Step 2: 实现量纲不变量**

`validate_price_amount_units()` 必须：

- 使用 `amount / (volume * raw_close)`。
- 丢弃停牌、零成交和缺失行。
- 样本少于 100 行时返回 `insufficient_sample`，不得伪报通过。
- 中位比率必须位于 `[0.90, 1.10]`。
- P95 绝对相对误差必须不超过 `0.20`。
- 按板块分别报告 `main`、`chinext`、`star`，任一有效板块失败则整体失败。
- 抛出的异常包含日期、板块、中位比率和样本数。

- [ ] **Step 3: 接到唯一写入口**

在 `update_lake.py` 合并增量数据、写 parquet 之前：

1. 把增量复权行与当日 `raw_close` 对齐。
2. 调用 `validate_price_amount_units()`。
3. 失败时不写逐只文件、不 compact 大表，日更状态为 `failed`。
4. 告警 payload 使用类别 `price_unit_contract`。

- [ ] **Step 4: 纳入一键检查**

`scripts/test_all.sh` 增加：

```bash
echo ""
echo "=== test_price_unit_contract.py (价量 canonical 单位) ==="
python3 -m pytest tests/test_price_unit_contract.py -q

echo ""
echo "=== test_price_amount_invariant.py (成交额物理量纲写入闸门) ==="
python3 -m pytest tests/test_price_amount_invariant.py -q
```

- [ ] **Step 5: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest tests/test_price_amount_invariant.py tests/test_lake_invariants.py -q
python3 scripts/ci/check_lake_writers.py
```

Expected: PASS。

- [ ] **Step 6: 原子提交**

```bash
git add \
  factor_research/lake/invariants.py \
  factor_research/scripts/data/update_lake.py \
  factor_research/tests/test_price_amount_invariant.py \
  factor_research/scripts/test_all.sh
git diff --cached --stat
git diff --cached
git commit -m "fix(data): block inconsistent price amount units at write time

Validate amount against shares times raw price for every board before
incremental data can enter the canonical lake."
```

---

## Task 3：审计、重建并验证受污染价量数据

**目的：** 修代码不等于修数据；必须确定污染起点、重建范围和研究影响。

**Files:**

- Create: `factor_research/scripts/repair/audit_price_units.py`
- Create: `factor_research/scripts/repair/rebuild_price_units.py`
- Create: `factor_research/tests/test_rebuild_price_units.py`
- Runtime output, not committed:
  - `factor_research/reports/data/price_unit_audit.json`
  - `factor_research/reports/data/price_unit_rebuild.json`
  - `factor_research/data_lake/backups/price_units_YYYYMMDDTHHMMSS/`

- [ ] **Step 1: 写重建函数失败测试**

测试使用临时 parquet，验证：

- dry-run 不修改源文件。
- `--apply` 只改量纲错误日期。
- 重跑幂等。
- 备份包含修改前文件。
- 修复后 `amount/(volume*raw_close)` 接近 1。

- [ ] **Step 2: 实现只读审计脚本**

命令：

```bash
cd /Users/kiki/astcok/factor_research
python3 scripts/repair/audit_price_units.py \
  --start 2026-06-01 \
  --output reports/data/price_unit_audit.json
```

报告必须包含：

- 每日、每板块样本数。
- ratio 的 median/P05/P95。
- 首个连续异常日期。
- 异常代码数量。
- `daily_all.parquet` 与逐只 parquet 是否一致。
- 建议重建日期范围。
- 数据文件内容指纹。

- [ ] **Step 3: 实现 dry-run 优先的重建脚本**

重建策略：

- 以 Tushare 原始 `daily.amount` 和 `daily.vol` 为事实源。
- 输出 canonical `volume=vol*100`、`amount=amount*1000`。
- 不使用复权价反推成交额。
- 同时修复逐只 parquet 和 `daily_all.parquet`，禁止只修一侧。
- 写入前备份；写入后运行湖不变量和指纹更新。
- 默认 dry-run；只有 `--apply` 才落盘。

命令：

```bash
INCIDENT_START="$(python3 -c 'import json; print(json.load(open("reports/data/price_unit_audit.json"))["first_bad_date"])')"
python3 scripts/repair/rebuild_price_units.py \
  --start "$INCIDENT_START" \
  --end 2026-06-20
```

Expected: 只输出拟修改文件、行数和 hash，不写数据。

应用命令：

```bash
python3 scripts/repair/rebuild_price_units.py \
  --start "$INCIDENT_START" \
  --end 2026-06-20 \
  --apply
```

- [ ] **Step 4: 运行重建后物理验证**

```bash
python3 scripts/repair/audit_price_units.py \
  --start "$INCIDENT_START" \
  --output reports/data/price_unit_audit_after.json
```

验收：

- main、chinext、star 的 median ratio 均在 `[0.90, 1.10]`。
- 任一板块 P95 绝对相对误差不超过 `0.20`。
- 逐只文件与大表同日期同代码的 `volume/amount` 相等。
- 第二次 dry-run 报告 `planned_changes=0`。

- [ ] **Step 5: 提交代码，不提交备份和运行产物**

```bash
git add \
  factor_research/scripts/repair/audit_price_units.py \
  factor_research/scripts/repair/rebuild_price_units.py \
  factor_research/tests/test_rebuild_price_units.py
git diff --cached --stat
git diff --cached
git commit -m "feat(data): add auditable price unit lake repair

Provide dry-run-first audit and idempotent rebuild tooling for both
per-symbol and compact price stores without committing lake artifacts."
```

---

## Task 4：量化污染影响并重新建立研究基线

**目的：** 明确哪些信号、回测、Nine-Gate 和注册证据必须作废重算。

**Files:**

- Create: `factor_research/scripts/research/price_unit_blast_radius.py`
- Create: `factor_research/tests/test_price_unit_blast_radius.py`
- Runtime output, not committed:
  - `factor_research/reports/research/price_unit_blast_radius.json`
  - `factor_research/reports/research/price_unit_blast_radius.md`

- [ ] **Step 1: 写影响比较失败测试**

比较器必须输出：

- Top-N overlap 和 Jaccard。
- 因子截面 Spearman。
- 日收益差、累计收益差。
- 年化、Sharpe、最大回撤差。
- 受影响策略、版本和证据日期。

- [ ] **Step 2: 实现双口径只读回放**

脚本同时计算：

1. 备份中的污染口径。
2. 重建后的 canonical 口径。

至少覆盖：

- `illiquidity/v3.1`
- `small-cap-size/v2.0`
- `illiquidity-large-cap/v1.0`
- 依赖 `amount` 的 AutoResearch 候选
- 当前生产日信号 Top25

- [ ] **Step 3: 定义机械失效规则**

任一条件成立即把旧证据标记为 `INVALIDATED_BY_DATA_UNIT_INCIDENT`：

- Top25 overlap `< 0.80`。
- 因子 Spearman `< 0.95`。
- 年化差绝对值 `> 2%`。
- Sharpe 差绝对值 `> 0.10`。
- 最大回撤差绝对值 `> 2%`。

失效动作必须通过 registry/governance API 完成，不得直接编辑 JSON：

- 暂不自动退役。
- 在版本证据中追加 incident 引用。
- readiness 阻断该版本，直到 Nine-Gate 和部署证据重算完成。

- [ ] **Step 4: 重跑当前生产策略证据**

```bash
cd /Users/kiki/astcok/factor_research
python3 scripts/research/run_nine_gates_all.py \
  --strategy illiquidity \
  --version v3.1 \
  --persist
python3 run_daily.py --no-update
```

验收：

- 新信号使用 canonical amount。
- 新 Nine-Gate 记录包含新数据指纹。
- 不覆盖旧证据；旧证据保留并标记失效原因。

- [ ] **Step 5: 原子提交代码**

```bash
git add \
  factor_research/scripts/research/price_unit_blast_radius.py \
  factor_research/tests/test_price_unit_blast_radius.py
git diff --cached --stat
git diff --cached
git commit -m "feat(research): quantify price unit incident blast radius

Compare contaminated and canonical factor, holdings, and return paths
and mechanically invalidate evidence whose conclusions changed."
```

---

## Task 5：定义不可变 ExecutableStrategySpec

**目的：** 让“策略”从字符串和重复公式升级为可哈希、可复现、可执行的领域实体。

**Files:**

- Create: `factor_research/core/strategy_spec.py`
- Create: `factor_research/tests/test_strategy_spec.py`
- Modify: `factor_research/strategy_registry.py`
- Modify: `factor_research/tests/test_governance_integrity.py`

- [ ] **Step 1: 写 spec 稳定性失败测试**

```python
from core.strategy_spec import ExecutableStrategySpec


def _spec():
    return ExecutableStrategySpec(
        family="illiquidity",
        version="v3.1",
        universe={"market": "A_SHARE", "exclude_star": False},
        data={"price_units": "shares_yuan", "warmup_start": "2010-01-01"},
        factor={"type": "amihud_illiquidity", "window": 20, "shift": 1},
        selection={"top_n": 25, "rebalance_days": 20},
        timing={"type": "pure_trend_band", "ma": 16, "cap": 1.5},
        policy={"veto": "salience_covariance", "veto_q": 0.30},
        execution={"fill": "T_PLUS_1_CLOSE", "cost_model": "A_SHARE_STANDARD_V1"},
    )


def test_spec_hash_is_stable_under_dict_key_order():
    left = _spec()
    right = ExecutableStrategySpec.from_dict(dict(reversed(list(left.to_dict().items()))))
    assert left.spec_hash == right.spec_hash


def test_identity_includes_execution_semantics():
    left = _spec()
    changed = left.replace(execution={**left.execution, "fill": "T_PLUS_1_OPEN"})
    assert left.spec_hash != changed.spec_hash
```

- [ ] **Step 2: 实现纯数据 spec**

要求：

- `frozen=True`。
- JSON canonical serialization 使用排序 key 和稳定浮点表示。
- `spec_hash = sha256(canonical_json)`。
- 禁止保存 lambda、函数对象、绝对本机路径或动态日期。
- `validate()` 检查：
  - family/version 非空。
  - factor 必须有 `type` 和 `shift>=1`。
  - execution.fill 必须属于显式枚举。
  - cost model 必须命名。
  - selection 的 top_n/rebalance_days 为正数。

- [ ] **Step 3: 扩展注册表 schema**

`strategy_registry.register()` 新增必填参数：

```python
spec: dict
spec_hash: str
```

注册时执行：

```python
parsed = ExecutableStrategySpec.from_dict(spec)
if parsed.spec_hash != spec_hash:
    raise ValueError("strategy spec hash mismatch")
if parsed.family != family or parsed.version != version:
    raise ValueError("strategy identity mismatch")
```

历史版本迁移前可读取旧记录，但旧记录不得新晋级为“在册”。

- [ ] **Step 4: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest tests/test_strategy_spec.py tests/test_governance_integrity.py -q
python3 scripts/ci/check_layer_deps.py
```

- [ ] **Step 5: 原子提交**

```bash
git add \
  factor_research/core/strategy_spec.py \
  factor_research/strategy_registry.py \
  factor_research/tests/test_strategy_spec.py \
  factor_research/tests/test_governance_integrity.py
git diff --cached --stat
git diff --cached
git commit -m "feat(strategy): introduce immutable executable strategy specs

Bind strategy identity to data, factor, policy, timing, cost, and fill
semantics with a stable hash shared by registry and production."
```

---

## Task 6：建立 canonical 策略构建器，删除公式复制

**目的：** 同一个 spec 必须生成同一 factor、timing、weights 和 Signal。

**Files:**

- Create: `factor_research/strategies/executable.py`
- Create: `factor_research/strategies/catalog.py`
- Create: `factor_research/tests/test_executable_strategy.py`
- Modify: `factor_research/portfolio/strategy_runners.py`
- Modify: `factor_research/run_daily.py`

- [ ] **Step 1: 写跨入口一致性失败测试**

测试固定小面板，断言：

- catalog 构建器和生产构建器得到相同 factor。
- 相同 spec 得到相同调仓日和持仓。
- 任何入口报告相同 `spec_hash`。
- `run_daily.py` 不再直接实例化 `AmihudIlliq` 或手写 Band 公式。
- `portfolio/strategy_runners.py` 不再保留 `_f_illiquidity` 复制实现。

- [ ] **Step 2: 实现 catalog**

`strategies/catalog.py` 只做确定性映射：

```python
FACTOR_BUILDERS = {
    "amihud_illiquidity": build_amihud_illiquidity,
    "small_cap_amount": build_small_cap_amount,
}

TIMING_BUILDERS = {
    "pure_trend_band": build_pure_trend_band,
    "ma_trend": build_ma_trend,
}

POLICY_BUILDERS = {
    "none": apply_no_policy,
    "salience_covariance": apply_salience_veto,
}
```

未知类型必须抛 `UnsupportedStrategyComponent`，不得静默 fallback。

- [ ] **Step 3: 实现 executable builder**

统一入口：

```python
@dataclass(frozen=True)
class ExecutableStrategy:
    factor: pd.DataFrame
    timing: pd.Series
    scheduled_weights: dict[pd.Timestamp, pd.Series]
    signal: Signal
    spec_hash: str
    diagnostics: dict


def build_executable_strategy(
    spec: ExecutableStrategySpec,
    prices: PricePanel,
) -> ExecutableStrategy:
    spec.validate()
    factor_builder = resolve_factor_builder(spec.factor["type"])
    timing_builder = resolve_timing_builder(spec.timing["type"])
    policy_builder = resolve_policy_builder(spec.policy.get("veto", "none"))
    factor = factor_builder(prices, spec.factor)
    timing, timing_diagnostics = timing_builder(prices, spec.timing)
    filtered_factor = policy_builder(factor, prices, spec.policy)
    weights = build_rebalance_weights(
        filtered_factor,
        prices.close,
        top_n=int(spec.selection["top_n"]),
        rebalance_days=int(spec.selection["rebalance_days"]),
    )
    signal = Signal(
        weights=weights,
        timing=timing,
        family=spec.family,
        version=spec.version,
        execution_timing=spec.execution["fill"],
    )
    return ExecutableStrategy(
        factor=factor,
        timing=timing,
        scheduled_weights=weights,
        signal=signal,
        spec_hash=spec.spec_hash,
        diagnostics={"timing": timing_diagnostics},
    )
```

返回对象必须包含：

- `factor`
- `timing`
- `scheduled_weights`
- `signal`
- `spec_hash`
- `diagnostics`

- [ ] **Step 4: 替换研究和生产重复实现**

- `portfolio/strategy_runners.py` 只保留研究组合编排，不再定义策略公式。
- `run_daily.py` 从当前部署加载 spec，调用 `build_executable_strategy()`。
- 日信号写入 `family`、`version`、`spec_hash`、`deployment_id`。

- [ ] **Step 5: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest tests/test_executable_strategy.py tests/test_e2e.py -q
python3 scripts/ci/check_layer_deps.py
```

- [ ] **Step 6: 原子提交**

```bash
git add \
  factor_research/strategies/executable.py \
  factor_research/strategies/catalog.py \
  factor_research/portfolio/strategy_runners.py \
  factor_research/run_daily.py \
  factor_research/tests/test_executable_strategy.py
git diff --cached --stat
git diff --cached
git commit -m "refactor(strategy): execute one canonical strategy definition

Replace duplicated factor and timing formulas with a spec-driven builder
used by research portfolio runners and daily production signals."
```

---

## Task 7：建立 DeploymentManifest 并移除硬编码 LIVE

**目的：** 区分“已注册策略”和“当前部署”，让启停动作真正控制生产执行器。

**Files:**

- Create: `factor_research/runtime/deployment.py`
- Create: `factor_research/deployments/production.json`
- Create: `factor_research/tests/test_deployment_manifest.py`
- Modify: `factor_research/portfolio/strategy_runners.py`
- Modify: `factor_research/run_daily.py`
- Modify: `factor_research/portfolio/regime_gate.py`

- [ ] **Step 1: 写部署约束失败测试**

覆盖：

- manifest 中每条腿必须引用 `family/version/spec_hash`。
- 只有 registry 状态为“在册”且 spec hash 一致才能激活。
- retired/候选版本不能激活。
- 防御腿权重上限属于 portfolio policy，不属于单策略 spec。
- registry 状态变化后，下一次加载立即阻断部署。

- [ ] **Step 2: 定义 manifest schema**

```json
{
  "deployment_id": "prod-a-share-v1",
  "environment": "production",
  "status": "active",
  "portfolio_policy": {
    "type": "regime_rotation",
    "defensive_cap": 1.0
  },
  "legs": [
    {
      "family": "illiquidity",
      "version": "v3.1",
      "spec_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "role": "equity_alpha"
    },
    {
      "family": "gov-bond-etf",
      "version": "v1.0",
      "spec_hash": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
      "role": "defensive"
    }
  ]
}
```

上面的 hash 仅用于说明字段格式，不是任何策略的有效身份。实际 `production.json` 必须由迁移工具从 canonical spec 生成，不得手填或复用示例值。

- [ ] **Step 3: 实现部署加载器**

`load_active_deployment()` 必须：

- 校验 JSON schema。
- 逐腿查询 registry。
- 比较 status 和 spec hash。
- 返回不可变 deployment 对象。
- 任一腿失败时抛 `DeploymentNotReady`。

- [ ] **Step 4: 移除硬编码状态**

- `LIVE_STRATEGIES` 重命名为 `RESEARCH_STRATEGY_CATALOG`，不得再表达生产事实。
- `active_strategies()` 从 deployment manifest 读取。
- `regime_gate.py` 删除“现行 LIVE”硬编码描述。
- `run_daily.py` 只执行 manifest 指定组合。

- [ ] **Step 5: 验证 registry 退役能停止执行**

测试中使用临时 registry：

1. active deployment 可加载。
2. 把引用版本改成退役。
3. 再次加载抛 `DeploymentNotReady`。
4. `run_daily` 不发布正式信号。

- [ ] **Step 6: 原子提交**

```bash
git add \
  factor_research/runtime/deployment.py \
  factor_research/deployments/production.json \
  factor_research/portfolio/strategy_runners.py \
  factor_research/portfolio/regime_gate.py \
  factor_research/run_daily.py \
  factor_research/tests/test_deployment_manifest.py
git diff --cached --stat
git diff --cached
git commit -m "feat(runtime): drive production from a validated deployment manifest

Separate registered strategies from active deployments so registry
retirement and spec mismatches mechanically stop production execution."
```

---

## Task 8：把完整准入改成注册前原子事务

**目的：** 候选只有在完整证据通过后才能一次性成为“在册”；失败结果保存为候选证据，不产生短暂假 LIVE。

**Files:**

- Create: `factor_research/workflow/admission.py`
- Create: `factor_research/tests/test_atomic_admission.py`
- Modify: `factor_research/workflow/promote.py`
- Modify: `factor_research/workflow/phase4_register.py`
- Modify: `factor_research/strategy_registry.py`
- Modify: `factor_research/scripts/ci/check_no_force_promote.py`

- [ ] **Step 1: 写原子性失败测试**

测试场景：

- Phase1 失败：不写“在册”。
- Nine-Gate 一门失败：不写“在册”。
- holdout 缺失：不写“在册”。
- evidence 缺失：不写“在册”。
- marginal 需要但失败：不写“在册”。
- registry 写入异常：不存在半完成 deployment 或 model card。
- 全部通过：只发生一次 registry 状态变更。

- [ ] **Step 2: 定义 AdmissionEvidence**

```python
@dataclass(frozen=True)
class AdmissionEvidence:
    phase1: dict
    phase2: dict
    phase3: dict
    nine_gate: dict
    holdout: dict
    marginal: dict
    experiment_ids: tuple[str, ...]
    data_fingerprint: str
    spec_hash: str
```

`admission.py` 提供：

```python
@dataclass(frozen=True)
class AdmissionDecision:
    approved: bool
    target_status: str
    blocking_reasons: tuple[str, ...]


def evaluate_admission(
    spec: ExecutableStrategySpec,
    evidence: AdmissionEvidence,
    *,
    admission_track: str,
    require_marginal: bool,
) -> AdmissionDecision:
    reasons: list[str] = []
    if evidence.spec_hash != spec.spec_hash:
        reasons.append("spec_hash_mismatch")
    if evidence.phase1.get("status") != "PASS":
        reasons.append("phase1_failed")
    if evidence.phase3.get("verdict") != "PASS":
        reasons.append("phase3_failed")
    if evidence.nine_gate.get("passed_all") is not True:
        reasons.append("nine_gate_not_passed")
    if evidence.holdout.get("peek_count") != 1:
        reasons.append("holdout_not_single_use")
    if not evidence.experiment_ids:
        reasons.append("evidence_missing")
    if require_marginal and evidence.marginal.get("verdict") != "PASS":
        reasons.append("marginal_failed")
    if admission_track not in {"standalone", "diversifier"}:
        reasons.append("invalid_admission_track")
    return AdmissionDecision(
        approved=not reasons,
        target_status="在册" if not reasons else "候选",
        blocking_reasons=tuple(reasons),
    )


def commit_admission(
    spec: ExecutableStrategySpec,
    evidence: AdmissionEvidence,
    decision: AdmissionDecision,
) -> RegistrationReport:
    return register_validated_strategy(
        spec=spec,
        evidence=evidence,
        status=decision.target_status,
        blocking_reasons=decision.blocking_reasons,
    )
```

- [ ] **Step 3: 固化准入不变量**

“在册”必须同时满足：

- Phase1 无失败。
- Phase2 必需段完成。
- Phase3 verdict PASS。
- Nine-Gate `passed_all is True`。
- required gates 均有报告且无 FAIL。
- holdout `peek_count == 1`。
- holdout DSR 在可计算时显著。
- evidence experiment IDs 非空。
- data fingerprint 与 spec 引用一致。
- standalone 必须 hit；diversifier 必须有正 marginal 证据。

- [ ] **Step 4: 删除标准路径可选开关**

从 `promote_spec()` 删除：

- `run_nine_gate=False`
- `run_marginal=False`
- 空 `holdout_id` 软通过
- 标准路径 `force=True`

如果保留历史修复入口，必须改名为 `admin_repair_candidate_metadata()`，且永远不能授予“在册”状态。

- [ ] **Step 5: 加强静态守卫**

`check_no_force_promote.py` 扫描所有 `scripts/ops/`、`services/actions/`、`apps/`：

- 禁止任何调用向 `promote_spec` 传入关键字参数 `force=True`。
- 禁止省略 holdout。
- 禁止直接调用 `Phase4Register.register()` 授予“在册”。
- 禁止 Nine-Gate 在 register 后运行。

- [ ] **Step 6: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest \
  tests/test_atomic_admission.py \
  tests/test_promote_nine_gate.py \
  tests/test_no_force_promote_guard.py \
  tests/test_registry_evidence_guard.py -q
python3 scripts/ci/check_no_force_promote.py
python3 scripts/ci/check_registry_evidence.py
```

- [ ] **Step 7: 原子提交**

```bash
git add \
  factor_research/workflow/admission.py \
  factor_research/workflow/promote.py \
  factor_research/workflow/phase4_register.py \
  factor_research/strategy_registry.py \
  factor_research/scripts/ci/check_no_force_promote.py \
  factor_research/tests/test_atomic_admission.py \
  factor_research/tests/test_promote_nine_gate.py \
  factor_research/tests/test_no_force_promote_guard.py \
  factor_research/tests/test_registry_evidence_guard.py
git diff --cached --stat
git diff --cached
git commit -m "fix(governance): make strategy admission atomic and evidence complete

Evaluate Nine-Gate, holdout, marginal contribution, and reproducibility
before a single registry transition can grant active registration."
```

---

## Task 9：建立单一 Nine-Gate 裁决策略

**目的：** 消除“DSR 通过等于 Nine-Gate 通过”的错误降维。

**Files:**

- Create: `factor_research/core/analysis/nine_gate_policy.py`
- Create: `factor_research/tests/test_nine_gate_policy.py`
- Modify: `factor_research/core/analysis/nine_gates.py`
- Modify: `factor_research/services/read/governance.py`
- Modify: `factor_research/runtime/production_readiness.py`
- Modify: `factor_research/services/read/trade_readiness.py`
- Modify: `factor_research/tests/test_nine_gates.py`
- Modify: `factor_research/tests/test_production_readiness.py`

- [ ] **Step 1: 写裁决矩阵失败测试**

必须覆盖：

| passed_all | Gate4 | PBO | Gate7 | 结果 |
|---|---|---|---|---|
| true | PASS | low | PASS | approved |
| false | PASS | high | WARN | blocked |
| missing | PASS | missing | missing | pending |
| false | FAIL | any | any | blocked |
| run error | any | any | any | blocked |

- [ ] **Step 2: 实现唯一 policy**

```python
@dataclass(frozen=True)
class NineGateDecision:
    code: str
    approved: bool
    audited: bool
    blocking_reasons: tuple[str, ...]


def decide_nine_gate(summary: dict) -> NineGateDecision:
    if summary.get("status") == "FAILED_TO_RUN":
        return NineGateDecision("RUN_FAILED", False, False, ("nine_gate_run_failed",))
    required = {"0", "1", "2", "3", "4", "5", "6", "7", "7A", "8"}
    reports = {str(k): v for k, v in (summary.get("gates") or {}).items()}
    missing = sorted(required - reports.keys())
    if missing:
        return NineGateDecision(
            "PENDING",
            False,
            False,
            tuple(f"missing_gate_{gate}" for gate in missing),
        )
    failures = tuple(
        f"gate_{gate}_{report.get('verdict', 'UNKNOWN').lower()}"
        for gate, report in reports.items()
        if report.get("verdict") in {"FAIL", "FAILED_TO_RUN"}
    )
    if summary.get("passed_all") is not True or failures:
        return NineGateDecision(
            "FAILED",
            False,
            True,
            failures or ("passed_all_false",),
        )
    return NineGateDecision("PASSED", True, True, ())
```

规则：

- `status=FAILED_TO_RUN` → blocked。
- required reports 缺失 → pending。
- `passed_all is not True` → blocked。
- 任一 required gate verdict FAIL → blocked。
- WARN 是否允许必须由显式 policy 配置，生产默认不允许 Gate7 极端 regime WARN。
- PBO high 不能被 DSR PASS 覆盖。

- [ ] **Step 3: 所有消费者调用同一 policy**

删除以下重复逻辑：

- `services/read/governance.py::_nine_gate_audit_state`
- `runtime/production_readiness.py::_nine_gate_audit_state`
- `trade_readiness` 中 DSR-only 字段推断

UI 可继续展示 DSR，但审批状态来自 `NineGateDecision`。

- [ ] **Step 4: 修复 stale 数量测试**

`test_nine_gates.py` 不再断言固定报告数 9；改为断言必需 gate ID 集合：

```python
assert {r.gate_id for r in reports} == {0, 1, 2, 3, 4, 5, 6, 7, "7A", 8}
```

- [ ] **Step 5: 将 trade readiness 改为 fail-closed**

异常默认值：

- data exception → `unknown`，阻断。
- risk exception → `unknown`，阻断。
- governance exception → `governance_unknown`，阻断。
- production readiness exception → `allowed=False`。
- 未计算 factor health、cost、liquidity 必须标 `unknown`，不得伪造 normal/acceptable。

- [ ] **Step 6: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest \
  tests/test_nine_gate_policy.py \
  tests/test_nine_gates.py \
  tests/test_production_readiness.py \
  tests/test_governance_integrity.py \
  tests/test_risk_phase3.py -q
```

- [ ] **Step 7: 原子提交**

```bash
git add \
  factor_research/core/analysis/nine_gate_policy.py \
  factor_research/core/analysis/nine_gates.py \
  factor_research/services/read/governance.py \
  factor_research/runtime/production_readiness.py \
  factor_research/services/read/trade_readiness.py \
  factor_research/tests/test_nine_gate_policy.py \
  factor_research/tests/test_nine_gates.py \
  factor_research/tests/test_production_readiness.py
git diff --cached --stat
git diff --cached
git commit -m "fix(governance): require the complete Nine-Gate decision

Replace DSR-only approval with one fail-closed policy shared by registry,
production readiness, trade readiness, and governance views."
```

---

## Task 10：强制 Holdout 单次消费与调度队列隔离

**目的：** 让“唯一一次金库验证”成为系统不变量，而不是 warning。

**Files:**

- Modify: `factor_research/governance/holdout.py`
- Modify: `factor_research/factory/autoresearch/repositories.py`
- Modify: `factor_research/scripts/ops/scheduled_factor_search.py`
- Modify: `factor_research/scripts/ci/check_holdout_compliance.py`
- Modify: `factor_research/tests/test_loop_foundations.py`
- Create: `factor_research/tests/test_holdout_single_use.py`

- [ ] **Step 1: 写重复消费失败测试**

规则：

- 首次验证写一条记录并返回 `peek_count=1`。
- 同一 `candidate_id + spec_hash + data_fingerprint` 重试返回原记录，保证任务幂等，不新增 peek。
- 同 candidate 但 spec 或数据指纹不同，必须使用新 candidate identity。
- 同 identity 第二次主动评估抛 `HoldoutAlreadyConsumed`。

- [ ] **Step 2: 扩展 holdout 记录身份**

每条记录增加：

- `candidate_id`
- `spec_hash`
- `data_fingerprint`
- `holdout_boundary`
- `return_hash`
- `consumed_at`

唯一键：

```text
candidate_id + spec_hash + data_fingerprint + holdout_boundary
```

- [ ] **Step 3: 修改调度器只处理本轮新增 pending**

- 岛搜索开始前记录 queue snapshot。
- 搜索结束后只取本轮新增且状态为 `PROMOTED_TO_REVIEW` 的 fingerprint。
- 禁止 `review_queue.all()` 触发全历史重审。
- 已批准、拒绝、已晋级候选永不进入 holdout 路径。

- [ ] **Step 4: 加强守卫**

静态守卫拒绝：

- 自动审计路径调用 `ReviewQueue.all()`。
- 捕获并吞掉 `HoldoutAlreadyConsumed` 后继续晋级。
- holdout 记录缺少 spec/data identity。

- [ ] **Step 5: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest \
  tests/test_holdout_single_use.py \
  tests/test_loop_foundations.py \
  tests/test_autoresearch_engine.py -q
python3 scripts/ci/check_holdout_compliance.py
```

- [ ] **Step 6: 原子提交**

```bash
git add \
  factor_research/governance/holdout.py \
  factor_research/factory/autoresearch/repositories.py \
  factor_research/scripts/ops/scheduled_factor_search.py \
  factor_research/scripts/ci/check_holdout_compliance.py \
  factor_research/tests/test_loop_foundations.py \
  factor_research/tests/test_holdout_single_use.py
git diff --cached --stat
git diff --cached
git commit -m "fix(research): enforce single-use holdout validation

Bind vault consumption to candidate, strategy spec, and data identity
and restrict weekly audits to candidates created in the current run."
```

---

## Task 11：统一 trial 计数语义

**目的：** DSR 的 `n_trials` 来自真实尝试账本，而不是保留版本数量或固定下限。

**Files:**

- Modify: `factor_research/governance/trial_ledger.py`
- Modify: `factor_research/scripts/research/run_nine_gates_all.py`
- Modify: `factor_research/factory/autoresearch/islands.py`
- Create: `factor_research/tests/test_trial_count_semantics.py`

- [ ] **Step 1: 写 trial 计数失败测试**

测试 10 次搜索中仅 2 个保留版本，期望：

```python
assert honest_n_trials("illiquidity") == 10
```

并覆盖：

- 失败候选计入。
- 参数变体计入。
- 语义完全等价且在运行前去重的 AST 不重复计入。
- 不同数据 vintage 的重复实验计入新 trial。

- [ ] **Step 2: 删除 registry 版本数代理**

`run_nine_gates_all.py` 禁止通过 family retained versions 推导 `n_trials`。若账本无记录：

- 状态为 `trial_count_unknown`。
- Nine-Gate 不得 approved。
- 不得用地板 3 或固定 15 代替。

- [ ] **Step 3: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest tests/test_trial_count_semantics.py tests/test_loop_foundations.py -q
```

- [ ] **Step 4: 原子提交**

```bash
git add \
  factor_research/governance/trial_ledger.py \
  factor_research/scripts/research/run_nine_gates_all.py \
  factor_research/factory/autoresearch/islands.py \
  factor_research/tests/test_trial_count_semantics.py
git diff --cached --stat
git diff --cached
git commit -m "fix(research): use the experiment ledger as trial count authority

Count all genuine search attempts for DSR and block approval when the
multiple-testing burden cannot be established."
```

---

## Task 12：版本化 decay、paper 和数据反馈

**目的：** 反馈必须来自当前部署、当前 spec 和可接受时效，执行阻塞必须进入 readiness。

**Files:**

- Modify: `factor_research/runtime/production_readiness.py`
- Modify: `factor_research/governance/decay.py`
- Modify: `factor_research/scripts/ops/decay_monitor.py`
- Modify: `factor_research/portfolio/paper_engine.py`
- Modify: `factor_research/services/read/paper.py`
- Create: `factor_research/tests/test_runtime_feedback_identity.py`

- [ ] **Step 1: 写陈旧/错版本反馈失败测试**

覆盖：

- decay family/version/spec_hash 与 deployment 不一致 → blocked。
- decay 生成时间超过 policy TTL → stale，blocked。
- decay 报告缺少数据指纹 → blocked。
- paper `last_exec.blocked=true` → paper status blocked。
- data triage 缺失或过期 → unknown，blocked。

- [ ] **Step 2: 定义统一反馈 envelope**

所有控制报告至少包含：

```json
{
  "report_type": "decay",
  "generated_at": "2026-06-20T12:00:00+08:00",
  "deployment_id": "prod-a-share-v1",
  "family": "illiquidity",
  "version": "v3.1",
  "spec_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "data_fingerprint": "ca978112ca1bbdcafac231b39a23dc4da786eff8147c4e72b9807785afee48bb",
  "as_of_date": "2026-06-18",
  "status": "green"
}
```

示例 hash 仅说明字段格式；运行报告必须写入当前 deployment 和数据 vintage 的真实计算值。

- [ ] **Step 3: readiness 校验身份和 TTL**

建议 policy：

- decay TTL：8 个自然日。
- data triage TTL：1 个交易日。
- paper execution：必须覆盖最新已发布 signal。
- deployment/spec 不匹配没有宽限期。

- [ ] **Step 4: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest \
  tests/test_runtime_feedback_identity.py \
  tests/test_production_readiness.py \
  tests/test_paper_etf.py -q
```

- [ ] **Step 5: 原子提交**

```bash
git add \
  factor_research/runtime/production_readiness.py \
  factor_research/governance/decay.py \
  factor_research/scripts/ops/decay_monitor.py \
  factor_research/portfolio/paper_engine.py \
  factor_research/services/read/paper.py \
  factor_research/tests/test_runtime_feedback_identity.py
git diff --cached --stat
git diff --cached
git commit -m "fix(runtime): bind monitoring feedback to active deployment identity

Reject stale or mismatched decay, data, and paper execution reports and
surface blocked fills as production readiness failures."
```

---

## Task 13：对齐 T+1 close 成交与收益归属

**目的：** 决策、成交、持有收益和成本必须使用同一时间语义。

**Files:**

- Modify: `factor_research/core/engine.py`
- Modify: `factor_research/core/strategy_spec.py`
- Modify: `factor_research/strategies/small_cap.py`
- Modify: `factor_research/portfolio/paper_engine.py`
- Create: `factor_research/tests/test_execution_timing.py`
- Modify: `factor_research/test_engine.py`

- [ ] **Step 1: 写三日价格路径失败测试**

示例：

- T0 close=100，收盘生成买入决策。
- T1 close=110，T+1 close 成交。
- T2 close=121，首次持仓收益应为 `+10%`，不是同时获得 T0→T1 的 `+10%`。

```python
def test_t_plus_one_close_does_not_capture_pre_fill_return():
    result = run_three_day_case(fill="T_PLUS_1_CLOSE")
    assert result.returns.loc["2026-01-02"] == 0.0
    assert result.returns.loc["2026-01-05"] == pytest.approx(0.10)
```

还应覆盖卖出、成本、换仓和空仓。

- [ ] **Step 2: 明确 Signal 时间字段**

`Signal` 增加：

```python
decision_weights
execution_timing
```

禁止使用含糊的 `effective` 命名。`build_rebalance_weights()` 返回决策日权重，成交延迟由 engine 根据 spec 执行。

- [ ] **Step 3: 修改引擎循环顺序**

T+1 close 语义：

1. 使用昨日收盘后已经成交的持仓计算今日 close-to-close 收益。
2. 今日收盘执行到期目标。
3. 今日记录 turnover 和交易成本。
4. 新持仓从下一交易日收益开始生效。

模拟盘默认 fill mode 同步改成 `T_PLUS_1_CLOSE`；文档和 UI 不得继续写 T+1 open。

- [ ] **Step 4: 重跑受影响基线**

该改动会改变全部策略历史指标，必须：

- 新建数据/执行语义版本。
- 重跑 Nine-Gate。
- 不覆盖旧台账证据。
- 旧 spec hash 自动失效。

- [ ] **Step 5: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest tests/test_execution_timing.py test_engine.py tests/test_paper_etf.py -q
```

- [ ] **Step 6: 原子提交**

```bash
git add \
  factor_research/core/engine.py \
  factor_research/core/strategy_spec.py \
  factor_research/strategies/small_cap.py \
  factor_research/portfolio/paper_engine.py \
  factor_research/tests/test_execution_timing.py \
  factor_research/test_engine.py
git diff --cached --stat
git diff --cached
git commit -m "fix(engine): align backtests with T plus one close fills

Apply target weights only after the fill close so strategies cannot
capture returns that occurred before the simulated trade."
```

---

## Task 14：区分固定公式稳定性测试与真实 Walk-Forward

**目的：** 不再把年度切片或全样本权重切片标成“训练/样本外/净化 CV”。

**Files:**

- Create: `factor_research/core/analysis/rolling_origin.py`
- Modify: `factor_research/workflow/phase3_wf.py`
- Modify: `factor_research/core/analysis/nine_gates.py`
- Modify: `factor_research/factory/autoresearch/walkforward.py`
- Create: `factor_research/tests/test_true_walk_forward.py`

- [ ] **Step 1: 写物理截断失败测试**

spy builder 记录每次收到的最大日期，断言：

- fit 回调永远看不到 test start 之后数据。
- 因子预热可读取 train 历史，但参数选择不可读取 test。
- purge 和 embargo 日期不进入 fit labels。
- test 权重不是从全样本预计算权重切片得到。

- [ ] **Step 2: 定义两种诚实模式**

**固定公式：**

- 名称：`rolling_origin_stability`。
- 不声称训练。
- 每个窗口从历史到 test end 因果重算信号。
- 报告年度稳定性和执行退化。

**可训练/可搜索策略：**

- 名称：`walk_forward_selection`。
- 接口：

```python
fit(train_prices, train_labels) -> FittedSignalFactory
predict(fitted, history_through_test_date) -> Signal
```

- 每折物理截断。
- purge/embargo 作用于训练标签和模型选择。

- [ ] **Step 3: 修改 Gate7 和 Gate7A**

- Gate7 固定公式使用 `rolling_origin_stability`。
- Gate7A 只有提供 fit callback 才执行 purged/embargoed selection CV。
- 无 fit callback 时 Gate7A 返回 `NOT_APPLICABLE`，不得伪造 PASS。
- `passed_all` policy 明确哪些策略要求 Gate7A。

- [ ] **Step 4: 周度 AutoResearch 切到 meta-WF**

调度器调用 `run_autoresearch_walk_forward`：

- 演化只看 cutoff 前。
- 冠军只在 OOS 看一次。
- OOS 结果不得反馈同一轮继续搜索。

- [ ] **Step 5: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest \
  tests/test_true_walk_forward.py \
  tests/test_autoresearch_engine.py \
  tests/test_nine_gates.py -q
```

- [ ] **Step 6: 原子提交**

```bash
git add \
  factor_research/core/analysis/rolling_origin.py \
  factor_research/workflow/phase3_wf.py \
  factor_research/core/analysis/nine_gates.py \
  factor_research/factory/autoresearch/walkforward.py \
  factor_research/scripts/ops/scheduled_factor_search.py \
  factor_research/tests/test_true_walk_forward.py
git diff --cached --stat
git diff --cached
git commit -m "fix(validation): separate rolling stability from true walk forward

Regenerate signals inside each causal window and reserve purged model
selection claims for strategies with an explicit fit boundary."
```

---

## Task 15：统一状态机和控制事件

**目的：** 消除 active/ACTIVE/在册/APPROVED 等平行状态造成的非法组合。

**Files:**

- Create: `factor_research/governance/state_machine.py`
- Create: `factor_research/governance/control_events.py`
- Create: `factor_research/tests/test_control_state_machine.py`
- Modify: `factor_research/strategy_registry.py`
- Modify: `factor_research/model_risk/model_inventory.py`
- Modify: `factor_research/runtime/deployment.py`

- [ ] **Step 1: 写非法转换失败测试**

合法生命周期：

```text
DRAFT → CANDIDATE → VALIDATED → REGISTERED → DEPLOYED
                       │             │            │
                       └→ REJECTED   └→ RETIRED   └→ SUSPENDED
```

测试：

- CANDIDATE 不能直接 DEPLOYED。
- RETIRED 不能重新 DEPLOYED；必须创建新版本。
- SUSPENDED 可在证据恢复后回 DEPLOYED。
- model approval、registry status、deployment status 从同一状态派生。

- [ ] **Step 2: 实现 append-only control event**

事件最少包含：

- event_id
- timestamp
- actor
- family/version/spec_hash
- from_state/to_state
- reason_code
- evidence_refs
- previous_event_hash/event_hash

- [ ] **Step 3: 保留中文展示映射**

内部枚举统一，UI 可映射：

- CANDIDATE → 候选
- REGISTERED → 在册
- RETIRED → 退役
- DEPLOYED → 已部署
- SUSPENDED → 已暂停

禁止业务逻辑直接比较展示文案。

- [ ] **Step 4: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 -m pytest tests/test_control_state_machine.py tests/test_governance_integrity.py -q
```

- [ ] **Step 5: 原子提交**

```bash
git add \
  factor_research/governance/state_machine.py \
  factor_research/governance/control_events.py \
  factor_research/strategy_registry.py \
  factor_research/model_risk/model_inventory.py \
  factor_research/runtime/deployment.py \
  factor_research/tests/test_control_state_machine.py
git diff --cached --stat
git diff --cached
git commit -m "refactor(governance): unify strategy control states

Represent candidate, registration, deployment, suspension, and retirement
as validated transitions backed by an append-only control event chain."
```

---

## Task 16：全量测试发现，禁止“手工列表等于全部测试”

**目的：** 确保新增测试和已有测试默认进入一键检查。

**Files:**

- Modify: `factor_research/scripts/test_all.sh`
- Modify: `factor_research/pyproject.toml`
- Create: `factor_research/scripts/ci/check_test_discovery.py`
- Create: `factor_research/tests/test_test_discovery_guard.py`

- [ ] **Step 1: 写发现完整性失败测试**

守卫扫描：

- `factor_research/test_*.py`
- `factor_research/tests/test_*.py`

并验证这些文件都被 pytest collection 收集；不维护第二份手工清单。

- [ ] **Step 2: 简化 test_all**

保留确定性静态守卫，然后运行：

```bash
python3 -m pytest -q
```

Web 保持：

```bash
cd ../web
npm test
npx tsc --noEmit
npm run lint
```

删除逐文件 Python 调用列表，避免再次漏掉 15 个测试文件。

- [ ] **Step 3: 修复当前全量失败**

`tests/test_nine_gates.py` 使用 gate ID 集合，不再期待 9 个报告。

Pandas warning 必须定位：

- `factors/alpha101.py` 显式指定 `fill_method=None`。
- 测试设置不把已知第三方 warning 误当业务失败，但项目自身 FutureWarning 必须清零。

- [ ] **Step 4: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 scripts/ci/check_test_discovery.py
PYTHONDONTWRITEBYTECODE=1 bash scripts/test_all.sh
```

Expected:

- 全部 Python 测试被收集。
- 当前 `test_nine_gates` 不再失败。
- Web test、TypeScript、lint 全部通过。

- [ ] **Step 5: 原子提交**

```bash
git add \
  factor_research/scripts/test_all.sh \
  factor_research/pyproject.toml \
  factor_research/scripts/ci/check_test_discovery.py \
  factor_research/tests/test_test_discovery_guard.py \
  factor_research/tests/test_nine_gates.py \
  factor_research/factors/alpha101.py
git diff --cached --stat
git diff --cached
git commit -m "test(ci): discover the complete Python test suite

Replace the incomplete hand-maintained test list with pytest discovery
and guard against silently excluded test modules."
```

---

## Task 17：移除控制路径静默异常

**目的：** 优先消除会改变准入、信号、执行或 readiness 结论的 `except/pass`。

**Files:**

- Modify: `factor_research/core/analysis/nine_gates.py`
- Modify: `factor_research/services/read/trade_readiness.py`
- Modify: `factor_research/runtime/production_readiness.py`
- Modify: `factor_research/scripts/ops/scheduled_factor_search.py`
- Create: `factor_research/scripts/ci/check_control_exceptions.py`
- Create: `factor_research/tests/test_control_exception_policy.py`

- [ ] **Step 1: 定义控制路径清单**

守卫至少扫描：

- `core/analysis/nine_gates.py`
- `workflow/`
- `governance/`
- `runtime/`
- `services/read/trade_readiness.py`
- `scripts/ops/`
- `portfolio/paper_engine.py`

- [ ] **Step 2: 禁止无动作捕获**

以下形式在控制路径报错：

```python
except Exception:
    pass
```

允许的异常处理必须同时满足：

- 记录结构化日志。
- 返回明确 `UNKNOWN/FAILED_TO_RUN/BLOCKED`。
- 不把异常转换成通过。

- [ ] **Step 3: Nine-Gate 失败可见化**

每个 gate 异常生成 GateReport：

```python
GateReport(
    gate_id=gate_id,
    passed=False,
    verdict="FAILED_TO_RUN",
    metrics={},
    details=f"{type(error).__name__}: {error}",
    reasons=["gate_execution_failed"],
)
```

- [ ] **Step 4: 验证**

```bash
cd /Users/kiki/astcok/factor_research
python3 scripts/ci/check_control_exceptions.py
python3 -m pytest tests/test_control_exception_policy.py tests/test_nine_gates.py -q
```

- [ ] **Step 5: 原子提交**

```bash
git add \
  factor_research/core/analysis/nine_gates.py \
  factor_research/services/read/trade_readiness.py \
  factor_research/runtime/production_readiness.py \
  factor_research/scripts/ops/scheduled_factor_search.py \
  factor_research/scripts/ci/check_control_exceptions.py \
  factor_research/tests/test_control_exception_policy.py
git diff --cached --stat
git diff --cached
git commit -m "fix(observability): make control path failures explicit

Replace silent exceptions with structured failed states and add a guard
that prevents approval or execution paths from swallowing errors."
```

---

## Task 18：隔离前端演示数据与真实生产视图

**目的：** A 股生产操作台默认只展示真实数据；演示模拟必须显式进入 sandbox。

**Files:**

- Modify: `web/app/portfolio/page.tsx`
- Modify: `web/components/paper/TimeTravelSimulator.tsx`
- Create: `web/components/paper/SimulationModeBanner.tsx`
- Create: `web/components/paper/TimeTravelSimulator.test.mjs`

- [ ] **Step 1: 写默认模式失败测试**

断言：

- portfolio 默认 tab 不是 time travel demo。
- demo 数据不会在未设置 `mode="sandbox"` 时渲染。
- sandbox 页面持续显示“模拟数据，不可用于交易”水印。
- AAPL/NVDA/TSLA 不会出现在 production mode。

- [ ] **Step 2: 改造组件契约**

```tsx
type TimeTravelSimulatorProps =
  | { mode: "production"; snapshots: RealSnapshot[] }
  | { mode: "sandbox"; snapshots?: DemoSnapshot[] };
```

production 缺数据时展示 unavailable，不得 fallback 到美股 mock。

- [ ] **Step 3: 默认真实页面**

- portfolio 默认进入组合概览或今日操作。
- “时空穿梭机”改名“策略模拟沙盒”。
- sandbox 显示固定 banner。

- [ ] **Step 4: 验证**

```bash
cd /Users/kiki/astcok/web
npm test
npx tsc --noEmit
npm run lint
```

- [ ] **Step 5: 原子提交**

```bash
git add \
  web/app/portfolio/page.tsx \
  web/components/paper/TimeTravelSimulator.tsx \
  web/components/paper/SimulationModeBanner.tsx \
  web/components/paper/TimeTravelSimulator.test.mjs
git diff --cached --stat
git diff --cached
git commit -m "fix(web): isolate simulated data from production portfolio views

Make real A-share state the default and require an explicit sandbox mode
with a permanent warning before rendering synthetic US examples."
```

---

## Task 19：迁移现有策略和部署

**目的：** 在新 schema 上重新建立当前生产事实，不延续旧字符串映射和失效证据。

**Files:**

- Create: `factor_research/scripts/repair/migrate_strategy_specs.py`
- Create: `factor_research/scripts/repair/migrate_deployment.py`
- Create: `factor_research/tests/test_strategy_migration.py`
- Runtime outputs, not committed:
  - `factor_research/reports/governance/strategy_spec_migration.json`
  - `factor_research/reports/governance/deployment_migration.json`

- [ ] **Step 1: 写 dry-run 和幂等测试**

覆盖：

- 未知旧 config 不猜测，标 `manual_review_required`。
- 已知 illiquidity v3.1 生成确定 spec hash。
- 二次运行无变化。
- 旧 evidence 不会被自动复制到新 spec hash。
- 未通过完整 Nine-Gate 的版本不能进入 deployment。

- [ ] **Step 2: 实现 strategy spec 迁移**

迁移分类：

- 可机械映射：生成 spec，状态保持但证据标记需重验。
- 信息不全：降为 candidate/manual review。
- config 与代码不一致：阻断并报告差异。

- [ ] **Step 3: 实现 deployment 迁移**

必须先由用户确认真实生产组合。迁移工具只接受显式参数：

```bash
python3 scripts/repair/migrate_deployment.py \
  --equity illiquidity/v3.1 \
  --defensive gov-bond-etf/v1.0
```

工具不得根据 `LIVE_STRATEGIES` 自动猜生产组合。

- [ ] **Step 4: 完整重验**

迁移后执行：

```bash
cd /Users/kiki/astcok/factor_research
python3 scripts/ci/check_layer_deps.py
python3 scripts/ci/check_registry_evidence.py
python3 scripts/ci/check_holdout_compliance.py
python3 scripts/research/run_nine_gates_all.py \
  --strategy illiquidity \
  --version v3.1 \
  --persist
python3 run_daily.py --no-update
```

验收：

- signal 的 spec/deployment identity 与 registry 一致。
- readiness 无 identity mismatch。
- 旧污染数据证据没有被复用。

- [ ] **Step 5: 原子提交迁移工具**

```bash
git add \
  factor_research/scripts/repair/migrate_strategy_specs.py \
  factor_research/scripts/repair/migrate_deployment.py \
  factor_research/tests/test_strategy_migration.py
git diff --cached --stat
git diff --cached
git commit -m "feat(migration): rebuild strategy and deployment identity

Provide dry-run-first migrations that refuse to guess missing semantics
or reuse evidence across different executable strategy hashes."
```

---

## Task 20：最终系统验收与文档纠错

**目的：** 只有代码、数据、运行态和文档四者一致，整改才算完成。

**Files:**

- Modify: `STATUS.md`
- Modify: `TASKS.md`
- Modify: `DECISIONS.md`
- Modify: `WORKFLOW.md`
- Modify: `LOOP_ENGINEERING.md`
- Modify: `factor_research/docs/ontology_glossary.md`
- Create: `factor_research/reports/governance/system_consistency_acceptance.md`

- [ ] **Step 1: 运行完整自动验收**

```bash
cd /Users/kiki/astcok/factor_research
PYTHONDONTWRITEBYTECODE=1 bash scripts/test_all.sh
```

Expected:

- 分层、registry、holdout、writer、exception、test discovery 守卫全部 PASS。
- 全部 Python 测试通过。
- Web tests、TypeScript、lint 通过。

- [ ] **Step 2: 运行运行态验收**

```bash
INCIDENT_START="$(python3 -c 'import json; print(json.load(open("reports/data/price_unit_rebuild.json"))["start_date"])')"
python3 scripts/repair/audit_price_units.py \
  --start "$INCIDENT_START" \
  --output reports/data/price_unit_acceptance.json
python3 scripts/ops/decay_monitor.py
python3 run_daily.py --no-update
python3 -m scripts.ops.paper_trade
```

必须核对：

- 价量单位报告通过。
- deployment、signal、decay、paper 的 family/version/spec_hash 一致。
- paper blocked fill 会阻断 readiness。
- 未通过完整 Nine-Gate 时正式信号不发布。

- [ ] **Step 3: 人工审查五个真实对象**

逐项对照：

1. Registry 当前在册版本。
2. Deployment 当前激活版本。
3. 最新正式 signal。
4. 最新 paper execution。
5. 最新 decay/data readiness 报告。

五者 identity 必须完全一致。

- [ ] **Step 4: 修正文档中的错误陈述**

必须删除或改正：

- “test_all 覆盖全部测试”的旧说法。
- “DSR 通过等于 Nine-Gate 通过”。
- “硬编码四腿组合是现行 LIVE”。
- “T+1 open”与实际 T+1 close 不一致。
- “Gate7A 已完成真实 purged model selection”的过度表述。
- “holdout 唯一一次”但代码仅 warning 的旧状态。

- [ ] **Step 5: 写最终验收报告**

报告必须包含：

- incident 起止日期和修复数据范围。
- 旧/新 Top25 overlap。
- 旧/新策略指标。
- 新 spec hash 和 deployment ID。
- Nine-Gate 完整裁决。
- holdout identity。
- T+1 语义测试证据。
- 全量测试数量和结果。
- 尚未解决但不阻断生产的风险。

- [ ] **Step 6: 文档原子提交**

当前共享工作树可能已有其他 agent 修改这些文件。提交前逐文件检查，仅在确认没有混入他人改动时执行：

```bash
git add \
  STATUS.md \
  TASKS.md \
  DECISIONS.md \
  WORKFLOW.md \
  LOOP_ENGINEERING.md \
  factor_research/docs/ontology_glossary.md \
  factor_research/reports/governance/system_consistency_acceptance.md
git diff --cached --stat
git diff --cached
git commit -m "docs(governance): record system consistency acceptance

Align status, workflow, ontology, and operating claims with the verified
data contract, deployment identity, admission gate, and execution model."
```

如果上述文档仍有他人未提交改动，停止提交并与对应 agent 协调，不得把别人改动一起 stage。

---

## 最终 Definition of Done

全部条件必须同时成立：

- [ ] 数据湖 canonical 单位为股、元、元/股，不存在板块特例。
- [ ] 最近和历史受影响日期通过 amount 物理量纲审计。
- [ ] 污染证据已标记失效，受影响策略完成重算。
- [ ] 每个可执行策略都有 immutable spec 和稳定 hash。
- [ ] 回测、注册、部署、信号和模拟执行使用同一 spec。
- [ ] 生产由 DeploymentManifest 驱动，不再由硬编码 ACTIVE 驱动。
- [ ] 完整 Nine-Gate、holdout、evidence 和 marginal 在注册前完成。
- [ ] DSR-only 不再能产生治理批准。
- [ ] Holdout 重复消费被机械拒绝。
- [ ] DSR trial 数来自真实实验账本。
- [ ] readiness 对未知、异常、陈旧和版本不匹配全部 fail-closed。
- [ ] decay、data、signal 和 paper 报告包含部署及 spec identity。
- [ ] 回测和模拟盘统一为明确的 T+1 fill 语义。
- [ ] 固定公式稳定性测试不再冒充模型训练 Walk-Forward。
- [ ] 所有控制路径异常可观测，不存在影响裁决的静默 `except/pass`。
- [ ] `test_all.sh` 使用全量测试发现，所有 Python/Web 检查通过。
- [ ] 生产页面默认不展示合成美股数据。
- [ ] `STATUS.md`、`TASKS.md`、`DECISIONS.md` 与实际运行状态一致。
