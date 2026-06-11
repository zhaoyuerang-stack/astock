"""Auto Factor Research Engine: DSL/guard/decision safety tests.

Run:
    cd factor_research && python3 tests/test_autoresearch_engine.py
"""
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from factory.autoresearch import (  # noqa: E402
    CandidateDecision,
    CandidateRepository,
    CandidateStatus,
    ExperimentLog,
    ReviewQueue,
    ast_to_hypothesis,
    compute_complexity,
    evaluate_lite,
    factor_redundancy_score,
    fingerprint_ast,
    generate_seed_candidates,
    run_validation_pipeline,
    validate_candidate_ast,
)
from factory.ontology import Decision, Experiment, ExperimentProtocol, ExperimentResult  # noqa: E402
from factory.autoresearch.guards import LeakageGuardError, run_leakage_guard  # noqa: E402
from factory.autoresearch.validator import DSLValidationError  # noqa: E402
from services.read.autoresearch import (  # noqa: E402
    autoresearch_candidates,
    autoresearch_funnel,
    autoresearch_review_queue,
)


def _candidate(weight: float = 0.7) -> dict:
    return {
        "type": "linear_combo",
        "terms": [
            {
                "factor": "momentum",
                "params": {"window": 20},
                "transforms": ["mad_clip", "zscore", "rank"],
                "weight": weight,
            },
            {
                "factor": "volume_ratio",
                "params": {"window": 5},
                "transforms": ["mad_clip", "zscore", "rank"],
                "weight": round(1 - weight, 2),
            },
        ],
        "direction": "positive",
        "thesis": {
            "mechanism": "动量和放量共同刻画关注度上升后的截面延续。",
            "citation": "internal hypothesis",
        },
    }


def test_json_ast_validation_rejects_free_string_and_unknown_ops():
    candidate = validate_candidate_ast(_candidate())
    assert candidate.ast["type"] == "linear_combo"
    assert candidate.fingerprint == fingerprint_ast(_candidate())
    assert candidate.status == CandidateStatus.GENERATED

    try:
        validate_candidate_ast({"expr": "rank(momentum_20d) + future_return"})
        raise AssertionError("free-form expression should be rejected")
    except DSLValidationError as e:
        assert "JSON AST" in str(e)

    bad = _candidate()
    bad["terms"][0]["transforms"] = ["zscore", "python_eval"]
    try:
        validate_candidate_ast(bad)
        raise AssertionError("unknown transform should be rejected")
    except DSLValidationError as e:
        assert "transform" in str(e)


def test_neutralize_declaration_rejected_until_runtime_supports_it():
    # compute_dsl_factor 尚未实现中性化;声明了却不执行 = 口径不透明,必须拒绝。
    ast = _candidate()
    ast["neutralize"] = ["industry"]
    try:
        validate_candidate_ast(ast)
        raise AssertionError("non-empty neutralize should be rejected")
    except DSLValidationError as e:
        assert "neutralize" in str(e)


def test_fingerprint_is_stable_and_repository_dedupes():
    left = _candidate()
    right = _candidate()
    right["terms"][0]["params"] = {"window": 20}  # same content, fresh dict

    assert fingerprint_ast(left) == fingerprint_ast(right)

    with tempfile.TemporaryDirectory() as td:
        repo = CandidateRepository(Path(td) / "candidates.jsonl")
        first = repo.add(validate_candidate_ast(left))
        second = repo.add(validate_candidate_ast(right))
        assert first is True
        assert second is False
        assert len(repo.all()) == 1


def test_candidate_generator_produces_unique_valid_ast_batch():
    candidates = list(generate_seed_candidates(limit=10))
    assert len(candidates) == 10
    assert len({c.fingerprint for c in candidates}) == 10
    assert all(c.ast["type"] == "linear_combo" for c in candidates)
    assert all(compute_complexity(c).score <= 5 for c in candidates)


def test_ast_to_hypothesis_uses_controlled_runtime_factor():
    candidate = validate_candidate_ast(_candidate())
    hyp = ast_to_hypothesis(candidate)
    assert hyp.factor_fn_name == "factors.autoresearch_dsl.compute_dsl_factor"
    assert hyp.factor_params["ast"] == candidate.ast
    assert "price/close" in hyp.data_dependencies
    assert "price/volume" in hyp.data_dependencies
    assert hyp.source == "autoresearch"
    assert hyp.source_ref == candidate.fingerprint


def test_dsl_runtime_factor_computes_linear_combo_panel():
    from factors.autoresearch_dsl import compute_dsl_factor

    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    close = pd.DataFrame(
        {
            "A": range(10, 40),
            "B": range(40, 10, -1),
            "C": [20 + (i % 5) for i in range(30)],
        },
        index=dates,
        dtype=float,
    )
    volume = pd.DataFrame(
        {
            "A": range(100, 130),
            "B": range(130, 100, -1),
            "C": [100 + (i % 3) for i in range(30)],
        },
        index=dates,
        dtype=float,
    )
    factor = compute_dsl_factor(close, volume, ast=_candidate())
    assert factor.shape == close.shape
    assert factor.index.equals(close.index)
    assert factor.columns.equals(close.columns)
    assert factor.iloc[-1].notna().sum() >= 2


def test_complexity_budget_blocks_overfit_candidates():
    simple = validate_candidate_ast(_candidate())
    assert compute_complexity(simple).score <= 5

    complex_ast = _candidate()
    complex_ast["terms"] = complex_ast["terms"] + [
        {
            "factor": "volatility",
            "params": {"window": 23},
            "transforms": ["mad_clip", "zscore", "rank", "neg"],
            "weight": 0.13,
        },
        {
            "factor": "roe",
            "params": {},
            "transforms": ["mad_clip", "zscore", "rank"],
            "weight": 0.11,
        },
    ]
    complex_ast["regime_filter"] = {"type": "market_state", "allowed": ["bull"]}
    complex_ast["industry_scope"] = ["801010", "801020"]

    complex_candidate = validate_candidate_ast(complex_ast)
    complexity = compute_complexity(complex_candidate)
    assert complexity.score > 8
    assert complexity.max_auto_stage == "review_only"


def test_leakage_guard_blocks_future_and_label_fields():
    candidate = validate_candidate_ast(_candidate())
    report = run_leakage_guard(candidate)
    assert report.passed is True

    bad_ast = _candidate()
    bad_ast["terms"][0]["factor"] = "future_return_20d"
    try:
        bad = validate_candidate_ast(bad_ast, allow_experimental_factors=True)
        run_leakage_guard(bad)
        raise AssertionError("future-looking factor should be blocked")
    except LeakageGuardError as e:
        assert "future" in str(e).lower() or "label" in str(e).lower()


def test_redundancy_score_combines_multiple_similarity_inputs():
    low = factor_redundancy_score(
        spearman_corr=0.1,
        normalized_mi=0.2,
        holding_overlap=0.1,
        return_corr=0.1,
        exposure_similarity=0.2,
    )
    high = factor_redundancy_score(
        spearman_corr=0.9,
        normalized_mi=0.8,
        holding_overlap=0.7,
        return_corr=0.9,
        exposure_similarity=0.8,
    )
    assert 0 <= low.score < 0.25
    assert high.score > 0.75


def test_lite_engine_logs_discard_shelve_and_promote_without_registry_write():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        repo = CandidateRepository(root / "candidates.jsonl")
        review = ReviewQueue(root / "review_queue.jsonl")

        good = validate_candidate_ast(_candidate())
        result = evaluate_lite(
            good,
            l0_metrics={
                "rank_ic_mean": 0.035,
                "icir": 0.55,
                "coverage": 0.91,
                "nan_ratio": 0.02,
                "extreme_ratio": 0.01,
            },
            l1_metrics={
                "monotonic_groups": True,
                "top_bottom_return": 0.08,
                "cost_after_return": 0.05,
                "turnover": 0.8,
            },
            redundancy_inputs={
                "spearman_corr": 0.15,
                "normalized_mi": 0.2,
                "holding_overlap": 0.1,
                "return_corr": 0.1,
                "exposure_similarity": 0.2,
            },
            repository=repo,
            review_queue=review,
        )
        assert result.decision == CandidateDecision.PROMOTE
        assert result.status == CandidateStatus.PROMOTED_TO_REVIEW
        assert len(review.all()) == 1
        assert not (root / "strategy_versions.json").exists()

        redundant = validate_candidate_ast(_candidate(weight=0.6))
        shelved = evaluate_lite(
            redundant,
            l0_metrics={
                "rank_ic_mean": 0.04,
                "icir": 0.7,
                "coverage": 0.95,
                "nan_ratio": 0.01,
                "extreme_ratio": 0.01,
            },
            l1_metrics={
                "monotonic_groups": True,
                "top_bottom_return": 0.09,
                "cost_after_return": 0.06,
                "turnover": 0.7,
            },
            redundancy_inputs={
                "spearman_corr": 0.9,
                "normalized_mi": 0.8,
                "holding_overlap": 0.8,
                "return_corr": 0.9,
                "exposure_similarity": 0.8,
            },
            repository=repo,
            review_queue=review,
        )
        assert shelved.decision == CandidateDecision.SHELVE
        assert shelved.status == CandidateStatus.SHELVED

        weak = validate_candidate_ast(_candidate(weight=0.5))
        discarded = evaluate_lite(
            weak,
            l0_metrics={
                "rank_ic_mean": 0.005,
                "icir": 0.1,
                "coverage": 0.9,
                "nan_ratio": 0.02,
                "extreme_ratio": 0.01,
            },
            l1_metrics={},
            redundancy_inputs={},
            repository=repo,
            review_queue=review,
        )
        assert discarded.decision == CandidateDecision.DISCARD
        assert discarded.status == CandidateStatus.DISCARDED
        assert len(repo.all()) == 3


def test_experiment_log_roundtrips_decision_enum():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        log = ExperimentLog(root / "experiment_log.jsonl")
        result = evaluate_lite(
            validate_candidate_ast(_candidate()),
            l0_metrics={
                "rank_ic_mean": 0.035,
                "icir": 0.55,
                "coverage": 0.91,
                "nan_ratio": 0.02,
                "extreme_ratio": 0.01,
            },
            l1_metrics={
                "monotonic_groups": True,
                "top_bottom_return": 0.08,
                "cost_after_return": 0.05,
                "turnover": 0.8,
            },
            redundancy_inputs={
                "spearman_corr": 0.15,
                "normalized_mi": 0.2,
                "holding_overlap": 0.1,
                "return_corr": 0.1,
                "exposure_similarity": 0.2,
            },
            repository=CandidateRepository(root / "candidates.jsonl"),
            experiment_log=log,
            review_queue=ReviewQueue(root / "review_queue.jsonl"),
        )
        loaded = list(log.iter_all())
        assert len(loaded) == 1
        assert loaded[0].decision == result.decision == CandidateDecision.PROMOTE


def test_validation_pipeline_runs_l0_to_l3_and_promotes_only_after_l3():
    calls: list[str] = []

    def fake(protocol: ExperimentProtocol, decision: Decision):
        def _run(hyp, *args, **kwargs):
            calls.append(protocol.value)
            return Experiment(
                experiment_id=f"fake-{protocol.value}",
                hypothesis_id=hyp.id,
                protocol=protocol,
                vintage_id=kwargs.get("vintage_id", "test-vintage"),
                result=ExperimentResult(
                    metrics={"ok": 1.0},
                    details={"direction": "long" if protocol == ExperimentProtocol.L0_IC_SCAN else 1},
                ),
                decision=decision,
                notes="fake pass",
            )
        return _run

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        candidate = validate_candidate_ast(_candidate())
        result = run_validation_pipeline(
            candidate,
            close=pd.DataFrame(),
            volume=pd.DataFrame(),
            amount=pd.DataFrame(),
            forward_ret=pd.DataFrame(),
            vintage_id="test-vintage",
            repository=CandidateRepository(root / "candidates.jsonl"),
            experiment_log=ExperimentLog(root / "experiment_log.jsonl"),
            review_queue=ReviewQueue(root / "review_queue.jsonl"),
            runners={
                "l0": fake(ExperimentProtocol.L0_IC_SCAN, Decision.PROMOTE),
                "l1": fake(ExperimentProtocol.L1_QUICK_BT, Decision.PROMOTE),
                "l2": fake(ExperimentProtocol.L2_MULTI_REGIME, Decision.PROMOTE),
                "l3": fake(ExperimentProtocol.L3_WALK_FORWARD, Decision.PROMOTE),
            },
        )
        assert calls == ["l0_ic_scan", "l1_quick_bt", "l2_multi_regime", "l3_walk_forward"]
        assert result.status == CandidateStatus.PROMOTED_TO_REVIEW
        assert result.decision == CandidateDecision.PROMOTE
        assert len(ReviewQueue(root / "review_queue.jsonl").all()) == 1


def _synthetic_panel(n_days: int = 420, n_stocks: int = 25):
    """确定性合成面板:逐股持续漂移,使动量在截面上可预测,不依赖 data_lake。"""
    import numpy as np

    rng = np.random.default_rng(7)
    dates = pd.bdate_range("2021-01-04", periods=n_days)
    codes = [f"{600000 + i:06d}" for i in range(n_stocks)]
    drift = np.linspace(-0.0015, 0.0015, n_stocks)
    rets = drift + rng.normal(0.0, 0.01, size=(n_days, n_stocks))
    close = pd.DataFrame(100.0 * np.exp(np.cumsum(rets, axis=0)), index=dates, columns=codes)
    volume = pd.DataFrame(
        rng.integers(200_000, 5_000_000, size=(n_days, n_stocks)).astype(float),
        index=dates,
        columns=codes,
    )
    amount = close * volume
    return close, volume, amount


def test_real_runners_accept_autoresearch_hypothesis_contract():
    """逐级调用真实 run_l0..run_l3,验证桥接契约:F-1/F-2 铁律、签名、DSL 运行时解析。

    Experiment.result.error 必须为 None;decision 由真实 gate 决定,不在断言范围。
    """
    from factory.autoresearch.pipeline import _hyp_with_status
    from factory.lines.line2_validation.l0_ic_scan import precompute_forward_returns, run_l0
    from factory.lines.line2_validation.l1_quick_bt import run_l1
    from factory.lines.line2_validation.l2_multi_regime import run_l2
    from factory.lines.line2_validation.l3_walk_forward import run_l3
    from factory.ontology import HypothesisStatus

    close, volume, amount = _synthetic_panel()
    forward_ret = precompute_forward_returns(close)
    candidate = validate_candidate_ast(_candidate())
    hyp = ast_to_hypothesis(candidate)
    assert hyp.status == HypothesisStatus.QUEUED  # F-2: run_l0 入口要求 QUEUED

    exp0 = run_l0(hyp, close, volume, amount, forward_ret, vintage_id="synthetic")
    assert exp0.result.error is None, exp0.result.error

    hyp = _hyp_with_status(hyp, HypothesisStatus.L0_PASSED)
    exp1 = run_l1(hyp, close, volume, amount, direction=1, vintage_id="synthetic", start="2021-01-04")
    assert exp1.result.error is None, exp1.result.error

    hyp = _hyp_with_status(hyp, HypothesisStatus.L1_PASSED)
    exp2 = run_l2(hyp, close, volume, amount, direction=1, vintage_id="synthetic", start="2021-01-04")
    assert exp2.result.error is None, exp2.result.error

    hyp = _hyp_with_status(hyp, HypothesisStatus.L2_PASSED)
    exp3 = run_l3(hyp, close, volume, amount, direction=1, vintage_id="synthetic", start="2021-01-04")
    assert exp3.result.error is None, exp3.result.error


def test_validation_pipeline_executes_real_l0_on_synthetic_panel():
    """端到端走默认真实 runner(max_stage=l0),决策交给真实 gate,只要求不报错。"""
    from factory.lines.line2_validation.l0_ic_scan import precompute_forward_returns

    close, volume, amount = _synthetic_panel()
    forward_ret = precompute_forward_returns(close)
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        candidate = validate_candidate_ast(_candidate())
        result = run_validation_pipeline(
            candidate,
            close=close,
            volume=volume,
            amount=amount,
            forward_ret=forward_ret,
            vintage_id="synthetic",
            repository=CandidateRepository(root / "candidates.jsonl"),
            experiment_log=ExperimentLog(root / "experiment_log.jsonl"),
            review_queue=ReviewQueue(root / "review_queue.jsonl"),
            max_stage="l0",
        )
        experiments = result.metrics["experiments"]
        assert experiments and experiments[0]["protocol"] == "l0_ic_scan"
        assert all(e["error"] is None for e in experiments), experiments


def test_run_autoresearch_seeds_action_uses_pipeline_contract():
    from services.actions.autoresearch import run_autoresearch_seeds

    def fake_l0(hyp, *args, **kwargs):
        return Experiment(
            experiment_id="fake-l0",
            hypothesis_id=hyp.id,
            protocol=ExperimentProtocol.L0_IC_SCAN,
            vintage_id=kwargs.get("vintage_id", "test-vintage"),
            result=ExperimentResult(metrics={"ICIR": 0.1}, details={"direction": "long"}),
            decision=Decision.PROMOTE,
            notes="fake l0 pass",
        )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        response = run_autoresearch_seeds(
            limit=2,
            max_stage="l0",
            close=pd.DataFrame(),
            volume=pd.DataFrame(),
            amount=pd.DataFrame(),
            forward_ret=pd.DataFrame(),
            vintage_id="test-vintage",
            repository=CandidateRepository(root / "candidates.jsonl"),
            experiment_log=ExperimentLog(root / "experiment_log.jsonl"),
            review_queue=ReviewQueue(root / "review_queue.jsonl"),
            runners={"l0": fake_l0},
        )
        assert response.max_stage == "l0"
        assert len(response.results) == 2
        assert all(r.protocols == ["l0_ic_scan"] for r in response.results)
        assert all(r.status == "l0_passed" for r in response.results)
        assert not (root / "strategy_versions.json").exists()


def test_human_review_approve_reject_without_registry_write():
    from services.actions.autoresearch import review_autoresearch_candidate

    promote_kwargs = dict(
        l0_metrics={"rank_ic_mean": 0.035, "icir": 0.55, "coverage": 0.91, "nan_ratio": 0.02, "extreme_ratio": 0.01},
        l1_metrics={"monotonic_groups": True, "top_bottom_return": 0.08, "cost_after_return": 0.05, "turnover": 0.8},
        redundancy_inputs={"spearman_corr": 0.15, "normalized_mi": 0.2, "holding_overlap": 0.1, "return_corr": 0.1, "exposure_similarity": 0.2},
    )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        repo = CandidateRepository(root / "candidates.jsonl")
        review = ReviewQueue(root / "review_queue.jsonl")

        approved_cand = validate_candidate_ast(_candidate())
        rejected_cand = validate_candidate_ast(_candidate(weight=0.6))
        for cand in (approved_cand, rejected_cand):
            result = evaluate_lite(cand, repository=repo, review_queue=review, **promote_kwargs)
            assert result.decision == CandidateDecision.PROMOTE
        assert len(review.pending()) == 2

        # approve:推进状态,但绝不写台账
        item = review_autoresearch_candidate(
            fingerprint=approved_cand.fingerprint, action="approve", notes="机制可信,转 workflow promote",
            repository=repo, review_queue=review,
        )
        assert item.review_action == "approve"
        assert item.status == CandidateStatus.APPROVED.value
        assert repo.get(approved_cand.fingerprint).status == CandidateStatus.APPROVED

        # reject
        item = review_autoresearch_candidate(
            fingerprint=rejected_cand.fingerprint, action="reject", notes="与现有 illiquidity 冗余",
            repository=repo, review_queue=review,
        )
        assert item.status == CandidateStatus.REJECTED_BY_HUMAN.value
        assert repo.get(rejected_cand.fingerprint).status == CandidateStatus.REJECTED_BY_HUMAN

        # 决策后不再 pending;重复决策 / 未知 fingerprint / 非法 action 全部拒绝
        assert len(review.pending()) == 0
        for bad in (
            dict(fingerprint=approved_cand.fingerprint, action="reject"),
            dict(fingerprint="deadbeef", action="approve"),
            dict(fingerprint=rejected_cand.fingerprint, action="retire"),
        ):
            try:
                review_autoresearch_candidate(repository=repo, review_queue=review, **bad)
                raise AssertionError(f"should reject: {bad}")
            except ValueError:
                pass

        # 重新加载验证 append-only 持久化(latest wins)
        reloaded = ReviewQueue(root / "review_queue.jsonl")
        assert reloaded.get(approved_cand.fingerprint)["review_action"] == "approve"
        assert len(reloaded.pending()) == 0
        assert not (root / "strategy_versions.json").exists()


def test_promote_approved_candidate_gates_and_calls_workflow_promote():
    from services.actions.autoresearch import promote_approved_candidate, review_autoresearch_candidate

    promote_kwargs = dict(
        l0_metrics={"rank_ic_mean": 0.035, "icir": 0.55, "coverage": 0.91, "nan_ratio": 0.02, "extreme_ratio": 0.01},
        l1_metrics={"monotonic_groups": True, "top_bottom_return": 0.08, "cost_after_return": 0.05, "turnover": 0.8},
        redundancy_inputs={"spearman_corr": 0.15, "normalized_mi": 0.2, "holding_overlap": 0.1, "return_corr": 0.1, "exposure_similarity": 0.2},
    )

    class FakeReport:
        registered = True
        detail = "registered by fake phase4"

    calls = []

    def fake_promote(hyp, version="v1.0", **kw):
        calls.append((hyp.name, version))
        return FakeReport()

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        repo = CandidateRepository(root / "candidates.jsonl")
        review = ReviewQueue(root / "review_queue.jsonl")
        cand = validate_candidate_ast(_candidate())
        evaluate_lite(cand, repository=repo, review_queue=review, **promote_kwargs)

        # 未 approve 不允许入册
        try:
            promote_approved_candidate(fingerprint=cand.fingerprint, repository=repo, review_queue=review, promote_fn=fake_promote)
            raise AssertionError("pending candidate must not be promotable")
        except ValueError as e:
            assert "not approved" in str(e)

        review_autoresearch_candidate(fingerprint=cand.fingerprint, action="approve", repository=repo, review_queue=review)
        resp = promote_approved_candidate(
            fingerprint=cand.fingerprint, version="v2.0",
            repository=repo, review_queue=review, promote_fn=fake_promote,
        )
        assert resp.registered is True
        assert resp.version == "v2.0"
        assert calls == [(f"autoresearch_{cand.fingerprint[:8]}", "v2.0")]
        assert "registered" in repo.get(cand.fingerprint).notes
        # 本动作自身绝不写台账
        assert not (root / "strategy_versions.json").exists()


class _FakeLLMAdapter:
    name = "fake"
    model = "fake-model"

    def __init__(self, text):
        self._text = text

    def available(self):
        return True

    def complete(self, system, user, max_tokens=2000):
        assert "momentum" in system and "白名单" in system  # DSL spec 必须注入 prompt
        return self._text


def test_llm_generation_validates_rejects_and_dedupes():
    import json as _json

    from factory.autoresearch.validator import validate_candidate_ast as _v
    from services.actions.autoresearch_llm import generate_llm_candidates

    good = _candidate()
    bad_factor = _candidate()
    bad_factor["terms"][0]["factor"] = "future_return_20d"
    payload = "```json\n" + _json.dumps([good, bad_factor, good]) + "\n```"

    with tempfile.TemporaryDirectory() as td:
        repo = CandidateRepository(Path(td) / "candidates.jsonl")
        accepted, rejected, model = generate_llm_candidates(
            n=3, adapter=_FakeLLMAdapter(payload), repository=repo,
        )
        assert model == "fake-model"
        assert len(accepted) == 1 and accepted[0].source == "llm"
        assert accepted[0].fingerprint == _v(good).fingerprint
        assert len(rejected) == 2  # 非法因子 + 重复 fingerprint

        # 仓库里已有的 fingerprint 也要拒
        repo.add(accepted[0])
        accepted2, rejected2, _ = generate_llm_candidates(n=1, adapter=_FakeLLMAdapter(payload), repository=repo)
        assert len(accepted2) == 0 and len(rejected2) == 3

    # LLM 未配置 → 明确报错,不静默降级
    class _Null:
        model = ""

        def available(self):
            return False

    try:
        generate_llm_candidates(n=1, adapter=_Null())
        raise AssertionError("unavailable adapter must raise")
    except ValueError as e:
        assert "LLM" in str(e)


def test_island_search_mutation_stays_in_whitelist_and_search_is_deterministic():
    import random as _random

    from factory.autoresearch.islands import crossover_ast, mutate_ast, run_island_search
    from factory.lines.line2_validation.l0_ic_scan import precompute_forward_returns

    # 变异/杂交模糊测试:50 轮全部仍在白名单内
    rng = _random.Random(11)
    asts = [c.ast for c in generate_seed_candidates(limit=4)]
    for _ in range(50):
        validate_candidate_ast(mutate_ast(rng.choice(asts), rng))
        validate_candidate_ast(crossover_ast(asts[0], asts[1], rng))

    close, volume, amount = _synthetic_panel()
    forward_ret = precompute_forward_returns(close)

    def _run(root):
        return run_island_search(
            close, volume, amount, forward_ret,
            vintage_id="synthetic",
            n_islands=2, generations=2, population=4, top_k=3, rng_seed=7,
            repository=CandidateRepository(root / "candidates.jsonl"),
            experiment_log=ExperimentLog(root / "experiment_log.jsonl"),
            review_queue=ReviewQueue(root / "review_queue.jsonl"),
        )

    with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
        r1 = _run(Path(td1))
        r2 = _run(Path(td2))
        assert r1.evaluated > 0
        assert len(r1.champions) == 3
        assert all(c.icir != 0.0 or c.status for c in r1.champions)
        # 同 seed + 同数据 → 同冠军(实验可复现)
        assert [c.fingerprint for c in r1.champions] == [c.fingerprint for c in r2.champions]
        assert r1.champions[0].icir == max(c.icir for c in r1.champions) or abs(r1.champions[0].icir) >= abs(r1.champions[-1].icir)


def test_read_views_expose_candidates_and_review_queue():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        repo = CandidateRepository(root / "candidates.jsonl")
        review = ReviewQueue(root / "review_queue.jsonl")
        candidate = validate_candidate_ast(_candidate())
        evaluate_lite(
            candidate,
            l0_metrics={
                "rank_ic_mean": 0.035,
                "icir": 0.55,
                "coverage": 0.91,
                "nan_ratio": 0.02,
                "extreme_ratio": 0.01,
            },
            l1_metrics={
                "monotonic_groups": True,
                "top_bottom_return": 0.08,
                "cost_after_return": 0.05,
                "turnover": 0.8,
            },
            redundancy_inputs={
                "spearman_corr": 0.15,
                "normalized_mi": 0.2,
                "holding_overlap": 0.1,
                "return_corr": 0.1,
                "exposure_similarity": 0.2,
            },
            repository=repo,
            review_queue=review,
        )

        candidates = autoresearch_candidates(path=root / "candidates.jsonl")
        queue = autoresearch_review_queue(path=root / "review_queue.jsonl")
        funnel = autoresearch_funnel(
            candidate_path=root / "candidates.jsonl",
            review_path=root / "review_queue.jsonl",
        )

        assert len(candidates) == 1
        assert candidates[0].status == "promoted_to_review"
        assert candidates[0].ast["type"] == "linear_combo"
        assert candidates[0].complexity_score > 0
        assert len(queue) == 1
        assert funnel.review_queue == 1
        assert any(s["stage"] == "promoted_to_review" and s["count"] == 1 for s in funnel.stages)


if __name__ == "__main__":
    test_json_ast_validation_rejects_free_string_and_unknown_ops()
    test_neutralize_declaration_rejected_until_runtime_supports_it()
    test_fingerprint_is_stable_and_repository_dedupes()
    test_candidate_generator_produces_unique_valid_ast_batch()
    test_ast_to_hypothesis_uses_controlled_runtime_factor()
    test_dsl_runtime_factor_computes_linear_combo_panel()
    test_complexity_budget_blocks_overfit_candidates()
    test_leakage_guard_blocks_future_and_label_fields()
    test_redundancy_score_combines_multiple_similarity_inputs()
    test_lite_engine_logs_discard_shelve_and_promote_without_registry_write()
    test_experiment_log_roundtrips_decision_enum()
    test_validation_pipeline_runs_l0_to_l3_and_promotes_only_after_l3()
    test_real_runners_accept_autoresearch_hypothesis_contract()
    test_validation_pipeline_executes_real_l0_on_synthetic_panel()
    test_run_autoresearch_seeds_action_uses_pipeline_contract()
    test_human_review_approve_reject_without_registry_write()
    test_promote_approved_candidate_gates_and_calls_workflow_promote()
    test_llm_generation_validates_rejects_and_dedupes()
    test_island_search_mutation_stays_in_whitelist_and_search_is_deterministic()
    test_read_views_expose_candidates_and_review_queue()
    print("✅ Auto Factor Research Engine tests passed")
