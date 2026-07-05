"""Two-percent rule: x_i <= 0.02 for ingredients in the ≤2% group."""
from __future__ import annotations

from pydantic import BaseModel

from nusol.compiler.ir import LinearConstraintIR


class TwoPercentParams(BaseModel):
    ingredient_ids: list[str]


def register(registry) -> None:
    @registry.register("two_percent", parameter_model=TwoPercentParams)
    def compile_two_pct(params, ing_ids, nut_ids, n_vars):
        """x_i <= 0.02 for each ingredient in the ≤2% group."""
        import numpy as np

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
