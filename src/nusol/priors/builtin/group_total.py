"""Ingredient group total fraction interval prior."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, model_validator

from nusol.compiler.ir import LinearConstraintIR


class GroupTotalPriorParams(BaseModel):
    ingredients: list[str]
    interval: tuple[float, float]

    @model_validator(mode="after")
    def validate_params(self) -> GroupTotalPriorParams:
        if not self.ingredients:
            raise ValueError("ingredients must be non-empty")
        lo, hi = self.interval
        if lo < 0 or hi > 1 or lo > hi:
            raise ValueError("interval must satisfy 0 <= lower <= upper <= 1")
        return self


def register(registry) -> None:
    @registry.register("group_total_prior", parameter_model=GroupTotalPriorParams)
    def compile_group_total(params, ingredient_ids, n_vars):
        coefficients = np.zeros(n_vars)
        for ing_id in params["ingredients"]:
            if ing_id not in ingredient_ids:
                raise ValueError(f"Unknown ingredient in prior: {ing_id}")
            coefficients[ingredient_ids.index(ing_id)] = 1.0
        lo, hi = params["interval"]
        return [
            LinearConstraintIR(
                id="prior_group_total",
                coefficients=coefficients,
                lower=lo,
                upper=hi,
                mode="soft",
            )
        ]
