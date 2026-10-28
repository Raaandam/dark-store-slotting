"""CLI entry point: load orders, build both layouts, replay held-out orders, export KPIs.

    python -m slotting.pipeline --config configs/config.yaml
    python -m slotting.pipeline --synthetic 5000 --output-dir reports/synthetic_smoke
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import yaml

from . import data, optimize, synthetic, velocity
from .evaluate import replay, summarise, zone_congestion
from .layout import Layout


def run(cfg: dict, lines, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "kpis").mkdir(exist_ok=True)

    train, test = data.split_orders(lines, cfg["data"]["holdout_fraction"], cfg["data"]["seed"])
    vel = velocity.abc_classes(velocity.sku_velocity(train), **cfg["abc"])
    aff = velocity.co_pick_affinity(train, cfg["slotting"]["affinity_min_support"])

    # Size the store to the range: a dark store is full, so both layouts must
    # use the same number of aisles or the comparison flatters the smaller one
    lay = dict(cfg["layout"])
    per_aisle = 2 * lay["bays_per_side"] * len(lay["levels"]) * lay["slots_per_level"]
    lay["aisles"] = min(lay["aisles"], math.ceil(len(vel) / per_aisle))
    layout = Layout.from_config(lay)
    bays, slots = layout.bays(), layout.slots()

    bay_capacity = int(bays["capacity"].iloc[0])
    clustered = optimize.affinity_clusters(vel, aff, bay_capacity)
    cluster_bay = optimize.assign_clusters_to_bays(clustered, bays,
                                                   cfg["slotting"]["max_aisle_pick_share"],
                                                   cfg["slotting"]["solver_time_limit_s"])
    plans = {
        "baseline": optimize.category_baseline(vel, slots),
        "optimised": optimize.slot_skus(clustered, cluster_bay, slots),
    }

    metrics: dict = {"skus": int(len(vel)), "aisles": layout.aisles,
                     "affinity_pairs": int(len(aff)),
                     "abc_counts": vel["abc"].value_counts().to_dict()}
    for name, plan in plans.items():
        plan.to_csv(output_dir / "kpis" / f"slotting_plan_{name}.csv", index=False)
        zone_congestion(test, plan).to_csv(output_dir / "kpis" / f"zone_congestion_{name}.csv",
                                           index=False)
        for routing in cfg["picking"]["routing"]:
            res = replay(test, plan, layout, routing, cfg["picking"])
            res.to_csv(output_dir / "kpis" / f"orders_{name}_{routing}.csv", index=False)
            metrics[f"{name}/{routing}"] = summarise(res)

    for routing in cfg["picking"]["routing"]:
        base, opt = metrics[f"baseline/{routing}"], metrics[f"optimised/{routing}"]
        metrics[f"improvement/{routing}"] = {
            "walk_reduction_pct": 100 * (1 - opt["mean_walk_m"] / base["mean_walk_m"]),
            "pick_time_reduction_pct": 100 * (1 - opt["mean_pick_s"] / base["mean_pick_s"]),
        }

    vel.to_csv(output_dir / "kpis" / "sku_velocity_abc.csv", index=False)
    aff.head(500).to_csv(output_dir / "kpis" / "top_affinity_pairs.csv", index=False)
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    return metrics


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/config.yaml")
    ap.add_argument("--synthetic", type=int, default=0,
                    help="run on N synthetic orders instead of the Instacart files")
    ap.add_argument("--output-dir", default="reports")
    args = ap.parse_args(argv)

    cfg = yaml.safe_load(Path(args.config).read_text())
    if args.synthetic:
        lines = synthetic.make_order_lines(n_orders=args.synthetic, seed=cfg["data"]["seed"])
        cfg["slotting"]["affinity_min_support"] = 5
    else:
        d = cfg["data"]
        lines = data.load_instacart(d["orders"], d["order_products"], d["products"],
                                    d["max_orders"])
    lines = data.restrict_to_top_skus(lines, cfg["data"]["top_n_skus"])

    metrics = run(cfg, lines, Path(args.output_dir))
    for routing in cfg["picking"]["routing"]:
        imp = metrics[f"improvement/{routing}"]
        print(f"{routing:12s} walk reduction {imp['walk_reduction_pct']:.1f}%  "
              f"pick-time reduction {imp['pick_time_reduction_pct']:.1f}%")


if __name__ == "__main__":
    main()
