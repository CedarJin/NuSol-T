"""Mass balance constraint: sum(x_i) = 1."""
from __future__ import annotations

import numpy as np

from nusol.compiler.ir import LinearConstraintIR


def register(registry) -> None:
    @registry.register("mass_balance")
    def compile_mass_balance(params, ing_ids, nut_ids, n_vars):
        """∑x = 1."""
        coefficients = np.ones(n_vars)
        return [
            LinearConstraintIR(
                id="mass_balance",
                coefficients=coefficients,
                lower=1.0,
                upper=1.0,
                mode="hard",
            ),
        ]
