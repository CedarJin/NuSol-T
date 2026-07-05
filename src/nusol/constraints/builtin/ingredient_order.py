"""Ingredient order constraint: x_i >= x_{i+1} for consecutive ingredients."""
from __future__ import annotations

import numpy as np

from nusol.compiler.ir import LinearConstraintIR


def register(registry) -> None:
    @registry.register("ingredient_order")
    def compile_order(params, ing_ids, nut_ids, n_vars):
        """x_i - x_{i+1} >= 0 → -(x_i - x_{i+1}) <= 0 → x_{i+1} - x_i <= 0"""
        result = []
        for i in range(len(ing_ids) - 1):
            coefficients = np.zeros(n_vars)
            coefficients[i] = 1.0  # x_i
            coefficients[i + 1] = -1.0  # -x_{i+1}
            result.append(
                LinearConstraintIR(
                    id=f"order_{ing_ids[i]}_ge_{ing_ids[i+1]}",
                    coefficients=coefficients,
                    lower=0.0,  # x_i - x_{i+1} >= 0
                    mode="hard",
                ),
            )
        return result
