"""P3: Added sugar balance — added sugars should come from sugar/sweetener ingredients."""

from __future__ import annotations

from typing import Any

import numpy as np

from nusol.constraints.base import ConstraintBase, ConstraintEval
from nusol.core.enums import ConstraintPriority


class AddedSugarBalanceConstraint(ConstraintBase):
    """Soft constraint: added sugars should correlate with sugar-containing ingredients."""

    priority = ConstraintPriority.P3
    name = "added_sugar_balance"
    slack_allowed = True
    weight = 0.3

    SUGAR_KEY = "Total Sugars"
    ADDED_SUGAR_KEY = "Sugars, added"

    # Ingredients that are typically major sugar sources
    SUGAR_KEYWORDS = {"sugar", "sucrose", "fructose", "glucose", "syrup",
                       "honey", "molasses", "dextrose", "maltose", "cane",
                       "juice concentrate", "nectar", "agave"}

    def evaluate(self, x: np.ndarray, context: dict[str, Any]) -> ConstraintEval:
        nutrient_matrix = context.get("nutrient_matrix")
        nutrient_names = context.get("nutrient_names", [])
        ingredient_names = context.get("ingredient_names", [])

        if nutrient_matrix is None:
            return ConstraintEval(name=self.name, satisfied=True, priority=self.priority)

        def idx(name: str) -> int | None:
            try:
                return nutrient_names.index(name)
            except ValueError:
                return None

        sugar_idx = idx(self.SUGAR_KEY)
        added_idx = idx(self.ADDED_SUGAR_KEY)

        if sugar_idx is None or added_idx is None:
            return ConstraintEval(name=self.name, satisfied=True, priority=self.priority)

        # Find sugar-containing ingredients
        sugar_ing_indices = []
        for i, name in enumerate(ingredient_names):
            name_lower = name.lower()
            if any(kw in name_lower for kw in self.SUGAR_KEYWORDS):
                sugar_ing_indices.append(i)

        if not sugar_ing_indices:
            # No sugar ingredients → added sugar should be near 0
            predicted = x @ nutrient_matrix
            added_sugar = predicted[added_idx] if nutrient_matrix.ndim == 2 else 0
            violation = max(0, added_sugar - 0.5) ** 2
        else:
            # Added sugar should not exceed total sugar from sugar ingredients
            sugar_from_sources = 0.0
            for i in sugar_ing_indices:
                sugar_from_sources += x[i] * nutrient_matrix[i, sugar_idx]

            predicted = x @ nutrient_matrix
            added_sugar = predicted[added_idx] if nutrient_matrix.ndim == 2 else 0
            total_sugar = predicted[sugar_idx] if nutrient_matrix.ndim == 2 else 0

            # Added sugar ≤ total sugar from sugar ingredients (soft)
            violation = max(0, added_sugar - total_sugar) ** 2

        return ConstraintEval(
            name=self.name,
            value=float(violation),
            target=0.0,
            violation=float(violation),
            satisfied=violation < 1e-6,
            priority=self.priority,
            weight=self.weight,
        )
