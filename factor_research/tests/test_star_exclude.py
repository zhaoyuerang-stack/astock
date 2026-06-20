"""科创板(688)处理:数据层 volume 单位修正 + 小盘 universe 显式排除。

Run:
    cd factor_research && python3 tests/test_star_exclude.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lake.load_lake import _normalize_star_volume  # noqa: E402
from strategies.small_cap import StrategyConfig, _drop_star  # noqa: E402


def test_normalize_star_volume_divides_688_only():
    idx = pd.bdate_range("2024-01-01", periods=3)
    vol = pd.DataFrame({"600519": [100.0, 100, 100],
                        "300750": [100.0, 100, 100],
                        "688256": [100.0, 100, 100]}, index=idx)
    out = _normalize_star_volume({"volume": vol.copy()})["volume"]
    assert (out["600519"] == 100).all()   # 主板不变
    assert (out["300750"] == 100).all()   # 创业板不变
    assert (out["688256"] == 1.0).all()   # 科创板 ÷100(股→手)
    print("✅ 688 volume ÷100,主板/创业板不变")


def test_normalize_star_volume_noop_without_volume():
    idx = pd.bdate_range("2024-01-01", periods=2)
    close = pd.DataFrame({"688256": [10.0, 11]}, index=idx)
    out = _normalize_star_volume({"close": close.copy()})
    assert (out["close"]["688256"] == close["688256"]).all()  # 无 volume 字段时不动
    print("✅ 无 volume 字段时幂等")


def test_drop_star_removes_688_columns():
    idx = pd.bdate_range("2024-01-01", periods=2)
    df = pd.DataFrame({"600519": [1.0, 2], "688256": [3.0, 4], "300750": [5.0, 6]}, index=idx)
    (out,) = _drop_star(df)
    assert list(out.columns) == ["600519", "300750"]  # 688 被剔除
    print("✅ _drop_star 剔除 688 列")


def test_exclude_star_default_on():
    assert StrategyConfig().exclude_star is True  # 默认排除科创板(保留验证过的口径)
    print("✅ exclude_star 默认 True")


if __name__ == "__main__":
    test_normalize_star_volume_divides_688_only()
    test_normalize_star_volume_noop_without_volume()
    test_drop_star_removes_688_columns()
    test_exclude_star_default_on()
    print("\n🎉 科创板处理 tests passed!")
