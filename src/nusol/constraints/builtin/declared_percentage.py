"""Declared percentage constraint: x_i = target for a specific ingredient."""
from __future__ import annotations

from pydantic import BaseModel

from nusol.compiler.ir import LinearConstraintIR


class DeclaredPercentageParams(BaseModel):
    ingredient: str
    exact: float | None = None
    interval: tuple[float, float] | None = None


def register(registry) -> None:
    @registry.register("declared_percentage", parameter_model=DeclaredPercentageParams)
    def compile_declared_pct(params, ing_ids, nut_ids, n_vars):
        import numpy as np

        ing_id = params["ingredient"]
        if ing_id not in ing_ids:
            raise ValueError(
                f"declared_percentage references '{ing_id}' not in ingredients"
            )
        i = ing_ids.index(ing_id)

        coefficients = np.zeros(n_vars)
        coefficients[i] = 1.0

        if params.get("exact") is not None:
            val = params["exact"]
            return [
                LinearConstraintIR(
                    id=f"declared_{ing_id}",
                    coefficients=coefficients,
                    lower=val,
                    upper=val,
                    mode="hard",
                ),
            ]
        elif params.get("interval") is not None:
            lo, hi = params["interval"]
            return [
                LinearConstraintIR(
                    id=f"declared_{ing_id}",
                    coefficients=coefficients,
                    lower=lo,
                    upper=hi,
                    mode="hard",
                ),
            ]
        raise ValueError("declared_percentage requires exact or interval")
