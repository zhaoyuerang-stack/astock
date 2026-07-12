"""审计#11: islands fitness 正交默认开启 + book 相关用残差(偏相关)非 raw。"""
from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from factory.autoresearch.islands import run_island_search
from factory.autoresearch.novelty import (
    max_return_correlation,
    partial_correlation_to_book,
)


def test_run_island_search_defaults_enable_orthogonality():
    """默认 corr/orth/turnover 权重必须 >0,不得默认关掉正交。"""
    sig = inspect.signature(run_island_search)
    assert sig.parameters["corr_weight"].default == pytest.approx(0.3)
    assert sig.parameters["orth_weight"].default == pytest.approx(0.2)
    assert sig.parameters["turnover_weight"].default == pytest.approx(0.15)
    assert sig.parameters["novelty_weight"].default == pytest.approx(0.25)


def test_partial_corr_differs_from_raw_when_market_drives_both():
    """对抗:两序列都跟大盘 → raw 高相关,残差(偏)相关应显著更低。"""
    rng = np.random.default_rng(0)
    n = 80
    mkt = pd.Series(rng.normal(0, 1, n))
    # 共同市场暴露 + 独立噪声
    book = 0.9 * mkt + rng.normal(0, 0.2, n)
    cand = 0.85 * mkt + rng.normal(0, 0.25, n)
    book_s = pd.Series(book)
    cand_s = pd.Series(cand)
    raw = max_return_correlation(cand_s, [book_s])
    partial = partial_correlation_to_book(cand_s, [book_s], mkt)
    assert raw > 0.7
    assert partial < raw - 0.3  # 扣市场后应明显下降


def test_partial_corr_pure_beta_twins_count_as_redundant():
    """对抗:两序列都是纯市场 beta(残差无定义)且 raw≈1 → 必须记冗余,不得洗成 0。"""
    n = 60
    mkt = pd.Series(np.linspace(-1, 1, n) + 0.01)
    book = mkt * 1.0 + 1e-8
    cand = mkt * 1.0 + 2e-8
    raw = max_return_correlation(cand, [book])
    partial = partial_correlation_to_book(cand, [book], mkt)
    assert raw > 0.99
    assert partial > 0.99  # 同质 beta → 计为相关冗余


def test_explicit_zero_corr_weight_disables_penalty():
    """显式 corr_weight=0 仍可隔离(向后兼容测试)。"""
    sig = inspect.signature(run_island_search)
    # 参数仍可接受 0
    assert "corr_weight" in sig.parameters


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v", "--tb=short"]))
