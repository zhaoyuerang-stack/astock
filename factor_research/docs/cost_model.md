# 交易成本模型 cost_model.md

> 成本口径的 **canonical 细节文档**。规则层(P0)见 [`CLAUDE.md`](../../CLAUDE.md) `R-COST-001`;本文给数字与变更纪律。
> **数值唯一权威 = 代码** `factor_research/core/engine.py::CostModel`（及 `formal_cost_model` / `core.cost_tiers` / `core.cost_impact`）;本文必须与代码一致。

---

## 1. 真实费率拆解(A股,审慎口径)

| 费用 | 比例 | 收取方式 |
|------|------|----------|
| 佣金 | 0.0065%(万 0.65) | 买卖双边 |
| 印花税 | 0.05% | 仅卖出(2023.8 起减半) |
| 过户费 | 0.001%(万 0.1) | 买卖双边 |
| 冲击/滑点 | 见 §5（小盘常数 0.2%；研究层可 ADV 挂钩） | 买卖双边 |
| 融资利率 | **6.5%/年**（代码 `CANONICAL_FINANCING_RATE=0.065`） | 持仓日,仅杠杆超额部分 |

**刚性税费单边**(不含冲击):买 ≈ 0.0075% / 卖 ≈ 0.0575%。  
**小盘正式**(刚性 + 0.2% 冲击 + 审慎垫):买 **0.225%** / 卖 **0.275%** → 往返 ≈ **0.50%**(另加融资)。

> 融资利率以代码 **6.5%** 为准。历史上文档曾写「5%/年」与代码不一致；自 ADR-033 起统一为 6.5%。

---

## 2. 代码固化的默认值(回测/进化实际所用)

`core/engine.py::CostModel` 默认:

| 参数 | 代码默认 | 含义 |
|------|---------|------|
| `buy_cost` | `0.00225`(0.225%) | 买入单边成本 |
| `sell_cost` | `0.00275`(0.275%) | 卖出单边成本 |
| `financing_rate` | `0.065`(6.5%/年) | 融资利率,仅 `leverage>1` 的超额部分按持仓日计 |

融资扣费:`(leverage - 1) * financing_rate / 252`（见 `BacktestEngine`）。

入口:

| 函数 | 用途 |
|------|------|
| `CostModel()` / `formal_cost_model(...)` | 正式地板；低于地板 raise |
| `core.cost_tiers.formal_cost_for_universe(...)` | 按宇宙选正式档（ETF 拒绝） |
| `core.cost_tiers.research_cost_for_universe(...)` | 研究敏感性；**不可入册** |
| `core.cost_impact.*` | ADV 平方根冲击叠加（研究/Gate 6）；**不降低地板** |

---

## 3. P0 纪律(违反则回测作废)

1. 正式回测、进化筛选、入册评估、横向比较 **必须扣真实成本**;禁用乐观值。
2. 小盘策略必须显式考虑冲击/滑点;高换手策略必须做成本敏感性。
3. 杠杆策略必须计融资成本（**6.5%/年** 口径）。
4. **禁止为达标临时下调**滑点/佣金/冲击。
5. 所有报告必须说明成本口径与宇宙档位。

### 3.0 地板强制(audit #8, 2026-07-12)

- **数值地板** = `buy_cost ≥ 0.00225`, `sell_cost ≥ 0.00275`。
- **运行时**:`formal_cost_model` / `formal_cost_for_universe`；phase2/phase3 低于地板 **raise**。
- **静态守卫**:`scripts/ci/check_cost_model_usage.py` 字面量低于地板即失败。
- ETF 正式折扣禁止；ETF 研究档见 §4。

### 3.1 对冲策略不是免成本策略

股票多头腿仍按 `CostModel()` 扣买卖与融资；`hedge_cost_annual` / `switch_friction` 不能替代 long 腿调仓成本。

### 3.2 容量结论的可信边界

Gate 6 / `cost_impact` 使用 ADV、波动率、平方根冲击与 1–5 日拆单近似；**不是订单簿回放**。容量数字 = 研究筛查上限，不得写成已验证可成交规模。

---

## 4. 策略宇宙分层(ADR-033)

| 宇宙 | 正式入册 | 研究敏感性 | 说明 |
|------|----------|------------|------|
| `small_cap` | **必须** `CostModel` 地板 | 同地板 | 默认；小盘/微盘主战场 |
| `large_cap` | **仍须** 地板（不可下调） | 可用更低冲击分解做对照 | 大盘正式证据不因「流动性好」降成本 |
| `etf` | **禁止** 作为正式证据 | `buy=sell=5bp` 等 | 仅 scripts/research / 敏感性 |

代码:

```python
from core.cost_tiers import formal_cost_for_universe, research_cost_for_universe

formal = formal_cost_for_universe("small_cap")   # 或 large_cap
# formal_cost_for_universe("etf")  → raises
research_etf = research_cost_for_universe("etf")  # 不可入册
```

---

## 5. 冲击:常数地板 vs ADV 研究层(ADR-033)

### 5.1 正式路径(常数冲击,已含在 buy/sell)

小盘正式单边已内嵌约 **20bp** 冲击 + 刚性税费 + 审慎垫。  
入册/phase2/3/promote **只认这套地板**，不因 ADV 高就自动降费率。

### 5.2 研究层 ADV 挂钩(`core.cost_impact`)

在 **已扣正式 CostModel** 的净收益上，再叠加:

```text
participation = trade_cny / ADV_20d
single_day    = Y * vol_20d * sqrt(participation)     # Y=1 默认
impact(N)     = single_day/sqrt(N) + (N-1)*alpha_decay  # N=1..5 取 min
portfolio_day = Σ impact_i * |w_i|
```

用途:Gate 6 容量曲线、AUM 压力、研究脚本。  
**禁止**用 ADV 冲击结果反推「正式 buy_cost 可以更低」。

---

## 6. 变更费率时必须同步(四处,缺一即口径漂移)

1. `factor_research/core/engine.py::CostModel` / `CANONICAL_*`(数值权威);
2. 本文 `cost_model.md`;
3. [`DECISIONS.md`](../../DECISIONS.md)(追加 ADR);
4. 受影响的回测报告(重算并标注新口径)。

分层档与 ADV 公式变更:同步 `core/cost_tiers.py`、`core/cost_impact.py` 与本文 §4–§5。
