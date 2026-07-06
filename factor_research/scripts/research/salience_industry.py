"""Point-in-time industry helpers for Salience research scripts."""
from __future__ import annotations

import pandas as pd

from lake.load_lake import load_fundamental_panel


def build_avail_date_industry_panel(
    close: pd.DataFrame,
    *,
    default: str = "Unknown",
) -> pd.DataFrame:
    """Return date x code industry labels aligned by fundamental avail_date."""
    panels = load_fundamental_panel(
        close.index,
        codes=list(close.columns),
        fields=["industry"],
    )
    industry = panels.get("industry", pd.DataFrame())
    if industry.empty:
        return pd.DataFrame(default, index=close.index, columns=close.columns)
    aligned = industry.reindex(index=close.index, columns=close.columns)
    return aligned.astype(object).where(aligned.notna(), default)
