"""§四修法②:islands fitness 的「方向」(directional)+「正交增量」(orth)项。

- directional=True:edge=max(ICIR,0),错号(负 ICIR)归零 → 根治进化用 neg/翻号刷分。
- orth_weight>0:罚对 size/流动性风格暴露 → 逼搜索保持正交。
默认(directional=False, orth_weight=0)完全向后兼容,既有 fitness 硬断言测试不变。
"""
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from factory.autoresearch.islands import _style_exposure, run_island_search
from factory.autoresearch.repositories import CandidateRepository, ExperimentLog, ReviewQueue
from factory.lines.line2_validation.l0_ic_scan import precompute_forward_returns
from factory.ontology import Decision, Experiment, ExperimentProtocol, ExperimentResult


def _synth():
    rng = np.random.default_rng(0)
    dates = pd.bdate_range("2020-01-01", periods=420)
    codes = [f"{i:06d}" for i in range(25)]
    close = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0, 0.02, (420, 25)), axis=0)), index=dates, columns=codes
    )
    volume = pd.DataFrame(rng.lognormal(15, 0.5, (420, 25)), index=dates, columns=codes)
    return close, volume, close * volume


def _run(directional, icir):
    def fake_l0(hyp, *a, **k):
        return Experiment(
            experiment_id="f", hypothesis_id=hyp.id, protocol=ExperimentProtocol.L0_IC_SCAN,
            vintage_id=k.get("vintage_id", "syn"),
            result=ExperimentResult(metrics={"ICIR": icir}, details={"direction": "long"}),
            decision=Decision.PROMOTE, notes="",
        )

    close, volume, amount = _synth()
    fwd = precompute_forward_returns(close)
    with tempfile.TemporaryDirectory() as td:
        r = Path(td)
        return run_island_search(
            close, volume, amount, fwd, vintage_id="syn",
            n_islands=2, generations=1, population=4, top_k=4, rng_seed=7,
            runners={"l0": fake_l0}, directional=directional,
            repository=CandidateRepository(r / "c.jsonl"),
            experiment_log=ExperimentLog(r / "e.jsonl"),
            review_queue=ReviewQueue(r / "q.jsonl"),
        )


def test_directional_zeros_wrong_sign():
    # 错号(ICIR=-0.1):默认 edge=|icir|=0.1;directional edge=max(icir,0)=0
    for c in _run(False, -0.1).champions:
        assert abs(c.fitness - (abs(c.icir) + 0.25 * c.novelty)) < 1e-9
    champs = _run(True, -0.1).champions
    assert champs
    for c in champs:
        assert c.icir < 0
        assert abs(c.fitness - (max(c.icir, 0.0) + 0.25 * c.novelty)) < 1e-9


def test_directional_keeps_right_sign():
    # 正号(ICIR=0.1):directional 不改变(max=icir)
    for c in _run(True, 0.1).champions:
        assert abs(c.fitness - (0.1 + 0.25 * c.novelty)) < 1e-9


def test_style_exposure_proxy_vs_orthogonal():
    rng = np.random.default_rng(1)
    dates = pd.bdate_range("2020-01-01", periods=6)
    codes = [f"{i:06d}" for i in range(40)]
    style = pd.DataFrame(rng.normal(size=(6, 40)), index=dates, columns=codes)
    assert _style_exposure(style, [style]) == pytest.approx(1.0, abs=1e-9)  # 与自身=1
    orth = pd.DataFrame(rng.normal(size=(6, 40)), index=dates, columns=codes)
    assert _style_exposure(orth, [style]) < 0.5  # 独立随机 → 低暴露


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-q"]))
