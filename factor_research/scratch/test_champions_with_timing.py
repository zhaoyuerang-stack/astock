"""Script to test and audit the 3 discarded champions with the Moving Average timing overlay."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import numpy as np

from factory.autoresearch import CandidateRepository, ast_to_hypothesis
from factory.lines.line2_validation.l1_quick_bt import _resolve_factor_fn, _dispatch_args
from strategies.small_cap import build_rebalance_weights
from core.overlays.moving_average_overlay import MovingAverageOverlay
from core.engine import BacktestConfig, BacktestEngine, CostModel, PricePanel, Signal
from services.actions.autoresearch import _load_validation_data


def test_champions_with_timing():
    print("=" * 80)
    print("  Auditing Discarded Champions with Moving Average Timing Overlay")
    print("=" * 80)

    # 1. Load data
    print("Loading data panels...")
    close, volume, amount, forward_ret = _load_validation_data("2018-01-01")

    # 2. Retrieve targeted candidates
    repository = CandidateRepository()
    targets = ["c74f2761f262230a", "1ed6fb13a9b58e5c", "b296d1a83d7244eb"]
    candidates = []
    for c in repository.all():
        for t in targets:
            if c.fingerprint.startswith(t):
                candidates.append(c)
                break

    if not candidates:
        print("Error: Targeted candidates not found in CandidateRepository.")
        return

    print(f"Found {len(candidates)} candidates to audit.")

    # 3. Instantiate timing overlay (MA16)
    overlay = MovingAverageOverlay(ma_window=16)
    print("Generating MA16 defensive timing exposure series...")
    timing_exposure = overlay.exposure_series(close, amount)

    # 4. Evaluate each candidate with and without timing
    for idx, cand in enumerate(candidates):
        print(f"\n[Candidate {idx+1}] Fingerprint: {cand.fingerprint[:12]}")
        print(f"Formula: {cand.ast}")

        # Resolve factor
        hyp = ast_to_hypothesis(cand)
        fn = _resolve_factor_fn(hyp.factor_fn_name)
        args = _dispatch_args(hyp.data_dependencies, close, volume, amount)

        # 4.1 Measure time to calculate factor panel once (optimized check)
        t_calc0 = time.time()
        factor = fn(*args, **hyp.factor_params)
        t_calc = time.time() - t_calc0
        print(f"  Factor panel calculated in: {t_calc:.2f} seconds (Cached/shared panel is now ready).")

        # 4.2 Run UNTIMED backtest (Base)
        print("  Running UNTIMED backtest (2018-01-01 to latest)...")
        # Invert weights if direction is negative
        dir_val = -1 if cand.ast.get("direction") == "negative" else 1
        
        # Build rebalance weights
        rebal_weights = build_rebalance_weights(
            factor=factor * dir_val,
            close=close,
            top_n=25,
            rebalance_days=20,
        )
        
        prices = PricePanel(close=close, volume=volume, amount=amount)
        cfg = BacktestConfig(start="2018-01-01", cost=CostModel(), leverage=1.0)
        
        # Base Engine
        engine_base = BacktestEngine(prices=prices, config=cfg)
        sig_base = Signal(weights=rebal_weights, family="base_untimed", version=cand.fingerprint[:8])
        res_base = engine_base.run(sig_base)
        
        # 4.3 Run TIMED backtest
        print("  Running TIMED backtest (with MA16 defensive timing)...")
        engine_timed = BacktestEngine(prices=prices, config=cfg)
        sig_timed = Signal(weights=rebal_weights, timing=timing_exposure, family="timed", version=cand.fingerprint[:8])
        res_timed = engine_timed.run(sig_timed)

        # 4.4 Report metrics comparison
        ann_base = res_base.returns.mean() * 252
        vol_base = res_base.returns.std() * np.sqrt(252)
        sr_base = ann_base / vol_base if vol_base > 0 else 0.0
        cum_base = (1.0 + res_base.returns).cumprod()
        dd_base = (cum_base / cum_base.cummax() - 1.0).min()

        ann_timed = res_timed.returns.mean() * 252
        vol_timed = res_timed.returns.std() * np.sqrt(252)
        sr_timed = ann_timed / vol_timed if vol_timed > 0 else 0.0
        cum_timed = (1.0 + res_timed.returns).cumprod()
        dd_timed = (cum_timed / cum_timed.cummax() - 1.0).min()

        print("  Comparison Results:")
        print(f"    - Base (Untimed): Annual Return = {ann_base:.2%}, Sharpe = {sr_base:.2f}, MaxDD = {dd_base:.2%}")
        print(f"    - Timed (MA16):   Annual Return = {ann_timed:.2%}, Sharpe = {sr_timed:.2f}, MaxDD = {dd_timed:.2%}")
        
        dd_saved = dd_base - dd_timed
        print(f"    - Drawdown Protection: Timing reduced Max Drawdown by: {dd_saved:.2%}")
        if abs(dd_timed) < 0.30:
            print("    🟢 SUCCESS: Timed version successfully pulls drawdown under the 30% safety limit!")
        else:
            print("    🔴 WARNING: Drawdown is still above 30%, might need tighter timing window.")


if __name__ == "__main__":
    test_champions_with_timing()
