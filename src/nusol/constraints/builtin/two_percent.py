"""Two-percent rule: x_i <= 0.02 for ingredients in the ≤2% group.

Two modes:
  1. ``source: explicit`` — user provides ``ingredient_ids`` list
  2. ``source: declaration_group`` — auto-generate from ingredient group metadata

Config::

    config:
      source: declaration_group       # auto-detect from YAML declaration_group
      # source: explicit              # manual list (legacy behaviour)
      # ingredient_ids: [salt, vitamin_d]
"""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from nusol.compiler.ir import LinearConstraintIR


class TwoPercentParams(BaseModel):
    source: str = "declaration_group"  # "declaration_group" | "explicit"
    ingredient_ids: list[str] = []     # used when source="explicit"


def register(registry) -> None:
    @registry.register("two_percent", parameter_model=TwoPercentParams)
    def compile_two_pct(params, ing_ids, nut_ids, n_vars):
        """x_i <= 0.02 for each ingredient in the ≤2% group."""
        source = params.get("source", "declaration_group")

        if source == "declaration_group":
            ing_groups: list[str] = params.get(
                "_ingredient_groups", ["main"] * n_vars
            )
            target_ids = [
                ing_ids[i] for i in range(n_vars)
                if i < len(ing_groups) and ing_groups[i] == "two_percent_or_less"
            ]
        else:
            target_ids = params.get("ingredient_ids", [])

        result = []
        for ing_id in target_ids:
            if ing_id not in ing_ids:
                raise ValueError(
                    f"Two-percent ingredient '{ing_id}' not found in problem"
                )
            i = ing_ids.index(ing_id)
            coefficients = np.zeros(n_vars)
            coefficients[i] = 1.0
            result.append(
                LinearConstraintIR(
                    id=f"two_pct_{ing_id}",
                    coefficients=coefficients,
                    upper=0.02,
                    mode="hard",
                ),
            )
        return result
