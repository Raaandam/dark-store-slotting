"""Load Instacart order lines and split them into slotting and evaluation sets."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


def load_instacart(orders: str | Path, order_products: str | Path, products: str | Path,
                   max_orders: int | None = None) -> pd.DataFrame:
    """Return one row per order line: order_id, sku, department, aisle."""
    prods = pd.read_csv(products, usecols=["product_id", "aisle_id", "department_id"])
    lines = pd.read_csv(order_products, usecols=["order_id", "product_id"])
    if max_orders:
        keep = lines["order_id"].drop_duplicates().iloc[:max_orders]
        lines = lines[lines["order_id"].isin(keep)]
    df = lines.merge(prods, on="product_id", how="left")
    return df.rename(columns={"product_id": "sku", "department_id": "department",
                              "aisle_id": "aisle"})


def restrict_to_top_skus(lines: pd.DataFrame, n: int) -> pd.DataFrame:
    """Keep lines for the n most-picked SKUs; a dark store carries a curated range."""
    top = lines["sku"].value_counts().index[:n]
    return lines[lines["sku"].isin(top)].reset_index(drop=True)


def split_orders(lines: pd.DataFrame, holdout_fraction: float,
                 seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by order so no order is used both to slot and to evaluate."""
    rng = np.random.default_rng(seed)
    orders = lines["order_id"].unique()
    test = set(rng.choice(orders, size=int(len(orders) * holdout_fraction), replace=False))
    mask = lines["order_id"].isin(test)
    return lines[~mask].reset_index(drop=True), lines[mask].reset_index(drop=True)
