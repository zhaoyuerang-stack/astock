"""Niche labels and review gates for factory candidates."""


SIZE_FACTORS = {"size20", "size40", "size60"}


def factor_names(row):
    config = row.get("config", {})
    return list(config.get("factors", []))


def size_exposure(row):
    factors = factor_names(row)
    if not factors:
        return 0.0
    return sum(1 for factor in factors if factor in SIZE_FACTORS) / len(factors)


def niche_label(row):
    factors = factor_names(row)
    families = row.get("family", "")
    if not factors:
        return "unknown"
    exposure = size_exposure(row)
    if exposure == 1:
        return "pure-size"
    if exposure > 0:
        return "size-blend"
    if "reversal" in families or any("reversal" in factor for factor in factors):
        return "non-size-reversal"
    if "liquidity" in families or any("turnover" in factor for factor in factors):
        return "non-size-liquidity"
    if "low-vol" in families or any("vol" in factor for factor in factors):
        return "non-size-quality"
    if "price-location" in families or any("price_below" in factor for factor in factors):
        return "non-size-location"
    return "non-size-other"


def review_candidate(row, max_corr=0.90):
    """Gate rows worth human follow-up before registry entry.

    This is intentionally looser than the final strategy registry threshold:
    phase 1.4 wants a shortlist for deeper validation, not automatic admission.
    """
    if not row.get("front_eligible") or not row.get("pareto"):
        return False
    corr = row.get("corr_to_baseline")
    oos = row.get("oos_annual")
    if size_exposure(row) >= 1:
        return False
    if corr is not None and corr > max_corr:
        return False
    if oos is not None and oos < 0:
        return False
    return row.get("annual", 0) > 0.05 and row.get("maxdd", -1) > -0.35


def annotate_niches(rows, max_corr=0.90):
    out = []
    for row in rows:
        copied = dict(row)
        copied["size_exposure"] = size_exposure(row)
        copied["niche"] = niche_label(row)
        copied["review_candidate"] = review_candidate(copied, max_corr=max_corr)
        out.append(copied)
    return out
