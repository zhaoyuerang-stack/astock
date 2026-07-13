"""对抗:momentum/fundamental/northbound/alpha101 迁移到 @register_factor 后三面一致。

护栏:
  · discover() 含可搜索核心因子,且 searchable 元数据正确
  · ALLOWED_FACTORS / DSL _FACTOR_CALLS 由 discover 自动接线(不靠大段手工表)
  · factors.momentum 兼容 shim 仍可 import
  · earnings 已登记但 searchable=False(probe-ready,不进搜索宇宙)
  · quality / gap_reversal 不在注册表与搜索白名单
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_discover_includes_migrated_searchable_families():
    from factors.registry import discover

    reg = discover()
    # 价行为 / 流动性 / 基本面 / 北向 / alpha 样本
    for name in (
        "momentum",
        "volatility",
        "volume_ratio",
        "illiquidity",
        "roe",
        "net_profit_yoy",
        "bp_proxy",
        "northbound_accumulation",
        "alpha_001",
        "alpha_055",
    ):
        assert name in reg, f"missing register_factor: {name}"
        assert reg[name].searchable is True, name


def test_earnings_registered_but_not_searchable():
    from factors.registry import discover
    from factory.autoresearch.registry import ALLOWED_FACTORS

    reg = discover()
    assert "sue" in reg and reg["sue"].searchable is False
    assert "earnings_forecast_surprise" in reg
    assert reg["earnings_forecast_surprise"].searchable is False
    assert "sue" not in ALLOWED_FACTORS
    assert "earnings_forecast_surprise" not in ALLOWED_FACTORS


def test_allowed_factors_and_dsl_auto_wired():
    from factory.autoresearch.registry import ALLOWED_FACTORS
    from factors.autoresearch_dsl import _FACTOR_CALLS

    # 迁移后白名单规模应稳定(含 holder/large_order 覆盖 + searchable 自动)
    assert len(ALLOWED_FACTORS) >= 40
    for name in ("momentum", "illiquidity", "roe", "northbound_hold_level", "alpha_009"):
        assert name in ALLOWED_FACTORS, name
        assert name in _FACTOR_CALLS, name
        mod, fn, _ = _FACTOR_CALLS[name]
        assert mod.startswith("factors."), mod
        assert fn  # non-empty


def test_momentum_shim_reexports_from_split_modules():
    from factors import momentum
    from factors import price_action, liquidity

    assert momentum.mom_n is price_action.mom_n
    assert momentum.illiquidity is liquidity.illiquidity
    assert momentum.volatility is price_action.volatility
    assert momentum.vol_ratio is liquidity.vol_ratio


def test_dsl_illiquidity_resolves_to_liquidity_module():
    from factors.autoresearch_dsl import _FACTOR_CALLS

    mod, fn, amap = _FACTOR_CALLS["illiquidity"]
    assert mod == "factors.liquidity"
    assert fn == "illiquidity"
    assert amap.get("window") == "n"


def test_deprecated_quality_and_gap_not_in_registry_or_search():
    from factors.registry import discover
    from factory.autoresearch.registry import ALLOWED_FACTORS
    from factors.autoresearch_dsl import _FACTOR_CALLS

    reg = discover()
    for name in (
        "gap_reversal",
        "gap_reversal_zscore",
        "overnight_gap",
        "roe_ttm",
        "accrual",
        "cfo_to_assets",
    ):
        assert name not in reg
        assert name not in ALLOWED_FACTORS
        assert name not in _FACTOR_CALLS


def test_deprecated_shims_warn_on_import():
    import importlib

    for mod in ("factors.quality", "factors.gap_reversal"):
        # force re-import warning
        if mod in sys.modules:
            del sys.modules[mod]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            importlib.import_module(mod)
            deprec = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert deprec, f"{mod} should emit DeprecationWarning"


def test_banned_alphas_still_not_searchable():
    from factors.registry import discover
    from factory.autoresearch.registry import ALLOWED_FACTORS

    reg = discover()
    for name in ("alpha_005", "alpha_020", "alpha_024", "alpha_049"):
        assert name not in ALLOWED_FACTORS
        # may or may not be in reg; if present must not be searchable
        if name in reg:
            assert reg[name].searchable is False


if __name__ == "__main__":
    test_discover_includes_migrated_searchable_families()
    test_earnings_registered_but_not_searchable()
    test_allowed_factors_and_dsl_auto_wired()
    test_momentum_shim_reexports_from_split_modules()
    test_dsl_illiquidity_resolves_to_liquidity_module()
    test_deprecated_quality_and_gap_not_in_registry_or_search()
    test_deprecated_shims_warn_on_import()
    test_banned_alphas_still_not_searchable()
    print("ok")
