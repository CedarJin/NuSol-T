"""Forward Nutrition Calculation Model.

Core equation:
    predicted_j = (100 / Y) * Σ_i x_i * A_ij * r_ij

where:
    x_i = mass fraction of ingredient i
    A_ij = amount of nutrient j in ingredient i per 100g
    r_ij = retention factor for nutrient j in ingredient i
    Y = final yield (accounting for moisture change)
"""

from __future__ import annotations

from typing import Optional

import numpy as np


class ForwardNutritionModel:
    """Forward model for calculating final product nutrients from ingredients.

    This model computes the nutrient profile of a finished food product
    given ingredient fractions and their nutrient compositions.
    """

    def __init__(self, config: dict | None = None) -> None:
        config = config or {}
        self.basis = config.get("basis", "per_100g")
        self.retention_enabled = config.get("retention", {}).get("enabled", False)
        self.moisture_enabled = config.get("moisture", {}).get("enabled", False)

    def compute(
        self,
        ingredient_fractions: np.ndarray,
        nutrient_matrix: np.ndarray,
        retention_factors: Optional[np.ndarray] = None,
        moisture_change: float = 0.0,
    ) -> np.ndarray:
        """Compute predicted final nutrient values.

        Args:
            ingredient_fractions: Shape (n_ingredients,) — mass fractions (sum to 1).
            nutrient_matrix: Shape (n_ingredients, n_nutrients) — A_ij values per 100g.
            retention_factors: Optional shape (n_ingredients, n_nutrients) — retention factors.
            moisture_change: Moisture/yield change as fraction (e.g. 0.05 = 5% moisture loss).

        Returns:
            Shape (n_nutrients,) — predicted nutrient values per 100g finished product.
        """
        # Apply retention if enabled
        if self.retention_enabled and retention_factors is not None:
            effective_matrix = nutrient_matrix * retention_factors
        else:
            effective_matrix = nutrient_matrix

        # Basic linear combination
        predicted = ingredient_fractions @ effective_matrix

        # Yield adjustment (moisture change)
        if self.moisture_enabled and abs(moisture_change) > 1e-10:
            # When moisture is lost, nutrients concentrate
            # predicted = (100 / (100 - moisture_change_percent)) * raw_prediction
            yield_factor = 100.0 / (100.0 - moisture_change)
            predicted = predicted * yield_factor

        return predicted

    def compute_from_dicts(
        self,
        ingredient_fractions: dict[str, float],
        nutrient_matrix: dict[str, dict[str, float]],
        nutrient_names: list[str],
    ) -> dict[str, float]:
        """Compute predicted nutrients from dictionary-based inputs.

        Args:
            ingredient_fractions: {ingredient_name: fraction}
            nutrient_matrix: {ingredient_name: {nutrient_name: amount}}
            nutrient_names: List of nutrient names to compute.

        Returns:
            {nutrient_name: predicted_amount}
        """
        # Build arrays
        ing_names = list(ingredient_fractions.keys())
        x = np.array([ingredient_fractions[name] for name in ing_names])

        A = np.zeros((len(ing_names), len(nutrient_names)))
        for i, ing_name in enumerate(ing_names):
            ing_nutrients = nutrient_matrix.get(ing_name, {})
            for j, nut_name in enumerate(nutrient_names):
                A[i, j] = ing_nutrients.get(nut_name, 0.0)

        predicted = self.compute(x, A)

        return {name: float(predicted[j]) for j, name in enumerate(nutrient_names)}

    def compute_energy_from_macronutrients(
        self,
        protein_g: float,
        fat_g: float,
        carbohydrate_g: float,
        fiber_g: float = 0.0,
        alcohol_g: float = 0.0,
    ) -> float:
        """Estimate energy (kcal) from macronutrients using Atwater factors.

        Standard Atwater factors:
          Protein: 4 kcal/g
          Fat: 9 kcal/g
          Carbohydrate: 4 kcal/g
          Fiber: 2 kcal/g (approximate)
          Alcohol: 7 kcal/g
        """
        return (
            4.0 * protein_g
            + 9.0 * fat_g
            + 4.0 * carbohydrate_g
            + 2.0 * fiber_g
            + 7.0 * alcohol_g
        )

    def compute_water_by_difference(self, fractions: np.ndarray, water_values: np.ndarray) -> float:
        """Compute water content as the weighted sum of ingredient water.

        Args:
            fractions: Ingredient mass fractions.
            water_values: Water content (g/100g) for each ingredient.

        Returns:
            Estimated water content (g/100g).
        """
        return float(np.dot(fractions, water_values))
