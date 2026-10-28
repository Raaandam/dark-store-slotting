"""SKU velocity, ABC classes and pairwise co-pick affinity."""

from __future__ import annotations

from collections import Counter
from itertools import combinations

import pandas as pd


def sku_velocity(lines: pd.DataFrame) -> pd.DataFrame:
    """Picks per SKU with cumulative share, sorted fastest first."""
    v = lines.groupby("sku").agg(picks=("order_id", "size"),
                                 department=("department", "first")).reset_index()
    v = v.sort_values("picks", ascending=False).reset_index(drop=True)
    v["share"] = v["picks"] / v["picks"].sum()
    v["cum_share"] = v["share"].cumsum()
    return v


def abc_classes(velocity: pd.DataFrame, a_share: float = 0.80,
                b_share: float = 0.95) -> pd.DataFrame:
    """Pareto split on cumulative pick share.

    A SKU's class is set by the share *before* it, so the SKU that crosses
    a threshold stays in the higher class.
    """
    out = velocity.copy()
    start = out["cum_share"] - out["share"]
    out["abc"] = "C"
    out.loc[start < b_share, "abc"] = "B"
    out.loc[start < a_share, "abc"] = "A"
    return out


def co_pick_affinity(lines: pd.DataFrame, min_support: int = 50) -> pd.DataFrame:
    """Count how often each SKU pair appears in the same order.

    Lift = P(a,b) / (P(a) P(b)) separates real affinity from two SKUs
    that are simply both popular.
    """
    n_orders = lines["order_id"].nunique()
    sku_orders = lines.groupby("sku")["order_id"].nunique()
    pairs: Counter = Counter()
    for skus in lines.groupby("order_id")["sku"].apply(lambda s: sorted(set(s))):
        pairs.update(combinations(skus, 2))

    rows = [(a, b, c) for (a, b), c in pairs.items() if c >= min_support]
    aff = pd.DataFrame(rows, columns=["sku_a", "sku_b", "co_picks"])
    if aff.empty:
        aff["lift"] = []
        return aff
    aff["lift"] = (aff["co_picks"] * n_orders
                   / (aff["sku_a"].map(sku_orders) * aff["sku_b"].map(sku_orders)))
    return aff.sort_values("co_picks", ascending=False).reset_index(drop=True)
