"""Market-liquidity HMM stress guard for the small-cap strategy.

This follows the "HMM Stress Guard" idea: infer hidden market stress states
from observable broad-market environment features, then block buys/sell out
when stress probability is above a threshold.

Research-only script. It reads data_lake/core helpers and writes artifacts
under reports/research. It does not change production signals or schedulers.

Usage:
  /usr/bin/python3 -m scripts.research.hmm_stress_guard_smallcap
"""
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from core.backtest import StrategyConfig, backtest_weights, metrics, run_small_cap_strategy  # noqa: E402
from scripts.research.hmm_exit_smallcap import ConstrainedGaussianHMM, row_for, standardize  # noqa: E402


OUT_DIR = ROOT / "reports" / "research"
OUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class StressGuardConfig:
    lookback: int = 1260
    retrain_days: int = 60
    threshold: float = 0.15
    max_iter: int = 35
    mode: str = "binary"
    stress_floor: float = 0.0


def build_market_features(close, amount):
    px = close
    ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    active = amount.gt(0) & close.notna()

    ma20 = px.rolling(20).mean()
    valid_ma20 = ma20.notna()
    ma_diffusion = (px.gt(ma20) & valid_ma20).sum(axis=1) / valid_ma20.sum(axis=1).replace(0, np.nan)
    ma_diffusion = ma_diffusion.fillna(0.5).round(4)

    up_ratio = (px.gt(px.shift(1)) & active).sum(axis=1) / active.sum(axis=1).replace(0, np.nan)
    risk_appetite = up_ratio.fillna(0.5)

    market_amount = amount.sum(axis=1, min_count=1)
    liquidity = (market_amount / market_amount.rolling(20).mean()).replace([np.inf, -np.inf], np.nan).fillna(1.0)

    market_ret = ret.where(active).mean(axis=1)
    volatility = market_ret.rolling(20).std().fillna(0.0).round(6)

    out = pd.DataFrame(index=close.index)
    out["risk_appetite"] = risk_appetite
    out["volatility"] = volatility
    out["liquidity"] = liquidity
    out["ma_diffusion"] = ma_diffusion
    return out.replace([np.inf, -np.inf], np.nan).dropna()


def stress_score_from_train(features, post):
    labels = post.argmax(axis=1)
    scores = []
    for state in range(post.shape[1]):
        mask = labels == state
        if not mask.any():
            scores.append(-np.inf)
            continue
        f = features.iloc[mask]
        score = (
            -float(f["risk_appetite"].mean())
            + float(f["volatility"].mean())
            - float(f["liquidity"].mean())
            - float(f["ma_diffusion"].mean())
        )
        scores.append(score)
    return int(np.argmax(scores)), scores


def hmm_stress_probability(features, cfg):
    dates = features.index
    prob = pd.Series(np.nan, index=dates, dtype="float64")
    state_trace = pd.Series(np.nan, index=dates, dtype="float64")
    stress_state_trace = pd.Series(np.nan, index=dates, dtype="float64")
    refit_dates = list(dates[cfg.lookback :: cfg.retrain_days])

    for pos, refit_date in enumerate(refit_dates):
        train_end = dates.get_loc(refit_date)
        train = features.iloc[train_end - cfg.lookback : train_end]
        if pos + 1 < len(refit_dates):
            next_pos = dates.get_loc(refit_dates[pos + 1])
        else:
            next_pos = len(dates)
        block = features.iloc[train_end:next_pos]
        if len(train) < cfg.lookback or block.empty:
            continue

        train_x = standardize(train, train).values
        block_x = standardize(train, pd.concat([train.tail(1), block])).values
        try:
            model = ConstrainedGaussianHMM(max_iter=cfg.max_iter).fit(train_x)
            train_post = model.filter_posteriors(train_x)
            train_std = pd.DataFrame(train_x, index=train.index, columns=train.columns)
            stress_state, _ = stress_score_from_train(train_std, train_post)
            post = model.filter_posteriors(block_x)[1:]
            block_prob = post[:, stress_state]
        except FloatingPointError:
            post = np.zeros((len(block), 3), dtype="float64")
            block_prob = np.zeros(len(block), dtype="float64")
            stress_state = np.nan

        prob.loc[block.index] = block_prob
        state_trace.loc[block.index] = post.argmax(axis=1)
        stress_state_trace.loc[block.index] = stress_state

    # T close features can only affect T+1 exposure.
    return prob.shift(1), state_trace.shift(1), stress_state_trace.shift(1)


def guard_exposure(prob, cfg):
    if cfg.mode == "binary":
        return (prob.fillna(1.0) <= cfg.threshold).astype(float)
    if cfg.mode == "floor":
        return pd.Series(np.where(prob.fillna(1.0) > cfg.threshold, cfg.stress_floor, 1.0), index=prob.index)
    raise ValueError(f"unknown mode: {cfg.mode}")


def fmt(row):
    return (
        f"2018年化{row['annual_2018']:+.1%} 回撤{row['maxdd_2018']:+.1%} "
        f"夏普{row['sharpe_2018']:.2f} 卡玛{row['calmar_2018']:.2f} | "
        f"2023年化{row['annual_2023']:+.1%} 回撤{row['maxdd_2023']:+.1%} | "
        f"2010年化{row['annual_2010']:+.1%} 回撤{row['maxdd_2010']:+.1%}"
    )


def main():
    cfg0 = StrategyConfig(start="2010-01-01")
    print("Loading baseline small-cap strategy...", flush=True)
    base = run_small_cap_strategy(cfg0)
    close, amount = base["close"], base["amount"]
    scheduled = base["scheduled_weights"]
    baseline_ret = base["returns"]
    smallcap_timing = base["timing"].astype(float).reindex(close.index).fillna(0.0)

    print("Building market stress features...", flush=True)
    features = build_market_features(close, amount)

    model_cfgs = [
        StressGuardConfig(lookback=756, retrain_days=60, threshold=0.15),
        StressGuardConfig(lookback=1008, retrain_days=60, threshold=0.15),
        StressGuardConfig(lookback=1260, retrain_days=60, threshold=0.15),
    ]
    threshold_grid = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40]
    floor_grid = [0.0, 0.3, 0.5, 0.7]

    rows = [row_for("v2.0 baseline", baseline_ret, baseline_ret)]
    daily_frames = []
    for model_cfg in model_cfgs:
        print(f"Training HMM stress model {model_cfg}", flush=True)
        prob, state, stress_state = hmm_stress_probability(features, model_cfg)
        prob = prob.reindex(close.index)
        for threshold in threshold_grid:
            for mode, floor in [("binary", 0.0)] + [("floor", x) for x in floor_grid if x > 0]:
                cfg = StressGuardConfig(
                    lookback=model_cfg.lookback,
                    retrain_days=model_cfg.retrain_days,
                    threshold=threshold,
                    max_iter=model_cfg.max_iter,
                    mode=mode,
                    stress_floor=floor,
                )
                exposure = guard_exposure(prob, cfg).reindex(close.index).fillna(0.0)
                timing = smallcap_timing * exposure
                ret, _ = backtest_weights(close, scheduled, timing, cfg0)
                label = (
                    f"hmm_stress {mode} lb{cfg.lookback} rt{cfg.retrain_days} "
                    f"th{threshold:.2f} floor{floor:.1f}"
                )
                active_2018 = timing[timing.index.year >= 2018]
                rows.append(
                    row_for(
                        label,
                        ret,
                        baseline_ret,
                        {
                            **asdict(cfg),
                            "stress_prob_mean_2018": float(prob[prob.index.year >= 2018].mean()),
                            "stress_prob_p90_2018": float(prob[prob.index.year >= 2018].quantile(0.90)),
                            "guard_exposure_2018": float(exposure[exposure.index.year >= 2018].mean()),
                            "timing_on_rate_2018": float(active_2018.mean()),
                        },
                    )
                )
                daily_frames.append(
                    pd.DataFrame(
                        {
                            "date": close.index,
                            "prob_stress": prob.reindex(close.index).values,
                            "state": state.reindex(close.index).values,
                            "stress_state": stress_state.reindex(close.index).values,
                            "guard_exposure": exposure.values,
                            "combined_timing": timing.values,
                            "ret": ret.reindex(close.index).values,
                            "label": label,
                        }
                    )
                )

    result = pd.DataFrame(rows)
    variants = result[result["label"] != "v2.0 baseline"].copy()
    variants["objective"] = (
        0.5 * variants["sharpe_2018"]
        + 0.5 * variants["calmar_2018"]
    ) * np.minimum(variants["annual_2018"] / 0.20, 1.0)
    result = pd.concat([result[result["label"] == "v2.0 baseline"], variants], ignore_index=True)
    result = result.sort_values(["objective", "sharpe_2018", "annual_2018"], ascending=[False, False, False], na_position="last")

    result_path = OUT_DIR / "hmm_stress_guard_smallcap_results.csv"
    daily_path = OUT_DIR / "hmm_stress_guard_smallcap_daily.csv"
    summary_path = OUT_DIR / "hmm_stress_guard_smallcap_summary.json"
    result.to_csv(result_path, index=False)
    pd.concat(daily_frames, ignore_index=True).to_csv(daily_path, index=False)

    variants = result[result["label"] != "v2.0 baseline"].copy()
    summary = {
        "baseline": rows[0],
        "best_by_objective": variants.iloc[0].to_dict(),
        "best_by_sharpe_2018": variants.sort_values(["sharpe_2018", "annual_2018"], ascending=[False, False]).iloc[0].to_dict(),
        "best_by_calmar_2018": variants.sort_values(["calmar_2018", "annual_2018"], ascending=[False, False]).iloc[0].to_dict(),
        "notes": [
            "Stress features: risk_appetite, volatility, liquidity, ma_diffusion.",
            "Stress probability is shifted one trading day before exposure changes.",
            "Research-only script; no production files changed.",
        ],
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n=== HMM Stress Guard results ===", flush=True)
    for _, row in result.head(14).iterrows():
        print(f"{row['label']:<48} {fmt(row)}", flush=True)
    print(f"\nWrote: {result_path}", flush=True)
    print(f"Wrote: {daily_path}", flush=True)
    print(f"Wrote: {summary_path}", flush=True)


if __name__ == "__main__":
    main()
