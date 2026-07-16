"""Quadratic distance-to-center recipe prior."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, model_validator

from nusol.compiler.ir import QuadraticPenaltyIR


class RecipeCenterPriorParams(BaseModel):
    center: dict[str, float]

    @model_validator(mode="after")
    def validate_center(self) -> RecipeCenterPriorParams:
        if not self.center:
            raise ValueError("center must be non-empty")
        invalid = {key: value for key, value in self.center.items() if value < 0}
        if invalid:
            raise ValueError(f"center values must be non-negative: {invalid}")
        return self


def register(registry) -> None:
    @registry.register("recipe_center_prior", parameter_model=RecipeCenterPriorParams)
    def compile_recipe_center(params, ingredient_ids, n_vars):
        target = np.zeros(n_vars)
        mask = np.zeros(n_vars)
        for ing_id, value in params["center"].items():
            if ing_id not in ingredient_ids:
                raise ValueError(f"Unknown ingredient in prior center: {ing_id}")
            i = ingredient_ids.index(ing_id)
            target[i] = value
            mask[i] = 1.0
        quadratic = np.diag(mask)
        linear = -2.0 * target
        constant = float(np.dot(target, target))
        return [
            QuadraticPenaltyIR(
                id="prior_recipe_center",
                quadratic=quadratic,
                linear=linear,
                constant=constant,
            )
        ]
