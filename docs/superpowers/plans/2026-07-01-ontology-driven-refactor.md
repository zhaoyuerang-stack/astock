# Ontology-Driven Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a concept-to-name taxonomy for `factor_research`, then migrate the highest-confusion names (`composer`, `to_signal`, `zscore`, `veto`, `regime/timing/filter`) in small, reversible batches without changing research semantics.

**Architecture:** Treat this as governance plus compatibility-layer migration, not a big-bang rename. New canonical modules/functions are introduced first, old names remain as wrappers during the migration, and tests prove old and new entrypoints produce identical output before callers are switched.

**Tech Stack:** Python 3, pandas, pytest-style script tests under `factor_research/tests`, static AST guard scripts under `factor_research/scripts/ci`, existing `bash factor_research/scripts/test_all.sh`.

---

## Non-Negotiable Constraints

- Do not change strategy formulas, costs, `shift(1)`, rebalance timing, T+1 behavior, universe filters, or registry statuses.
- Do not rewrite historical `strategy_versions.json` transform strings such as `"zscore"` unless a separate registry migration ADR is approved.
- Do not use `git add -A`, `git add .`, or `git commit -a`.
- Do not edit unrelated dirty worktree files. Before each task, run `git status --short` and only stage explicit paths owned by the task.
- Preserve backward imports until all in-repo callers have moved and one full `test_all.sh` has passed.
- Each task below should be one independent commit.

## Target Taxonomy

| Concept | Canonical Names | Old Names Kept Temporarily |
|---|---|---|
| Factor composition | `engine.factor_composer`, `equal_weight_factor`, `ic_weight_factor`, `pca_factor_composite` | `engine.composer`, `equal_weight`, `ic_weight`, `pca_composite` |
| Portfolio composition | `portfolio.portfolio_composer`, `equal_weight_portfolio`, `compose_portfolio_returns` | `portfolio.composer`, `equal_weight`, `compose` |
| Factor to Signal bridge | `engine.signal_factory.factor_to_signal` | `engine.portfolio.to_signal`, `engine.composer.to_signal` |
| Cross-sectional transform | `zscore_cross_section` | registered DSL transform name `"zscore"` |
| Series transform | `zscore_series` | `engine.neutralize.zscore` |
| Policy candidate filter | `policy.candidate_filters.loser_reversal_filter` | `factors.veto.loser_veto_reversal` |
| Illiquidity component | `factors.illiquidity_components.salience_covariance_score` | `factors.veto.salience_covariance_veto` |
| Timing exposure | `small_cap_exposure_signal` | `small_cap_timing` |
| Strategy daily decision | `latest_decision` | `latest_signal` |

## File Map

- Create: `factor_research/docs/naming_taxonomy.md`
  - Canonical taxonomy, migration policy, and examples.
- Modify: `factor_research/docs/ontology_glossary.md`
  - Link the glossary to the taxonomy and mark baseline vs implementation plan.
- Create: `factor_research/engine/factor_composer.py`
  - Canonical factor composition functions.
- Modify: `factor_research/engine/composer.py`
  - Backward-compatible wrappers.
- Create: `factor_research/engine/signal_factory.py`
  - One canonical `factor_to_signal` implementation.
- Modify: `factor_research/engine/portfolio.py`
  - Delegate `to_signal` to `signal_factory`.
- Modify: `factor_research/engine/__init__.py`
  - Export canonical names without breaking old imports.
- Create: `factor_research/portfolio/portfolio_composer.py`
  - Canonical portfolio composition functions.
- Modify: `factor_research/portfolio/composer.py`
  - Backward-compatible wrappers.
- Modify: `factor_research/factors/alpha/transforms.py`
  - Add explicit `zscore_cross_section`; keep registered `"zscore"`.
- Modify: `factor_research/engine/neutralize.py`
  - Add explicit `zscore_series`; keep old `zscore` wrapper.
- Create: `factor_research/policy/__init__.py`
- Create: `factor_research/policy/candidate_filters.py`
  - Canonical policy filters.
- Create: `factor_research/factors/illiquidity_components.py`
  - Canonical illiquidity factor components.
- Modify: `factor_research/factors/veto.py`
  - Backward-compatible wrappers only.
- Modify: `factor_research/factors/small_cap.py`
  - Add `small_cap_exposure_signal`; keep old `small_cap_timing` wrapper.
- Modify: selected callers after wrappers are tested:
  - `factor_research/strategies/small_cap.py`
  - `factor_research/strategies/size_earnings.py`
  - `factor_research/portfolio/regime_gate.py`
  - Any low-risk imports found by `rg`.
- Create or modify tests:
  - `factor_research/tests/test_naming_taxonomy.py`
  - `factor_research/tests/test_factor_composer_taxonomy.py`
  - `factor_research/tests/test_signal_factory.py`
  - `factor_research/tests/test_composer.py`
  - `factor_research/tests/test_factor_normalization_axis.py`
  - `factor_research/tests/test_veto_filter.py`
  - `factor_research/tests/test_timing_taxonomy.py`
- Modify: `factor_research/scripts/ci/check_layer_deps.py` only if `policy.*` needs explicit layer rules.
- Create: `factor_research/scripts/ci/check_naming_taxonomy.py`
  - Guard against new ambiguous modules/functions once compatibility wrappers exist.
- Modify: `factor_research/scripts/test_all.sh`
  - Add the new naming guard after it is stable.

---

### Task 1: Document the Canonical Naming Taxonomy

**Files:**
- Create: `factor_research/docs/naming_taxonomy.md`
- Modify: `factor_research/docs/ontology_glossary.md`
- Test: `factor_research/tests/test_naming_taxonomy.py`

- [ ] **Step 1: Write the failing test**

Create `factor_research/tests/test_naming_taxonomy.py`:

```python
"""Naming taxonomy documentation guard.

Run:
    cd factor_research && python3 tests/test_naming_taxonomy.py
"""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_naming_taxonomy_doc_exists_and_defines_required_concepts():
    doc = ROOT / "docs" / "naming_taxonomy.md"
    assert doc.exists(), "docs/naming_taxonomy.md must define canonical naming rules"
    text = doc.read_text(encoding="utf-8")
    required = [
        "Factor",
        "Signal",
        "Timing/Regime",
        "Strategy",
        "Policy",
        "Portfolio",
        "Engine",
        "zscore_cross_section",
        "zscore_series",
        "factor_to_signal",
        "loser_reversal_filter",
        "salience_covariance_score",
    ]
    missing = [term for term in required if term not in text]
    assert not missing, f"naming taxonomy missing terms: {missing}"


def test_ontology_glossary_links_taxonomy():
    glossary = ROOT / "docs" / "ontology_glossary.md"
    text = glossary.read_text(encoding="utf-8")
    assert "naming_taxonomy.md" in text


if __name__ == "__main__":
    test_naming_taxonomy_doc_exists_and_defines_required_concepts()
    test_ontology_glossary_links_taxonomy()
    print("naming taxonomy doc tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_naming_taxonomy.py
```

Expected: FAIL because `docs/naming_taxonomy.md` does not exist or the glossary does not link it.

- [ ] **Step 3: Create the taxonomy document**

Create `factor_research/docs/naming_taxonomy.md`:

```markdown
# Naming Taxonomy

> Canonical naming rules for ontology-driven refactors. The glossary records current collisions; this file defines target names for new code and staged migrations.

## Concept Layers

| Layer | Meaning | Canonical Naming |
|---|---|---|
| Factor | Single cross-sectional formula or formula component | `*_factor`, `*_component`, `*_score` |
| Signal | Backtest-engine input built from factor values or scheduled weights | `factor_to_signal`, `weights_to_signal` |
| Timing/Regime | Market-state label or exposure series | `*_timing_state`, `*_exposure_signal`, `*_regime_label` |
| Strategy | Executable selection/rebalance behavior | `build_*_target_weights`, `latest_decision` |
| Policy | Hard candidate/position constraint that does not claim standalone alpha | `*_filter`, `*_gate`, `*_constraint` |
| Portfolio | Multi-strategy return or weight composition | `compose_portfolio_*`, `*_portfolio` |
| Engine | Backtest, metrics, and low-level computation | engine-specific descriptive nouns |

## Required Disambiguations

- Use `zscore_cross_section` for row-wise date-by-date stock standardization.
- Use `zscore_series` for one-dimensional Series standardization.
- Use `factor_to_signal` for wrapping a factor panel as `core.engine.Signal`.
- Use `latest_decision` for a strategy's latest tradable decision; keep `latest_signal` only as a compatibility wrapper.
- Use `loser_reversal_filter` for the policy-layer death-bucket exclusion score.
- Use `salience_covariance_score` for the illiquidity/salience factor component.
- Use `small_cap_exposure_signal` for the PureTrend small-cap exposure series.

## Compatibility Policy

1. Introduce canonical names first.
2. Keep old names as wrappers until all production and tested research callers migrate.
3. Tests must prove old and new names are equivalent before callers are switched.
4. Registry strings and historical evidence are not renamed without a separate migration ADR.
5. New code must use canonical names.
```

- [ ] **Step 4: Link the glossary**

In `factor_research/docs/ontology_glossary.md`, add this paragraph after the opening scope statement:

```markdown
> **执行规则**：目标命名 taxonomy 见 [`naming_taxonomy.md`](naming_taxonomy.md)。本文保留当前冲突盘点；新代码和分批迁移以 taxonomy 为准。
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
cd factor_research && python3 tests/test_naming_taxonomy.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add factor_research/docs/naming_taxonomy.md factor_research/docs/ontology_glossary.md factor_research/tests/test_naming_taxonomy.py
git diff --cached --stat
git diff --cached
git commit -m "docs(factor-research): define ontology naming taxonomy"
```

---

### Task 2: Split Factor Composer From Portfolio Composer With Wrappers

**Files:**
- Create: `factor_research/engine/factor_composer.py`
- Modify: `factor_research/engine/composer.py`
- Create: `factor_research/portfolio/portfolio_composer.py`
- Modify: `factor_research/portfolio/composer.py`
- Modify: `factor_research/engine/__init__.py`
- Test: `factor_research/tests/test_factor_composer_taxonomy.py`
- Test: `factor_research/tests/test_composer.py`

- [ ] **Step 1: Write failing factor composer tests**

Create `factor_research/tests/test_factor_composer_taxonomy.py`:

```python
"""Factor composer taxonomy tests.

Run:
    cd factor_research && python3 tests/test_factor_composer_taxonomy.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _factors():
    idx = pd.date_range("2024-01-01", periods=3)
    return {
        "a": pd.DataFrame([[1, 2], [3, 4], [5, 6]], index=idx, columns=["x", "y"], dtype=float),
        "b": pd.DataFrame([[3, 4], [5, 6], [7, 8]], index=idx, columns=["x", "y"], dtype=float),
    }


def test_factor_composer_canonical_and_legacy_equal_weight_match():
    from engine.factor_composer import equal_weight_factor
    from engine.composer import equal_weight

    expected = pd.DataFrame([[2, 3], [4, 5], [6, 7]], index=list(_factors().values())[0].index, columns=["x", "y"], dtype=float)
    pd.testing.assert_frame_equal(equal_weight_factor(_factors()), expected)
    pd.testing.assert_frame_equal(equal_weight(_factors()), expected)


def test_portfolio_composer_canonical_and_legacy_compose_match():
    from portfolio.portfolio_composer import compose_portfolio_returns
    from portfolio.composer import compose

    idx = pd.date_range("2024-01-01", periods=3)
    returns = {
        "a": pd.Series([0.01, 0.02, 0.03], index=idx),
        "b": pd.Series([0.03, 0.02, 0.01], index=idx),
    }
    new_ret, new_w = compose_portfolio_returns(returns, method="equal_weight")
    old_ret, old_w = compose(returns, method="equal_weight")
    pd.testing.assert_series_equal(new_ret, old_ret)
    pd.testing.assert_frame_equal(new_w, old_w)


if __name__ == "__main__":
    test_factor_composer_canonical_and_legacy_equal_weight_match()
    test_portfolio_composer_canonical_and_legacy_compose_match()
    print("factor/portfolio composer taxonomy tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_factor_composer_taxonomy.py
```

Expected: FAIL because `engine.factor_composer` and `portfolio.portfolio_composer` do not exist.

- [ ] **Step 3: Create `engine/factor_composer.py`**

Move the implementation from `engine/composer.py` into `factor_research/engine/factor_composer.py`, using canonical function names:

```python
"""Canonical factor composition utilities."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA


def equal_weight_factor(factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
    aligned = list(factors.values())
    return sum(aligned) / len(aligned)


def ic_weight_factor(
    factors: dict[str, pd.DataFrame],
    forward_ret: pd.DataFrame,
    ic_window: int = 12,
) -> pd.DataFrame:
    from engine.factor_analysis import calc_ic

    ic_series = {name: calc_ic(f, forward_ret) for name, f in factors.items()}
    dates = sorted(set.intersection(*[set(f.index) for f in factors.values()]))
    result = {}

    for dt in dates:
        weights = {}
        for name, ic in ic_series.items():
            past_ic = ic[ic.index < dt].tail(ic_window)
            weights[name] = 0.0 if len(past_ic) < 3 else past_ic.mean()
        total_abs = sum(abs(w) for w in weights.values())
        if total_abs < 1e-6:
            continue
        norm_w = {n: w / total_abs for n, w in weights.items()}
        row = sum(factors[n].loc[dt] * w for n, w in norm_w.items() if dt in factors[n].index)
        result[dt] = row

    return pd.DataFrame(result).T


def pca_factor_composite(
    factors: dict[str, pd.DataFrame],
    n_components: int = 1,
) -> pd.DataFrame:
    names = list(factors.keys())
    dates = sorted(set.intersection(*[set(f.index) for f in factors.values()]))
    result = {}

    for dt in dates:
        cols = {name: factors[name].loc[dt] for name in names if dt in factors[name].index}
        df = pd.DataFrame(cols).dropna()
        if len(df) < 50 or df.shape[1] < 2:
            continue
        pca = PCA(n_components=n_components)
        pc = pca.fit_transform(df.values)[:, 0]
        if np.corrcoef(df.iloc[:, 0].values, pc)[0, 1] < 0:
            pc = -pc
        result[dt] = pd.Series(pc, index=df.index)

    return pd.DataFrame(result).T


def factor_corr_matrix(
    factors: dict[str, pd.DataFrame],
    sample_dates: int = 60,
) -> pd.DataFrame:
    names = list(factors.keys())
    dates = sorted(set.intersection(*[set(f.index) for f in factors.values()]))[-sample_dates:]
    corr_accum = pd.DataFrame(0.0, index=names, columns=names)
    count = 0

    for dt in dates:
        cols = {name: factors[name].loc[dt] for name in names if dt in factors[name].index}
        df = pd.DataFrame(cols).dropna()
        if len(df) < 30:
            continue
        corr_accum += df.corr(method="spearman")
        count += 1

    return (corr_accum / max(count, 1)).round(3)
```

- [ ] **Step 4: Convert `engine/composer.py` to wrappers**

Replace `factor_research/engine/composer.py` with:

```python
"""Backward-compatible factor composer wrappers.

New code should import from ``engine.factor_composer`` and
``engine.signal_factory``.
"""
from __future__ import annotations

import pandas as pd

from engine.factor_composer import (
    equal_weight_factor,
    factor_corr_matrix,
    ic_weight_factor,
    pca_factor_composite,
)
from engine.signal_factory import factor_to_signal


def equal_weight(factors: dict[str, pd.DataFrame]) -> pd.DataFrame:
    return equal_weight_factor(factors)


def ic_weight(
    factors: dict[str, pd.DataFrame],
    forward_ret: pd.DataFrame,
    ic_window: int = 12,
) -> pd.DataFrame:
    return ic_weight_factor(factors, forward_ret, ic_window)


def pca_composite(
    factors: dict[str, pd.DataFrame],
    n_components: int = 1,
) -> pd.DataFrame:
    return pca_factor_composite(factors, n_components)


def to_signal(
    factor: pd.DataFrame,
    top_n: int = 25,
    direction: int = 1,
    rebalance_freq: str = "20D",
    timing: pd.Series | None = None,
    family: str = "",
    version: str = "",
):
    return factor_to_signal(
        factor,
        top_n=top_n,
        direction=direction,
        rebalance_freq=rebalance_freq,
        timing=timing,
        family=family,
        version=version,
    )
```

- [ ] **Step 5: Create `engine/signal_factory.py` because composer wrappers need it**

Create `factor_research/engine/signal_factory.py`:

```python
"""Canonical builders for core.engine.Signal objects."""
from __future__ import annotations

import pandas as pd


def factor_to_signal(
    factor: pd.DataFrame,
    *,
    top_n: int = 25,
    direction: int = 1,
    rebalance_freq: str = "20D",
    timing: pd.Series | None = None,
    family: str = "",
    version: str = "",
):
    """Wrap a factor panel into ``core.engine.Signal``."""
    from core.engine import Signal

    return Signal(
        factor=factor,
        top_n=top_n,
        direction=direction,
        rebalance_freq=rebalance_freq,
        timing=timing,
        family=family,
        version=version,
    )
```

- [ ] **Step 6: Create `portfolio/portfolio_composer.py`**

Copy behavior from `portfolio/composer.py` with canonical names:

```python
"""Canonical portfolio composition algorithms."""
from __future__ import annotations

import numpy as np
import pandas as pd


def equal_weight_portfolio(returns: pd.DataFrame) -> pd.Series:
    n = returns.shape[1]
    weights = np.full(n, 1.0 / n)
    return (returns * weights).sum(axis=1)


def risk_parity_portfolio(returns: pd.DataFrame, lookback: int = 252) -> pd.Series:
    rolling_vol = returns.rolling(lookback, min_periods=63).std()
    inv_vol = 1.0 / rolling_vol.replace(0, np.nan)
    weights = inv_vol.div(inv_vol.sum(axis=1), axis=0)
    weights = weights.shift(1)
    return (returns * weights).sum(axis=1)


def capped_portfolio_weight(returns: pd.DataFrame, defensive: set, cap: float = 0.30) -> tuple[pd.Series, pd.Series]:
    cols = list(returns.columns)
    d = [c for c in cols if c in defensive]
    g = [c for c in cols if c not in defensive]
    w = pd.Series(0.0, index=cols)
    if d and g:
        w[d] = cap / len(d)
        w[g] = (1.0 - cap) / len(g)
    else:
        w[:] = 1.0 / len(cols)
    return (returns * w).sum(axis=1), w


def regime_adaptive_portfolio(
    returns: pd.DataFrame,
    vol: pd.DataFrame,
    regime_signal: pd.Series,
) -> pd.Series:
    regime = regime_signal.reindex(returns.index).fillna(0)
    n = returns.shape[1]
    bull_w = pd.DataFrame(1.0 / n, index=returns.index, columns=returns.columns)
    vol_mean = vol.rolling(252).mean().iloc[-1]
    lowest_vol = vol_mean.idxmin()
    bear_w = pd.DataFrame(1.0 / n, index=returns.index, columns=returns.columns)
    bear_w[lowest_vol] = min(0.5, 2.0 / n)
    weights = bull_w.mul(regime, axis=0) + bear_w.mul(1 - regime, axis=0)
    weights = weights.div(weights.sum(axis=1), axis=0).fillna(1.0 / n)
    weights = weights.shift(1).fillna(1.0 / n)
    return (returns * weights).sum(axis=1)


def compose_portfolio_returns(
    returns: dict[str, pd.Series],
    method: str = "equal_weight",
    regime_signal: pd.Series | None = None,
    defensive: set | None = None,
    cap: float = 0.30,
) -> tuple[pd.Series, pd.DataFrame]:
    df = pd.DataFrame(returns).dropna()
    if df.shape[1] < 2:
        return df.iloc[:, 0], pd.DataFrame({"weight": [1.0]})

    static_w = None
    if method == "risk_parity":
        port_ret = risk_parity_portfolio(df)
    elif method == "regime_adaptive":
        if regime_signal is None:
            raise ValueError("regime_signal required for regime_adaptive")
        vol = df.rolling(252).std()
        port_ret = regime_adaptive_portfolio(df, vol, regime_signal)
    elif method == "capped":
        port_ret, static_w = capped_portfolio_weight(df, defensive or set(), cap)
    else:
        port_ret = equal_weight_portfolio(df)

    if static_w is not None:
        weights = pd.DataFrame([static_w.values], columns=df.columns, index=["weight"])
    else:
        weights = pd.DataFrame(1.0 / df.shape[1], index=df.index, columns=df.columns)
    return port_ret.dropna(), weights


def portfolio_metrics(returns: pd.Series) -> dict:
    r = returns.dropna()
    if len(r) < 50:
        return {"annual": 0, "maxdd": 0, "sharpe": 0, "calmar": 0}
    ann = float(r.mean() * 252)
    vol = float(r.std() * np.sqrt(252))
    sharpe = ann / vol if vol > 0 else 0.0
    cum = (1 + r).cumprod()
    maxdd = float((cum / cum.cummax() - 1).min())
    calmar = ann / abs(maxdd) if maxdd < 0 else 0.0
    return {"annual": ann, "vol": vol, "maxdd": maxdd, "sharpe": sharpe, "calmar": calmar, "n_days": len(r)}
```

- [ ] **Step 7: Convert `portfolio/composer.py` to wrappers**

Replace `factor_research/portfolio/composer.py` with:

```python
"""Backward-compatible portfolio composer wrappers.

New code should import from ``portfolio.portfolio_composer``.
"""
from __future__ import annotations

import pandas as pd

from portfolio.portfolio_composer import (
    capped_portfolio_weight,
    compose_portfolio_returns,
    equal_weight_portfolio,
    portfolio_metrics,
    regime_adaptive_portfolio,
    risk_parity_portfolio,
)


def equal_weight(returns: pd.DataFrame) -> pd.Series:
    return equal_weight_portfolio(returns)


def risk_parity(returns: pd.DataFrame, lookback: int = 252) -> pd.Series:
    return risk_parity_portfolio(returns, lookback)


def capped_weight(returns: pd.DataFrame, defensive: set, cap: float = 0.30):
    return capped_portfolio_weight(returns, defensive, cap)


def regime_adaptive(
    returns: pd.DataFrame,
    vol: pd.DataFrame,
    regime_signal: pd.Series,
) -> pd.Series:
    return regime_adaptive_portfolio(returns, vol, regime_signal)


def compose(
    returns: dict[str, pd.Series],
    method: str = "equal_weight",
    regime_signal: pd.Series | None = None,
    defensive: set | None = None,
    cap: float = 0.30,
) -> tuple[pd.Series, pd.DataFrame]:
    return compose_portfolio_returns(returns, method, regime_signal, defensive, cap)


def metrics(returns: pd.Series) -> dict:
    return portfolio_metrics(returns)
```

- [ ] **Step 8: Update `engine/__init__.py` exports**

Ensure `factor_research/engine/__init__.py` contains both legacy and canonical exports:

```python
"""Engine utility exports."""
from engine.factor_analysis import calc_ic, ic_summary, stratify_return  # noqa: F401
from engine.factor_composer import equal_weight_factor, ic_weight_factor, pca_factor_composite  # noqa: F401
from engine.composer import equal_weight, ic_weight, pca_composite  # noqa: F401
from engine.portfolio import performance_metrics, to_signal  # noqa: F401
from engine.signal_factory import factor_to_signal  # noqa: F401
```

- [ ] **Step 9: Run targeted tests**

Run:

```bash
cd factor_research && python3 tests/test_factor_composer_taxonomy.py && python3 tests/test_composer.py
```

Expected: PASS.

- [ ] **Step 10: Run layer guard**

Run:

```bash
cd factor_research && python3 scripts/ci/check_layer_deps.py
```

Expected: PASS. If it fails because of a newly introduced forbidden import, fix the module placement rather than adding an exception.

- [ ] **Step 11: Commit**

```bash
git add factor_research/engine/factor_composer.py factor_research/engine/composer.py factor_research/engine/signal_factory.py factor_research/engine/__init__.py factor_research/portfolio/portfolio_composer.py factor_research/portfolio/composer.py factor_research/tests/test_factor_composer_taxonomy.py factor_research/tests/test_composer.py
git diff --cached --stat
git diff --cached
git commit -m "refactor(engine): split factor and portfolio composers"
```

---

### Task 3: Canonicalize Signal Factory Entrypoints

**Files:**
- Modify: `factor_research/engine/portfolio.py`
- Test: `factor_research/tests/test_signal_factory.py`

- [ ] **Step 1: Write failing signal factory tests**

Create `factor_research/tests/test_signal_factory.py`:

```python
"""Signal factory compatibility tests.

Run:
    cd factor_research && python3 tests/test_signal_factory.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _factor():
    return pd.DataFrame(
        [[1.0, 2.0, 3.0], [3.0, 2.0, 1.0]],
        index=pd.date_range("2024-01-01", periods=2),
        columns=["a", "b", "c"],
    )


def test_factor_to_signal_sets_core_fields():
    from engine.signal_factory import factor_to_signal

    sig = factor_to_signal(_factor(), top_n=2, direction=-1, rebalance_freq="20D", family="fam", version="v1")
    assert sig.factor.equals(_factor())
    assert sig.top_n == 2
    assert sig.direction == -1
    assert sig.rebalance_freq == "20D"
    assert sig.family == "fam"
    assert sig.version == "v1"


def test_legacy_engine_portfolio_to_signal_delegates_to_same_fields():
    from engine.portfolio import to_signal

    sig = to_signal(_factor(), n=2, direction=-1, rebalance_freq="20D", family="fam", version="v1")
    assert sig.factor.equals(_factor())
    assert sig.top_n == 2
    assert sig.direction == -1
    assert sig.rebalance_freq == "20D"
    assert sig.family == "fam"
    assert sig.version == "v1"


if __name__ == "__main__":
    test_factor_to_signal_sets_core_fields()
    test_legacy_engine_portfolio_to_signal_delegates_to_same_fields()
    print("signal factory tests passed")
```

- [ ] **Step 2: Run test**

Run:

```bash
cd factor_research && python3 tests/test_signal_factory.py
```

Expected before Task 2 completion: FAIL because `engine.signal_factory` is missing. Expected after Task 2: the first test passes and legacy delegation may still need cleanup.

- [ ] **Step 3: Delegate `engine/portfolio.py::to_signal`**

Modify only the `to_signal` function in `factor_research/engine/portfolio.py`:

```python
def to_signal(factor: pd.DataFrame, n: int = 100, direction: int = 1,
              rebalance_freq: str = "W", family: str = "", version: str = ""):
    """Backward-compatible wrapper for ``engine.signal_factory.factor_to_signal``."""
    from engine.signal_factory import factor_to_signal

    return factor_to_signal(
        factor,
        top_n=n,
        direction=direction,
        rebalance_freq=rebalance_freq,
        family=family,
        version=version,
    )
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
cd factor_research && python3 tests/test_signal_factory.py && python3 tests/test_factor_composer_taxonomy.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add factor_research/engine/portfolio.py factor_research/tests/test_signal_factory.py
git diff --cached --stat
git diff --cached
git commit -m "refactor(engine): add canonical signal factory"
```

---

### Task 4: Disambiguate Cross-Sectional vs Series Z-Score

**Files:**
- Modify: `factor_research/factors/alpha/transforms.py`
- Modify: `factor_research/engine/neutralize.py`
- Modify: `factor_research/tests/test_factor_normalization_axis.py`

- [ ] **Step 1: Extend the axis test first**

In `factor_research/tests/test_factor_normalization_axis.py`, update imports:

```python
from factors.alpha.transforms import zscore, zscore_cross_section, mad_clip, rank_transform
from engine.neutralize import zscore_series
```

Add tests:

```python
def test_zscore_cross_section_alias_is_cross_sectional():
    out = zscore_cross_section(_DF)
    assert _rows_centered(out), "zscore_cross_section 不是逐行(横截面)归一化"
    assert not _cols_centered(out)
    pd.testing.assert_frame_equal(out, zscore(_DF))


def test_zscore_series_is_one_dimensional():
    s = pd.Series([1.0, 2.0, 3.0, 4.0])
    out = zscore_series(s)
    assert abs(float(out.mean())) < 1e-10
    assert abs(float(out.std()) - 1.0) < 1e-8
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_factor_normalization_axis.py
```

Expected: FAIL because `zscore_cross_section` and `zscore_series` are missing.

- [ ] **Step 3: Add `zscore_cross_section` without changing DSL semantics**

Modify `factor_research/factors/alpha/transforms.py`:

```python
def zscore_cross_section(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional z-score (row-wise, date by date)."""
    return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1) + 1e-8, axis=0)


@register_transform("zscore")
def zscore(df: pd.DataFrame) -> pd.DataFrame:
    """Backward-compatible DSL name for row-wise cross-sectional z-score."""
    return zscore_cross_section(df)
```

Keep the transform registry key `"zscore"` unchanged because registry configs already use it.

- [ ] **Step 4: Add `zscore_series` wrapper**

Modify `factor_research/engine/neutralize.py`:

```python
def zscore_series(s: pd.Series) -> pd.Series:
    """One-dimensional z-score for a single cross-section or generic Series."""
    return (s - s.mean()) / (s.std() + 1e-10)


def zscore(s: pd.Series) -> pd.Series:
    """Backward-compatible wrapper for ``zscore_series``."""
    return zscore_series(s)
```

- [ ] **Step 5: Run targeted tests**

Run:

```bash
cd factor_research && python3 tests/test_factor_normalization_axis.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add factor_research/factors/alpha/transforms.py factor_research/engine/neutralize.py factor_research/tests/test_factor_normalization_axis.py
git diff --cached --stat
git diff --cached
git commit -m "refactor(factors): disambiguate zscore semantics"
```

---

### Task 5: Split Veto Policy Filters From Illiquidity Components

**Files:**
- Create: `factor_research/policy/__init__.py`
- Create: `factor_research/policy/candidate_filters.py`
- Create: `factor_research/factors/illiquidity_components.py`
- Modify: `factor_research/factors/veto.py`
- Modify: `factor_research/tests/test_veto_filter.py`
- Possibly modify: `factor_research/scripts/ci/check_layer_deps.py`

- [ ] **Step 1: Extend veto tests first**

In `factor_research/tests/test_veto_filter.py`, add imports:

```python
from policy.candidate_filters import loser_reversal_filter
from factors.illiquidity_components import salience_covariance_score
from factors.veto import salience_covariance_veto
```

Add tests:

```python
def test_loser_reversal_filter_matches_legacy_veto_score():
    dates = pd.date_range("2024-01-01", periods=80, freq="B")
    close = pd.DataFrame(
        {
            "DEATH": [10.0 - i * 0.01 for i in range(80)],
            "SAFE": [10.0 + i * 0.04 for i in range(80)],
            "MID": [10.0 + i * 0.01 for i in range(80)],
        },
        index=dates,
    )
    pd.testing.assert_frame_equal(
        loser_reversal_filter(close, lookback=20, vol_window=20),
        loser_veto_reversal(close, lookback=20, vol_window=20),
    )


def test_salience_covariance_score_matches_legacy_veto_component():
    dates = pd.date_range("2024-01-01", periods=60, freq="B")
    close = pd.DataFrame(
        {
            "A": [10.0 + i * 0.02 for i in range(60)],
            "B": [12.0 - i * 0.01 for i in range(60)],
            "C": [8.0 + i * 0.03 for i in range(60)],
        },
        index=dates,
    )
    pd.testing.assert_frame_equal(
        salience_covariance_score(close),
        salience_covariance_veto(close),
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_veto_filter.py
```

Expected: FAIL because `policy.candidate_filters` and `factors.illiquidity_components` do not exist.

- [ ] **Step 3: Create policy package**

Create `factor_research/policy/__init__.py`:

```python
"""Policy-layer filters and constraints."""
```

Create `factor_research/policy/candidate_filters.py`:

```python
"""Candidate-pool policy filters.

Policy filters constrain a host strategy. They are not standalone alpha factors.
"""
from __future__ import annotations

import pandas as pd


def _row_pct_rank(df: pd.DataFrame) -> pd.DataFrame:
    return df.rank(axis=1, pct=True)


def loser_reversal_filter(
    close: pd.DataFrame,
    *,
    lookback: int = 20,
    vol_window: int = 20,
) -> pd.DataFrame:
    """Higher is safer; low scores are death-bucket exclusion candidates."""
    momentum = close.pct_change(lookback, fill_method=None)
    volatility = close.pct_change(fill_method=None).rolling(vol_window).std()
    return 0.75 * _row_pct_rank(momentum) + 0.25 * _row_pct_rank(volatility)
```

- [ ] **Step 4: Create illiquidity component module**

Create `factor_research/factors/illiquidity_components.py`:

```python
"""Illiquidity and salience factor components."""
from __future__ import annotations

import pandas as pd


def salience_covariance_score(
    close: pd.DataFrame,
    *,
    W: int = 20,
    theta: float = 0.1,
    delta: float = 0.7,
) -> pd.DataFrame:
    """Faded Salience Covariance score; higher is safer."""
    returns = close.pct_change(fill_method=None)
    market_returns = returns.mean(axis=1)

    r_diff = returns.sub(market_returns, axis=0).abs()
    r_sum = returns.abs().add(market_returns.abs(), axis=0) + theta
    salience = r_diff / r_sum

    ranks = {}
    valid_count = pd.DataFrame(0, index=salience.index, columns=salience.columns)
    for j in range(W):
        valid_count += salience.shift(j).notna().astype(int)

    for s in range(W):
        better_count = pd.DataFrame(0, index=salience.index, columns=salience.columns)
        for j in range(W):
            if j == s:
                continue
            better_count += (salience.shift(j) > salience.shift(s)).astype(int)
        ranks[s] = (better_count + 1).where(salience.shift(s).notna())

    denom = delta * (1 - delta ** valid_count) / (1 - delta)
    est_return = pd.DataFrame(0.0, index=returns.index, columns=returns.columns)
    for s in range(W):
        weight_s = (delta ** ranks[s]) / denom
        r_lag = returns.shift(s)
        est_return += weight_s * r_lag.fillna(0.0)

    avg_return = returns.rolling(W).mean()
    st_cov = est_return - avg_return
    return -st_cov
```

- [ ] **Step 5: Convert `factors/veto.py` to compatibility wrappers**

Replace `factor_research/factors/veto.py` with:

```python
"""Backward-compatible veto names.

New policy filters belong in ``policy.candidate_filters``.
New illiquidity components belong in ``factors.illiquidity_components``.
"""
from __future__ import annotations

import pandas as pd

from factors.illiquidity_components import salience_covariance_score
from policy.candidate_filters import loser_reversal_filter


def loser_veto_reversal(
    close: pd.DataFrame,
    *,
    lookback: int = 20,
    vol_window: int = 20,
) -> pd.DataFrame:
    return loser_reversal_filter(close, lookback=lookback, vol_window=vol_window)


def salience_covariance_veto(
    close: pd.DataFrame,
    *,
    W: int = 20,
    theta: float = 0.1,
    delta: float = 0.7,
) -> pd.DataFrame:
    return salience_covariance_score(close, W=W, theta=theta, delta=delta)
```

- [ ] **Step 6: Update layer guard only if needed**

Run:

```bash
cd factor_research && python3 scripts/ci/check_layer_deps.py
```

If it fails because `policy.*` is not classified, add this edge to `FORBIDDEN_EDGES` in `factor_research/scripts/ci/check_layer_deps.py`:

```python
("policy.", ["factory.", "strategies.", "scripts.research.", "workflow.", "knowledge.", "api.", "services."]),
```

Then run the guard again.

- [ ] **Step 7: Run targeted tests**

Run:

```bash
cd factor_research && python3 tests/test_veto_filter.py && python3 scripts/ci/check_layer_deps.py
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add factor_research/policy/__init__.py factor_research/policy/candidate_filters.py factor_research/factors/illiquidity_components.py factor_research/factors/veto.py factor_research/tests/test_veto_filter.py factor_research/scripts/ci/check_layer_deps.py
git diff --cached --stat
git diff --cached
git commit -m "refactor(policy): split veto filters from factor components"
```

If `check_layer_deps.py` was not modified, omit it from `git add`.

---

### Task 6: Add Explicit Small-Cap Timing Name Without Migrating All Callers

**Files:**
- Modify: `factor_research/factors/small_cap.py`
- Create: `factor_research/tests/test_timing_taxonomy.py`

- [ ] **Step 1: Write timing compatibility test**

Create `factor_research/tests/test_timing_taxonomy.py`:

```python
"""Timing taxonomy compatibility tests.

Run:
    cd factor_research && python3 tests/test_timing_taxonomy.py
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from factors.small_cap import small_cap_exposure_signal, small_cap_timing


def _panels():
    dates = pd.date_range("2024-01-01", periods=80, freq="B")
    close = pd.DataFrame(
        {
            "A": [10.0 + i * 0.01 for i in range(80)],
            "B": [9.0 + i * 0.02 for i in range(80)],
            "C": [8.0 - i * 0.005 for i in range(80)],
        },
        index=dates,
    )
    amount = pd.DataFrame(
        {
            "A": [100.0] * 80,
            "B": [200.0] * 80,
            "C": [300.0] * 80,
        },
        index=dates,
    )
    return close, amount


def test_small_cap_exposure_signal_matches_legacy_small_cap_timing():
    close, amount = _panels()
    new = small_cap_exposure_signal(close, amount, ma_window=16)
    old = small_cap_timing(close, amount, ma_window=16)
    assert len(new) == 3
    for a, b in zip(new, old):
        pd.testing.assert_series_equal(a, b)


if __name__ == "__main__":
    test_small_cap_exposure_signal_matches_legacy_small_cap_timing()
    print("timing taxonomy tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_timing_taxonomy.py
```

Expected: FAIL because `small_cap_exposure_signal` does not exist.

- [ ] **Step 3: Add canonical timing function**

Modify `factor_research/factors/small_cap.py`:

```python
def small_cap_exposure_signal(close, amount, ma_window=16):
    """Small-cap exposure signal: long when small-cap NAV is above its moving average."""
    ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    small_mask = amount.rolling(20).mean().rank(axis=1, pct=True) < 0.5
    small_idx = (ret * small_mask).sum(axis=1) / small_mask.sum(axis=1)
    small_nav = (1 + small_idx.fillna(0)).cumprod()
    timing = (small_nav > small_nav.rolling(ma_window).mean()).shift(1, fill_value=False).astype(bool)
    dist = small_nav / small_nav.rolling(ma_window).mean() - 1
    return timing, small_nav, dist


def small_cap_timing(close, amount, ma_window=16):
    """Backward-compatible wrapper for ``small_cap_exposure_signal``."""
    return small_cap_exposure_signal(close, amount, ma_window)
```

- [ ] **Step 4: Run test**

Run:

```bash
cd factor_research && python3 tests/test_timing_taxonomy.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add factor_research/factors/small_cap.py factor_research/tests/test_timing_taxonomy.py
git diff --cached --stat
git diff --cached
git commit -m "refactor(factors): add explicit small-cap exposure signal"
```

---

### Task 7: Migrate Low-Risk Callers to Canonical Names

**Files:**
- Modify low-risk imports only after wrappers pass:
  - `factor_research/portfolio/regime_gate.py`
  - `factor_research/strategies/small_cap.py`
  - `factor_research/strategies/size_earnings.py`
  - Small targeted tests as needed.

- [ ] **Step 1: List callers and classify**

Run:

```bash
cd factor_research
rg -n "from portfolio\\.composer|from engine\\.composer|from factors\\.veto|small_cap_timing|\\bzscore\\b|to_signal" . --glob '*.py' --glob '!**/__pycache__/**'
```

Expected: A call list. Mark each caller as:

- production or strategy path: migrate only with targeted test.
- research script: leave for later unless it is actively tested.
- scratch/archive: do not touch in this phase.

- [ ] **Step 2: Migrate `portfolio/regime_gate.py` timing import**

Change:

```python
from factors.small_cap import small_cap_timing

timing, _, _ = small_cap_timing(close, amount, ma)
```

To:

```python
from factors.small_cap import small_cap_exposure_signal

timing, _, _ = small_cap_exposure_signal(close, amount, ma)
```

- [ ] **Step 3: Migrate `strategies/small_cap.py` timing import**

Change:

```python
from factors.small_cap import small_cap_factor, small_cap_timing
```

To:

```python
from factors.small_cap import small_cap_exposure_signal, small_cap_factor
```

Change:

```python
timing, small_nav, timing_dist = small_cap_timing(close, amount, config.timing_ma)
```

To:

```python
timing, small_nav, timing_dist = small_cap_exposure_signal(close, amount, config.timing_ma)
```

- [ ] **Step 4: Migrate `strategies/size_earnings.py` timing import**

Change its import and call in the same way as `strategies/small_cap.py`.

- [ ] **Step 5: Run targeted tests**

Run:

```bash
cd factor_research && python3 tests/test_timing_taxonomy.py && python3 tests/test_regime_gate.py && python3 tests/test_veto_filter.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add factor_research/portfolio/regime_gate.py factor_research/strategies/small_cap.py factor_research/strategies/size_earnings.py
git diff --cached --stat
git diff --cached
git commit -m "refactor(strategies): use canonical timing names"
```

---

### Task 8: Add Naming Taxonomy Guard

**Files:**
- Create: `factor_research/scripts/ci/check_naming_taxonomy.py`
- Create: `factor_research/tests/test_naming_taxonomy_guard.py`
- Modify: `factor_research/scripts/test_all.sh`

- [ ] **Step 1: Write guard test**

Create `factor_research/tests/test_naming_taxonomy_guard.py`:

```python
"""Naming taxonomy guard tests.

Run:
    cd factor_research && python3 tests/test_naming_taxonomy_guard.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_naming_taxonomy_guard_passes_current_tree():
    proc = subprocess.run(
        [sys.executable, "scripts/ci/check_naming_taxonomy.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


if __name__ == "__main__":
    test_naming_taxonomy_guard_passes_current_tree()
    print("naming taxonomy guard tests passed")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd factor_research && python3 tests/test_naming_taxonomy_guard.py
```

Expected: FAIL because the guard script is missing.

- [ ] **Step 3: Create the guard script**

Create `factor_research/scripts/ci/check_naming_taxonomy.py`:

```python
"""Guard against new ambiguous ontology names.

This guard is intentionally conservative: it allows known compatibility wrappers
but blocks new modules with ambiguous names that already caused confusion.
"""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

ALLOWED_AMBIGUOUS_FILES = {
    "engine/composer.py",
    "portfolio/composer.py",
    "factors/veto.py",
}

FORBIDDEN_NEW_BASENAMES = {
    "composer.py": "Use factor_composer.py or portfolio_composer.py.",
    "veto.py": "Use policy/candidate_filters.py or factors/illiquidity_components.py.",
    "filter.py": "Use a domain-specific name such as candidate_filters.py.",
}


def main() -> int:
    failures = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if any(part in {"__pycache__", ".pytest_cache", ".ruff_cache", "scratch"} for part in path.parts):
            continue
        reason = FORBIDDEN_NEW_BASENAMES.get(path.name)
        if reason and rel not in ALLOWED_AMBIGUOUS_FILES:
            failures.append(f"{rel}: {reason}")

    if failures:
        print("Naming taxonomy guard failed:")
        for item in failures:
            print(f"  - {item}")
        return 1

    print("Naming taxonomy guard passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run guard and test**

Run:

```bash
cd factor_research && python3 scripts/ci/check_naming_taxonomy.py && python3 tests/test_naming_taxonomy_guard.py
```

Expected: PASS.

- [ ] **Step 5: Add guard to `scripts/test_all.sh`**

Insert near the other CI guards:

```bash
echo "== Naming taxonomy guard =="
python3 scripts/ci/check_naming_taxonomy.py
```

- [ ] **Step 6: Run guard stack**

Run:

```bash
cd factor_research && python3 scripts/ci/check_naming_taxonomy.py && python3 scripts/ci/check_layer_deps.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add factor_research/scripts/ci/check_naming_taxonomy.py factor_research/tests/test_naming_taxonomy_guard.py factor_research/scripts/test_all.sh
git diff --cached --stat
git diff --cached
git commit -m "test(ci): guard ontology naming taxonomy"
```

---

### Task 9: Full Verification and Migration Report

**Files:**
- Create: `factor_research/docs/ontology_refactor_migration_report.md`

- [ ] **Step 1: Run full backend checks**

Run:

```bash
cd factor_research && bash scripts/test_all.sh
```

Expected: PASS. If this fails because unrelated dirty worktree changes are present, capture the exact failing command and rerun only the targeted tests from Tasks 1-8 to isolate whether this refactor caused the failure.

- [ ] **Step 2: Check remaining ambiguous references**

Run:

```bash
cd factor_research
rg -n "from portfolio\\.composer|from engine\\.composer|from factors\\.veto|small_cap_timing|latest_signal|\\bzscore\\b|\\bto_signal\\b" . --glob '*.py' --glob '!**/__pycache__/**' --glob '!scratch/**'
```

Expected: Remaining references are either compatibility wrappers, historical research scripts, strategy entrypoints intentionally deferred, or registry/DSL-compatible names.

- [ ] **Step 3: Write migration report**

Create `factor_research/docs/ontology_refactor_migration_report.md`:

```markdown
# Ontology Refactor Migration Report

## Scope

This migration introduced canonical names for the highest-confusion ontology terms while preserving backward-compatible wrappers.

## Canonical Entrypoints Added

- `engine.factor_composer`
- `engine.signal_factory.factor_to_signal`
- `portfolio.portfolio_composer`
- `factors.alpha.transforms.zscore_cross_section`
- `engine.neutralize.zscore_series`
- `policy.candidate_filters.loser_reversal_filter`
- `factors.illiquidity_components.salience_covariance_score`
- `factors.small_cap.small_cap_exposure_signal`

## Compatibility Entrypoints Retained

- `engine.composer`
- `engine.portfolio.to_signal`
- `portfolio.composer`
- `factors.alpha.transforms.zscore`
- `engine.neutralize.zscore`
- `factors.veto.loser_veto_reversal`
- `factors.veto.salience_covariance_veto`
- `factors.small_cap.small_cap_timing`

## Semantics Preserved

- No strategy formula changed.
- No registry status or evidence changed.
- No cost model changed.
- No `shift(1)`, T+1, rebalance frequency, universe filter, or veto refill behavior changed.

## Verification

- `python3 tests/test_naming_taxonomy.py`
- `python3 tests/test_factor_composer_taxonomy.py`
- `python3 tests/test_signal_factory.py`
- `python3 tests/test_factor_normalization_axis.py`
- `python3 tests/test_veto_filter.py`
- `python3 tests/test_timing_taxonomy.py`
- `python3 scripts/ci/check_naming_taxonomy.py`
- `python3 scripts/ci/check_layer_deps.py`
- `bash scripts/test_all.sh`

## Deferred Work

- Rename `latest_signal` to `latest_decision` only after production/Web consumers are mapped.
- Migrate historical research scripts opportunistically; do not churn archived or scratch files.
- Remove compatibility wrappers only after one release cycle and a clean `rg` audit.
```

- [ ] **Step 4: Commit report**

```bash
git add factor_research/docs/ontology_refactor_migration_report.md
git diff --cached --stat
git diff --cached
git commit -m "docs(factor-research): record ontology refactor migration"
```

---

## Rollback Strategy

- If a task fails targeted tests, revert only that task's commit.
- Because wrappers preserve old imports, Tasks 2-6 should be reversible without requiring registry or production config changes.
- Do not remove old names in this plan. Removal is a separate deprecation cleanup after full caller migration.

## Final Definition of Done

- `factor_research/docs/naming_taxonomy.md` exists and is linked from `ontology_glossary.md`.
- Canonical modules exist for composer, signal factory, zscore, veto policy, salience component, and small-cap timing.
- Old names still work and are tested against canonical names.
- New naming guard runs in `scripts/test_all.sh`.
- `python3 scripts/ci/check_layer_deps.py` passes.
- `bash factor_research/scripts/test_all.sh` passes, or any failure is proven unrelated to this refactor with exact command output.
- No strategy metrics, registry entries, costs, or production deployment manifests are changed.

## Execution Notes

- Recommended execution mode: subagent-driven, one task per subagent, with review after each commit-sized task.
- If executing inline, stop after each task and inspect `git diff --stat` before continuing.
- Current repository has a large dirty worktree. Re-check `git status --short` before starting and do not stage unrelated files.
