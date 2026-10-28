import pandas as pd
import pytest
import yaml

from slotting import optimize, velocity
from slotting.layout import Layout
from slotting.pipeline import run
from slotting.routing import largest_gap, s_shape
from slotting.synthetic import make_order_lines


@pytest.fixture
def cfg():
    with open("configs/config.yaml") as f:
        c = yaml.safe_load(f)
    c["layout"].update(aisles=4, bays_per_side=5)
    c["slotting"]["affinity_min_support"] = 3
    return c


@pytest.fixture
def lines():
    return make_order_lines(n_orders=800, n_skus=150, seed=1)


def test_abc_shares(lines):
    v = velocity.abc_classes(velocity.sku_velocity(lines))
    assert set(v["abc"]) <= {"A", "B", "C"}
    a_share = v.loc[v["abc"] == "A", "share"].sum()
    assert 0.80 <= a_share < 0.95
    # Faster SKUs never get a lower class than slower ones
    assert v["abc"].is_monotonic_increasing


def test_affinity_lift_positive(lines):
    aff = velocity.co_pick_affinity(lines, min_support=3)
    assert not aff.empty
    assert (aff["lift"] > 0).all()
    assert (aff["sku_a"] < aff["sku_b"]).all()


def test_routing_single_aisle(cfg):
    layout = Layout.from_config(cfg["layout"])
    picks = {0: [5.0, 12.0]}
    # One aisle: walk in to the farthest pick and back, both heuristics agree
    assert s_shape(layout, picks) == pytest.approx(largest_gap(layout, picks))


def test_clusters_cover_every_sku(lines):
    v = velocity.sku_velocity(lines)
    aff = velocity.co_pick_affinity(lines, min_support=3)
    c = optimize.affinity_clusters(v, aff, cluster_size=20)
    assert c["cluster"].notna().all()
    assert c.groupby("cluster").size().max() <= 20


def test_fast_clusters_sit_closer(cfg, lines):
    layout = Layout.from_config(cfg["layout"])
    v = velocity.sku_velocity(lines)
    aff = velocity.co_pick_affinity(lines, min_support=3)
    c = optimize.affinity_clusters(v, aff, cluster_size=20)
    bays = layout.bays()
    plan = optimize.assign_clusters_to_bays(c, bays)
    picks = c.groupby("cluster")["picks"].sum()
    dist = bays.set_index("bay_id")["slot_cost"]
    d = pd.Series({k: dist[b] for k, b in plan.items()})
    # Busiest cluster is no farther than the quietest one
    assert d[picks.idxmax()] <= d[picks.idxmin()]


def test_pipeline_smoke(cfg, lines, tmp_path):
    metrics = run(cfg, lines, tmp_path)
    assert (tmp_path / "metrics.json").exists()
    for routing in cfg["picking"]["routing"]:
        assert metrics[f"optimised/{routing}"]["orders"] > 0
