"""P3: Sodium source balance — sodium should come primarily from salt-containing ingredients."""

from __future__ import annotations

from typing import Any

import numpy as np

from nusol.constraints.base import ConstraintBase, ConstraintEval
from nusol.core.enums import ConstraintPriority


class SodiumBalanceConstraint(ConstraintBase):
    """Soft constraint: ingredients with high sodium should account for label sodium.

    Penalizes solutions where sodium comes from ingredients with low natural sodium
    (e.g., sugar) rather than from salt/seasoning ingredients.
    """

    priority = ConstraintPriority.P3
    name = "sodium_balance"
    slack_allowed = True
    weight = 0.5

    SODIUM_KEY = "Sodium, Na"

    def evaluate(self, x: np.ndarray, context: dict[str, Any]) -> ConstraintEval:
        nutrient_matrix = context.get("nutrient_matrix")
        nutrient_names = context.get("nutrient_names", [])
        ingredient_names = context.get("ingredient_names", [])

        if nutrient_matrix is None:
            return ConstraintEval(name=self.name, satisfied=True, priority=self.priority)

        try:
            na_idx = nutrient_names.index(self.SODIUM_KEY)
        except ValueError:
            return ConstraintEval(name=self.name, satisfied=True, priority=self.priority)

        predicted_na = x @ nutrient_matrix[:, na_idx] if nutrient_matrix.ndim == 2 else x @ nutrient_matrix

        # Penalize if any single low-sodium ingredient contributes too much sodium
        # (This encourages salt to come from salt-containing ingredients)
        violation = 0.0
        for i, name in enumerate(ingredient_names):
            ing_na = nutrient_matrix[i, na_idx] if nutrient_matrix.ndim == 2 else 0
            # If an ingredient has very low natural sodium (<50mg/100g) but accounts
            # for >30% of total sodium → unlikely
            if ing_na < 50 and predicted_na > 0:
                fraction = x[i] * ing_na / max(predicted_na, 1e-6)
                if fraction > 0.3:
                    violation += (fraction - 0.3) ** 2

        return ConstraintEval(
            name=self.name,
            value=float(violation),
            target=0.0,
            violation=float(violation),
            satisfied=violation < 1e-6,
            priority=self.priority,
            weight=self.weight,
        )
