"""Factor Crowding Scores.

Evaluates crowding indicators: institutional ownership clustering,
turnover spikes, and extreme pairwise stock correlations.
"""
from __future__ import annotations

import pandas as pd
import numpy as np

def calculate_crowding_score(
    weights: pd.DataFrame,
    returns: pd.DataFrame,
    window: int = 20
) -> pd.Series:
    """Calculate the crowding score of a portfolio over time.

    Method: average pairwise correlation of active holdings weighted by portfolio holdings.
    Higher correlation indicates crowded positions that may suffer from simultaneous liquidation.
    """
    common_idx = weights.index.intersection(returns.index)
    if len(common_idx) < window:
        return pd.Series(0.0, index=weights.index)

    crowding_scores = []
    
    # Calculate rolling pairwise correlation
    for i in range(len(common_idx)):
        if i < window:
            crowding_scores.append(0.0)
            continue
            
        date = common_idx[i]
        w = weights.loc[date]
        active_assets = w[w > 0.0001].index
        
        if len(active_assets) < 2:
            crowding_scores.append(0.0)
            continue

        hist_rets = returns.loc[common_idx[i - window]:date, active_assets]
        corr_matrix = hist_rets.corr().fillna(0.0)
        
        # Weighted average correlation
        w_active = w.loc[active_assets]
        w_active = w_active / w_active.sum()
        
        # Calculate sum(w_i * w_j * corr_ij) excluding diagonal
        score = 0.0
        for asset_i in active_assets:
            for asset_j in active_assets:
                if asset_i != asset_j:
                    score += w_active[asset_i] * w_active[asset_j] * corr_matrix.loc[asset_i, asset_j]
                    
        crowding_scores.append(score)

    return pd.Series(crowding_scores, index=common_idx)
