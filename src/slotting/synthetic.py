"""Instacart-shaped synthetic order lines for smoke tests without the real data."""

from __future__ import annotations

import numpy as np
import pandas as pd


def make_order_lines(n_orders: int = 5000, n_skus: int = 2000, n_departments: int = 12,
                     mean_lines: float = 8.0, zipf_s: float = 1.1,
                     seed: int = 0) -> pd.DataFrame:
    """Zipf-like SKU popularity plus 'basket themes' so co-pick affinity exists.

    Grocery demand is highly skewed: a few hundred staples (milk, bread, eggs,
    onions) take most picks, so zipf_s sits a little above 1.
    """
    rng = np.random.default_rng(seed)
    popularity = 1.0 / np.arange(1, n_skus + 1) ** zipf_s
    popularity /= popularity.sum()
    department = rng.integers(1, n_departments + 1, size=n_skus)

    # Each theme favours a handful of SKUs that tend to be bought together
    n_themes = 30
    themes = [rng.choice(n_skus // 5, size=12, replace=False) for _ in range(n_themes)]

    # Draw background picks in one go; per-pick weighted sampling is slow
    pool = iter(rng.choice(n_skus, size=int(n_orders * mean_lines * 2), p=popularity).tolist())
    rows = []
    for order_id in range(1, n_orders + 1):
        k = max(1, rng.poisson(mean_lines))
        theme = themes[rng.integers(n_themes)]
        n_theme = min(len(theme), rng.binomial(k, 0.4))
        picks = set(rng.choice(theme, size=n_theme, replace=False).tolist())
        while len(picks) < k:
            picks.add(next(pool))
        rows.extend((order_id, sku + 1, department[sku], department[sku] * 10) for sku in picks)

    return pd.DataFrame(rows, columns=["order_id", "sku", "department", "aisle"])
