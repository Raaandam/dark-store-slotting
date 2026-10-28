"""Pick-route distance for a single order under two classic routing heuristics.

S-shape (traversal): enter every aisle that holds a pick and walk its full
length, alternating direction; return from the last aisle if needed.

Largest gap: in each picked aisle, enter from the front and back cross
aisles but never cross the largest gap between consecutive picks.
"""

from __future__ import annotations

import numpy as np

from .layout import Layout


def _horizontal(layout: Layout, aisles: list[int]) -> float:
    """Walk along the cross aisles from the pack station to the farthest aisle and back."""
    px = layout.pack_station[0]
    far = max(aisles) * layout.aisle_spacing_m
    return 2 * abs(far - px)


def s_shape(layout: Layout, picks: dict[int, list[float]]) -> float:
    """picks maps aisle index to the y positions of the picks in that aisle."""
    if not picks:
        return 0.0
    aisles = sorted(picks)
    L = layout.aisle_length_m + 2 * layout.cross_aisle_m
    dist = _horizontal(layout, aisles) + 2 * abs(layout.pack_station[1])
    n = len(aisles)
    if n % 2 == 0:
        dist += n * L
    else:
        # Odd count: the last aisle is entered and exited from the front
        dist += (n - 1) * L + 2 * max(picks[aisles[-1]])
    return dist


def largest_gap(layout: Layout, picks: dict[int, list[float]]) -> float:
    if not picks:
        return 0.0
    aisles = sorted(picks)
    L = layout.aisle_length_m
    dist = _horizontal(layout, aisles) + 2 * abs(layout.pack_station[1])
    if len(aisles) == 1:
        # Nothing to gain from the back cross aisle: walk in to the farthest pick and out
        return dist + 2 * max(picks[aisles[0]])
    # The first and last aisles are traversed fully to reach the back cross aisle
    dist += 2 * (L + 2 * layout.cross_aisle_m)
    for a in aisles[1:-1]:
        ys = np.sort(np.asarray(picks[a]))
        gaps = np.diff(np.concatenate([[0.0], ys, [L]]))
        # Walk everything twice except the largest gap
        dist += 2 * (L - gaps.max())
    return dist


ROUTERS = {"s_shape": s_shape, "largest_gap": largest_gap}
