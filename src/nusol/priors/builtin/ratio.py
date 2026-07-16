"""Ratio prior between two ingredients or ingredient groups."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, model_validator

from nusol.compiler.ir import LinearConstraintIR


class RatioPriorParams(BaseModel):
    numerator: str | list[str]
    denominator: str | list[str]
    interval: tuple[float, float]

    @model_validator(mode="after")
    def validate_params(self) -> RatioPriorParams:
        lo, hi = self.interval
        if lo < 0 or lo > hi:
            raise ValueError("interval must satisfy 0 <= lower <= upper")
        return self


def _as_list(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else value


def register(registry) -> None:
    @registry.register("ratio_prior", parameter_model=RatioPriorParams)
    def compile_ratio(params, ingredient_ids, n_vars):
        numerator = _as_list(params["numerator"])
        denominator = _as_list(params["denominator"])
        lo, hi = params["interval"]

        def coefficients_for(ratio: float) -> np.ndarray:
            coefficients = np.zeros(n_vars)
            for ing_id in numerator:
                if ing_id not in ingredient_ids:
                    raise ValueError(f"Unknown numerator ingredient: {ing_id}")
                coefficients[ingredient_ids.index(ing_id)] += 1.0
            for ing_id in denominator:
                if ing_id not in ingredient_ids:
                    raise ValueError(f"Unknown denominator ingredient: {ing_id}")
                coefficients[ingredient_ids.index(ing_id)] -= ratio
            return coefficients

        # lower: numerator / denominator >= lo → numerator - lo*denominator >= 0
        # upper: numerator / denominator <= hi → numerator - hi*denominator <= 0
        return [
            LinearConstraintIR(
                id="prior_ratio_lower",
                coefficients=coefficients_for(lo),
                lower=0.0,
                mode="soft",
            ),
            LinearConstraintIR(
                id="prior_ratio_upper",
                coefficients=coefficients_for(hi),
                upper=0.0,
                mode="soft",
            ),
        ]
