"""Algorithm Order Router.

Splits orders over time using execution algorithms like TWAP and VWAP.
"""
from __future__ import annotations

import numpy as np
from typing import Dict, List, Any

class AlgoRouter:
    def __init__(self, mode: str = "TWAP"):
        self.mode = mode # TWAP | VWAP

    def generate_slices(
        self,
        symbol: str,
        total_volume: int,
        intervals: int = 6,
        volume_profile: Optional[np.ndarray] = None
    ) -> List[Dict[str, Any]]:
        """Slice the order into sub-orders to manage market impact."""
        slices = []
        if total_volume <= 0:
            return slices

        if self.mode == "TWAP":
            # Equal volume slices
            slice_vol = total_volume // intervals
            remainder = total_volume % intervals
            for i in range(intervals):
                vol = slice_vol + (1 if i < remainder else 0)
                if vol > 0:
                    slices.append({
                        "symbol": symbol,
                        "slice_index": i,
                        "volume": vol,
                        "delay_seconds": i * 600 # 10 mins apart
                    })
        elif self.mode == "VWAP":
            # Volume profile based slices
            if volume_profile is None or len(volume_profile) != intervals:
                volume_profile = np.ones(intervals) / intervals
            else:
                volume_profile = volume_profile / np.sum(volume_profile)
                
            accumulated = 0
            for i in range(intervals):
                vol = int(total_volume * volume_profile[i])
                accumulated += vol
                if i == intervals - 1:
                    vol += (total_volume - accumulated)
                if vol > 0:
                    slices.append({
                        "symbol": symbol,
                        "slice_index": i,
                        "volume": vol,
                        "delay_seconds": i * 600
                    })
        return slices
