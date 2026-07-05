"""General linear expression constraint: c·x ∈ [lower, upper].

Covers all category-specific priors (oil ≤ meat, flour 40-70%).
Coefficients map ingredient IDs to numeric values.
"""
from __future__ import annotations

from pydantic import BaseModel

from nusol.compiler.ir import LinearConstraintIR


class LinearExpressionParams(BaseModel):
    coefficients: dict[str, float]
    lower: float | None = None
    upper: float | None = None


def register(registry) -> None:
    @registry.register("linear_expression", parameter_model=LinearExpressionParams)
    def compile_linear_expr(params, ing_ids, nut_ids, n_vars):
        import numpy as np

        coeffs_dict = params["coefficients"]
        lower = params.get("lower")
        upper = params.get("upper")

        if lower is None and upper is None:
            raise ValueError(
                "linear_expression must have at least one of lower/upper"
            )

        coefficients = np.zeros(n_vars)
        for ing_id, val in coeffs_dict.items():
            if ing_id not in ing_ids:
                raise ValueError(
                    f"linear_expression references '{ing_id}' not in ingredients"
                )
            i = ing_ids.index(ing_id)
            coefficients[i] = val

        mode = params.get("mode", "hard")

        return [
            LinearConstraintIR(
                id=params.get("id", "linear_expr"),
                coefficients=coefficients,
                lower=lower,
                upper=upper,
                mode=mode,
                weight=params.get("weight", 1.0),
            ),
        ]
