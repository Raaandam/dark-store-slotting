"""Replay held-out orders against a slotting plan and compute picking KPIs."""

from __future__ import annotations

import pandas as pd

from .layout import Layout
from .routing import ROUTERS


def replay(orders: pd.DataFrame, plan: pd.DataFrame, layout: Layout,
           routing: str, picking: dict) -> pd.DataFrame:
    """One row per order: lines, walk distance (m) and pick time (s).

    Lines for SKUs that are not slotted are dropped, since they would be
    picked from overflow storage and are outside this study.
    """
    where = plan.set_index("sku")[["aisle", "y"]]
    lines = orders[["order_id", "sku"]].merge(where, left_on="sku", right_index=True)
    router = ROUTERS[routing]
    rows = []
    for order_id, grp in lines.groupby("order_id"):
        picks = grp.groupby("aisle")["y"].apply(list).to_dict()
        dist = router(layout, picks)
        secs = (dist / picking["walk_speed_mps"]
                + len(grp) * picking["seconds_per_line"]
                + picking["seconds_per_order"])
        rows.append((order_id, len(grp), dist, secs))
    return pd.DataFrame(rows, columns=["order_id", "lines", "walk_m", "pick_s"])


def summarise(results: pd.DataFrame) -> dict:
    hours = results["pick_s"].sum() / 3600
    return {
        "orders": int(len(results)),
        "mean_walk_m": float(results["walk_m"].mean()),
        "mean_pick_s": float(results["pick_s"].mean()),
        "lines_per_hour": float(results["lines"].sum() / hours) if hours else 0.0,
        "orders_per_hour": float(len(results) / hours) if hours else 0.0,
    }


def zone_congestion(orders: pd.DataFrame, plan: pd.DataFrame) -> pd.DataFrame:
    """Share of all picks landing in each aisle; a hot aisle means pickers queue."""
    hits = orders[["sku"]].merge(plan[["sku", "aisle"]], on="sku").groupby("aisle").size()
    return (hits / hits.sum()).rename("pick_share").reset_index()
