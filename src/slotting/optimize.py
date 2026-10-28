"""Slotting: affinity clustering, then an integer program that assigns clusters to bays.

A full SKU-to-slot model with co-pick terms is quadratic and far too large
for 2,000 SKUs. The problem is decomposed instead:

1. Greedy affinity clustering groups SKUs that are often picked together into
   clusters of one bay's capacity.
2. A PuLP assignment IP places clusters in bays to minimise
   sum(cluster picks x bay slot cost), with a cap on the share of picks any
   one aisle may take so fast movers do not jam a single aisle.
3. Inside each bay, the fastest SKUs take golden-zone levels.
"""

from __future__ import annotations

import pandas as pd
import pulp


def affinity_clusters(velocity: pd.DataFrame, affinity: pd.DataFrame,
                      cluster_size: int) -> pd.DataFrame:
    """Seed each cluster with the fastest unassigned SKU, then pull in its strongest partners."""
    partners: dict[int, list[int]] = {}
    for a, b in affinity.sort_values("lift", ascending=False)[["sku_a", "sku_b"]].itertuples(index=False):
        partners.setdefault(a, []).append(b)
        partners.setdefault(b, []).append(a)

    unassigned = list(velocity["sku"])  # fastest first
    remaining = set(unassigned)
    cluster_of: dict[int, int] = {}
    cid = 0
    for seed in unassigned:
        if seed not in remaining:
            continue
        members = [seed]
        remaining.discard(seed)
        frontier = list(partners.get(seed, []))
        while frontier and len(members) < cluster_size:
            sku = frontier.pop(0)
            if sku in remaining:
                members.append(sku)
                remaining.discard(sku)
                frontier.extend(partners.get(sku, []))
        # Top up with the next fastest SKUs so clusters fill whole bays
        for sku in unassigned:
            if len(members) >= cluster_size:
                break
            if sku in remaining:
                members.append(sku)
                remaining.discard(sku)
        for sku in members:
            cluster_of[sku] = cid
        cid += 1

    out = velocity.copy()
    out["cluster"] = out["sku"].map(cluster_of)
    return out


def assign_clusters_to_bays(clustered: pd.DataFrame, bays: pd.DataFrame,
                            max_aisle_pick_share: float = 1.0,
                            time_limit_s: int = 60) -> dict[int, int]:
    """Assignment IP: each cluster gets exactly one bay, each bay at most one cluster."""
    picks = clustered.groupby("cluster")["picks"].sum()
    if len(picks) > len(bays):
        raise ValueError(f"{len(picks)} clusters but only {len(bays)} bays; enlarge the layout")

    prob = pulp.LpProblem("slotting", pulp.LpMinimize)
    x = {(c, b): prob.add_variable(f"x_{c}_{b}", cat="Binary")
         for c in picks.index for b in bays["bay_id"]}
    cost = bays.set_index("bay_id")["slot_cost"]
    prob += pulp.lpSum(picks[c] * cost[b] * var for (c, b), var in x.items())
    for c in picks.index:
        prob += pulp.lpSum(x[c, b] for b in bays["bay_id"]) == 1
    for b in bays["bay_id"]:
        prob += pulp.lpSum(x[c, b] for c in picks.index) <= 1
    # Congestion cap: no aisle carries more than its share of total picks. The
    # cap can never be below an even split, or the model would be infeasible.
    n_aisles = bays["aisle"].nunique()
    cap = max(max_aisle_pick_share, 1.5 / n_aisles) * picks.sum()
    for _, aisle_bays in bays.groupby("aisle")["bay_id"]:
        prob += pulp.lpSum(picks[c] * x[c, b] for c in picks.index for b in aisle_bays) <= cap

    stats = prob.solve(pulp.HiGHS(msg=False, timeLimit=time_limit_s))
    if not stats.has_solution:
        raise RuntimeError(f"slotting IP found no solution: {stats.status.name}")
    return {c: b for (c, b), var in x.items() if var.value() and var.value() > 0.5}


def slot_skus(clustered: pd.DataFrame, cluster_bay: dict[int, int],
              slots: pd.DataFrame) -> pd.DataFrame:
    """Within each bay, give golden-zone slots to the fastest SKUs."""
    out = []
    for cluster, bay_id in cluster_bay.items():
        skus = clustered[clustered["cluster"] == cluster].sort_values("picks", ascending=False)
        bay_slots = slots[slots["bay_id"] == bay_id].sort_values(["golden", "level"],
                                                                 ascending=[False, True])
        n = min(len(skus), len(bay_slots))
        placed = bay_slots.iloc[:n].copy()
        placed["sku"] = skus["sku"].iloc[:n].to_numpy()
        out.append(placed)
    return pd.concat(out, ignore_index=True)


def category_baseline(velocity: pd.DataFrame, slots: pd.DataFrame) -> pd.DataFrame:
    """The usual store layout: SKUs grouped by department, walked aisle by aisle."""
    ordered = velocity.sort_values(["department", "sku"])
    order_slots = slots.sort_values(["aisle", "bay", "side", "level", "slot"])
    n = min(len(ordered), len(order_slots))
    placed = order_slots.iloc[:n].copy()
    placed["sku"] = ordered["sku"].iloc[:n].to_numpy()
    return placed
