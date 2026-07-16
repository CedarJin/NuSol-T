"""Ingredient order constraint: x_i >= x_{i+1}, declaration-group-aware.

Rules:
  1. ``main`` group: enforce descending order within the group
  2. ``two_percent_or_less`` group: no internal ordering by default
  3. No ordering enforced across group boundaries

Config::

    config:
      groups: ["main"]                # only enforce within these groups
      include_two_percent_order: false  # if true, also order 2% group
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from nusol.compiler.ir import LinearConstraintIR


class IngredientOrderParams(BaseModel):
    groups: list[str] = ["main"]
    include_two_percent_order: bool = False


def register(registry) -> None:
    @registry.register("ingredient_order", parameter_model=IngredientOrderParams)
    def compile_order(params, ing_ids, nut_ids, n_vars):
        """Declaration-group-aware ingredient ordering.

        Only enforces x_i >= x_{i+1} when BOTH ingredients i and i+1
        belong to a group listed in ``groups``.
        """
        enforce_groups: set[str] = set(params.get("groups", ["main"]))
        include_two = params.get("include_two_percent_order", False)
        if include_two:
            enforce_groups.add("two_percent_or_less")

        # Get ingredient groups from params (set by compiler)
        ing_groups: list[str] = params.get("_ingredient_groups", ["main"] * n_vars)

        result = []
        for i in range(n_vars - 1):
            g_i = ing_groups[i] if i < len(ing_groups) else "main"
            g_j = ing_groups[i + 1] if i + 1 < len(ing_groups) else "main"

            # Only enforce order when BOTH are in an enforced group
            if g_i not in enforce_groups or g_j not in enforce_groups:
                continue

            coefficients = np.zeros(n_vars)
            coefficients[i] = 1.0
            coefficients[i + 1] = -1.0
            result.append(
                LinearConstraintIR(
                    id=f"order_{ing_ids[i]}_ge_{ing_ids[i+1]}",
                    coefficients=coefficients,
                    lower=0.0,  # x_i - x_{i+1} >= 0
                    mode="hard",
                ),
            )
        return result
