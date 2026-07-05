"""P3: Water-solid balance constraint.

Water + Protein + Fat + Carbohydrate + Fiber + Ash ≈ 100g per 100g.
This provides a structural constraint even when water is not on the label.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from nusol.constraints.base import ConstraintBase, ConstraintEval
from nusol.core.enums import ConstraintPriority


class WaterSolidBalanceConstraint(ConstraintBase):
    """Soft constraint: water + solids ≈ 100% of product mass.

    Solids ≈ protein + fat + carbohydrate + fiber + ash.
    If ash is not available, it's estimated as ~1-3% typical residual.
    """

    priority = ConstraintPriority.P3
    name = "water_solid_balance"
    slack_allowed = True
    weight = 0.5

    WATER_KEY = "Water"
    PROTEIN_KEY = "Protein"
    FAT_KEY = "Total lipid (fat)"
    CARB_KEY = "Carbohydrate, by difference"
    FIBER_KEY = "Fiber, total dietary"
    ASH_KEY = "Ash"
    ALCOHOL_KEY = "Alcohol, ethyl"

    def evaluate(self, x: np.ndarray, context: dict[str, Any]) -> ConstraintEval:
        nutrient_matrix = context.get("nutrient_matrix")
        nutrient_names = context.get("nutrient_names", [])

        if nutrient_matrix is None:
            return ConstraintEval(name=self.name, satisfied=True, priority=self.priority)

        predicted = x @ nutrient_matrix

        def idx(name: str) -> int | None:
            try:
                return nutrient_names.index(name)
            except ValueError:
                return None

        water_idx = idx(self.WATER_KEY)
        protein_idx = idx(self.PROTEIN_KEY)
        fat_idx = idx(self.FAT_KEY)
        carb_idx = idx(self.CARB_KEY)
        fiber_idx = idx(self.FIBER_KEY)
        ash_idx = idx(self.ASH_KEY)
        alcohol_idx = idx(self.ALCOHOL_KEY)

        # Sum solids
        total = 0.0
        if water_idx is not None:
            total += predicted[water_idx]
        if protein_idx is not None:
            total += predicted[protein_idx]
        if fat_idx is not None:
            total += predicted[fat_idx]
        if carb_idx is not None:
            total += predicted[carb_idx]
        if fiber_idx is not None:
            total += predicted[fiber_idx]
        if ash_idx is not None:
            total += predicted[ash_idx]
        if alcohol_idx is not None:
            total += predicted[alcohol_idx]

        # Should be close to 100 (g per 100g)
        violation = (total - 100.0) ** 2

        return ConstraintEval(
            name=self.name,
            value=float(total),
            target=100.0,
            violation=float(violation),
            satisfied=abs(total - 100.0) < 2.0,  # ±2g tolerance
            priority=self.priority,
            weight=self.weight,
        )
