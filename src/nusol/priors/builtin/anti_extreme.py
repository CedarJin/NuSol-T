"""Weak anti-extreme prior discouraging unsupported boundary solutions."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel

from nusol.compiler.ir import QuadraticPenaltyIR


class AntiExtremePriorParams(BaseModel):
    ingredients: list[str] | None = None
    target: float | None = None


def register(registry) -> None:
    @registry.register("anti_extreme_prior", parameter_model=AntiExtremePriorParams)
    def compile_anti_extreme(params, ingredient_ids, n_vars):
        selected = params.get("ingredients") or ingredient_ids
        target_value = params.get("target")
        if target_value is None:
            target_value = 1.0 / len(selected)

        target = np.zeros(n_vars)
        mask = np.zeros(n_vars)
        for ing_id in selected:
            if ing_id not in ingredient_ids:
                raise ValueError(f"Unknown ingredient in anti_extreme prior: {ing_id}")
            i = ingredient_ids.index(ing_id)
            target[i] = target_value
            mask[i] = 1.0

        quadratic = np.diag(mask)
        linear = -2.0 * target
        constant = float(np.dot(target, target))
        return [
            QuadraticPenaltyIR(
                id="prior_anti_extreme",
                quadratic=quadratic,
                linear=linear,
                constant=constant,
            )
        ]
