"""Single ingredient fraction interval prior."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, model_validator

from nusol.compiler.ir import LinearConstraintIR


class FractionIntervalPriorParams(BaseModel):
    ingredient: str
    interval: tuple[float, float]

    @model_validator(mode="after")
    def validate_interval(self) -> FractionIntervalPriorParams:
        lo, hi = self.interval
        if lo < 0 or hi > 1 or lo > hi:
            raise ValueError("interval must satisfy 0 <= lower <= upper <= 1")
        return self


def register(registry) -> None:
    @registry.register(
        "fraction_interval_prior",
        parameter_model=FractionIntervalPriorParams,
    )
    def compile_fraction_interval(params, ingredient_ids, n_vars):
        ing_id = params["ingredient"]
        if ing_id not in ingredient_ids:
            raise ValueError(f"Unknown ingredient in prior: {ing_id}")
        lo, hi = params["interval"]
        coefficients = np.zeros(n_vars)
        coefficients[ingredient_ids.index(ing_id)] = 1.0
        return [
            LinearConstraintIR(
                id=f"prior_fraction_interval_{ing_id}",
                coefficients=coefficients,
                lower=lo,
                upper=hi,
                mode="soft",
            )
        ]
