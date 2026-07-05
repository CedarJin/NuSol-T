"""P3: Fatty acid closure — saturated + mono + poly + trans ≤ total fat."""

from __future__ import annotations

from typing import Any

import numpy as np

from nusol.constraints.base import ConstraintBase, ConstraintEval
from nusol.core.enums import ConstraintPriority


class FattyAcidClosureConstraint(ConstraintBase):
    """Soft constraint: individual fatty acid classes should not exceed total fat."""

    priority = ConstraintPriority.P3
    name = "fatty_acid_closure"
    slack_allowed = True
    weight = 0.3

    FAT_KEY = "Total lipid (fat)"
    SAT_KEY = "Fatty acids, total saturated"
    MONO_KEY = "Fatty acids, total monounsaturated"
    POLY_KEY = "Fatty acids, total polyunsaturated"
    TRANS_KEY = "Fatty acids, total trans"

    def evaluate(self, x: np.ndarray, context: dict[str, Any]) -> ConstraintEval:
        nutrient_matrix = context.get("nutrient_matrix")
        nutrient_names = context.get("nutrient_names", [])

        if nutrient_matrix is None:
            return ConstraintEval(name=self.name, satisfied=True, priority=self.priority)

        def idx(name: str) -> int | None:
            try:
                return nutrient_names.index(name)
            except ValueError:
                return None

        fat_idx = idx(self.FAT_KEY)
        sat_idx = idx(self.SAT_KEY)
        mono_idx = idx(self.MONO_KEY)
        poly_idx = idx(self.POLY_KEY)
        trans_idx = idx(self.TRANS_KEY)

        if fat_idx is None:
            return ConstraintEval(name=self.name, satisfied=True, priority=self.priority)

        predicted = x @ nutrient_matrix
        total_fat = predicted[fat_idx]

        sub_total = 0.0
        if sat_idx is not None:
            sub_total += predicted[sat_idx]
        if mono_idx is not None:
            sub_total += predicted[mono_idx]
        if poly_idx is not None:
            sub_total += predicted[poly_idx]
        if trans_idx is not None:
            sub_total += predicted[trans_idx]

        # Sub-total should not exceed total fat
        violation = max(0, sub_total - total_fat) ** 2

        return ConstraintEval(
            name=self.name,
            value=float(sub_total),
            target=float(total_fat),
            violation=float(violation),
            satisfied=sub_total <= total_fat + 0.5,  # 0.5g tolerance
            priority=self.priority,
            weight=self.weight,
        )
