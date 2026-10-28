"""Grid model of a dark store: parallel aisles, bays on both sides, shelf levels.

Coordinates are in metres. Aisle i runs along y from 0 to aisle_length at
x = i * aisle_spacing. The front cross aisle is at y = 0, the back one at
y = aisle_length, and the pack station sits in front of the first aisle.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class Layout:
    aisles: int
    bays_per_side: int
    levels: list[int]
    golden_levels: list[int]
    slots_per_level: int
    aisle_length_m: float
    aisle_spacing_m: float
    cross_aisle_m: float
    pack_station: tuple[float, float]

    @classmethod
    def from_config(cls, cfg: dict) -> "Layout":
        cfg = dict(cfg)
        cfg["pack_station"] = tuple(cfg["pack_station"])
        return cls(**cfg)

    @property
    def bay_depth_m(self) -> float:
        return self.aisle_length_m / self.bays_per_side

    def bays(self) -> pd.DataFrame:
        """One row per bay (aisle, side, position) with walk distance to the pack station."""
        px, py = self.pack_station
        rows = []
        for a in range(self.aisles):
            x = a * self.aisle_spacing_m
            for side in ("L", "R"):
                for b in range(self.bays_per_side):
                    y = (b + 0.5) * self.bay_depth_m
                    # Walk along the front cross aisle, then up the aisle
                    dist = abs(x - px) + abs(y - py)
                    rows.append((a, side, b, x, y, dist))
        df = pd.DataFrame(rows, columns=["aisle", "side", "bay", "x", "y", "dist_to_pack"])
        df["bay_id"] = range(len(df))
        # Slotting cost runs aisle by aisle ("within-aisle storage"): every bay in
        # aisle 0 is cheaper than any bay in aisle 1. Under traversal routing the
        # number of aisles entered dominates walk distance, so fast movers should
        # be packed into the fewest, nearest aisles rather than the nearest bays.
        df["slot_cost"] = (df["aisle"] * (self.aisle_length_m + self.aisle_spacing_m)
                           + df["y"])
        df["capacity"] = len(self.levels) * self.slots_per_level
        return df

    def slots(self) -> pd.DataFrame:
        """One row per SKU slot. Golden-zone levels carry a lower handling cost."""
        bays = self.bays()
        rows = []
        for _, bay in bays.iterrows():
            for lvl in self.levels:
                for s in range(self.slots_per_level):
                    rows.append((bay.bay_id, lvl, s, lvl in self.golden_levels))
        slots = pd.DataFrame(rows, columns=["bay_id", "level", "slot", "golden"])
        return slots.merge(bays, on="bay_id")
