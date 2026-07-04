"""P3: Energy closure constraint — energy from macronutrients should match label energy."""

from __future__ import annotations

from typing import Any

import numpy as np

from nusol.constraints.base import ConstraintBase, ConstraintEval
from nusol.core.enums import ConstraintPriority


class EnergyClosureConstraint(ConstraintBase):
    """Soft constraint: Energy computed from macronutrients should be consistent.

    Atwater general factors:
      Energy (kcal) = 4 × Protein_g + 9 × Fat_g + 4 × Carbohydrate_g + 2 × Fiber_g + 7 × Alcohol_g
    """

    priority = ConstraintPriority.P3
    name = "energy_closure"
    slack_allowed = True
    weight = 0.2

    # Nutrient names to look for
    ENERGY_KEY = "Energy"
    PROTEIN_KEY = "Protein"
    FAT_KEY = "Total lipid (fat)"
    CARB_KEY = "Carbohydrate, by difference"
    FIBER_KEY = "Fiber, total dietary"
    ALCOHOL_KEY = "Alcohol, ethyl"

    def evaluate(self, x: np.ndarray, context: dict[str, Any]) -> ConstraintEval:
        nutrient_matrix = context.get("nutrient_matrix")
        nutrient_names = context.get("nutrient_names", [])

        if nutrient_matrix is None:
            return ConstraintEval(name=self.name, satisfied=True, priority=self.priority)

        predicted = x @ nutrient_matrix

        # Get indices for relevant nutrients
        def idx(name):
            try:
                return nutrient_names.index(name)
            except ValueError:
                return None

        energy_idx = idx(self.ENERGY_KEY)
        protein_idx = idx(self.PROTEIN_KEY)
        fat_idx = idx(self.FAT_KEY)
        carb_idx = idx(self.CARB_KEY)
        fiber_idx = idx(self.FIBER_KEY)
        alcohol_idx = idx(self.ALCOHOL_KEY)

        if energy_idx is None:
            return ConstraintEval(name=self.name, satisfied=True, priority=self.priority)

        # Compute energy from macronutrients
        calc_energy = 0.0
        if protein_idx is not None:
            calc_energy += 4.0 * predicted[protein_idx]
        if fat_idx is not None:
            calc_energy += 9.0 * predicted[fat_idx]
        if carb_idx is not None:
            calc_energy += 4.0 * predicted[carb_idx]
        if fiber_idx is not None:
            calc_energy += 2.0 * predicted[fiber_idx]
        if alcohol_idx is not None:
            calc_energy += 7.0 * predicted[alcohol_idx]

        label_energy = predicted[energy_idx]
        violation = (calc_energy - label_energy) ** 2

        return ConstraintEval(
            name=self.name,
            value=float(calc_energy),
            target=float(label_energy),
            violation=float(violation),
            satisfied=violation < 1.0,  # Allow ±1 kcal tolerance
            priority=self.priority,
            weight=self.weight,
        )
