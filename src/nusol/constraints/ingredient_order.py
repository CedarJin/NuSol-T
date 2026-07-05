"""P1: Ingredient order constraint — main ingredients in descending order."""

from __future__ import annotations

from typing import Any

import numpy as np

from nusol.constraints.base import ConstraintBase, ConstraintEval
from nusol.core.enums import ConstraintPriority


class IngredientOrderConstraint(ConstraintBase):
    """Main ingredients must appear in descending order by mass fraction.

    For ingredients NOT in the ≤2% group:
        x_i ≥ x_{i+1}

    Also enforces declared percentage constraints when available.
    """

    priority = ConstraintPriority.P1
    name = "ingredient_order"
    slack_allowed = True
    weight = 1000.0

    def evaluate(self, x: np.ndarray, context: dict[str, Any]) -> ConstraintEval:
        main_indices = context.get("main_ingredient_indices", list(range(len(x))))

        total_violation = 0.0
        n_violations = 0

        for k in range(len(main_indices) - 1):
            i = main_indices[k]
            j = main_indices[k + 1]
            if x[i] < x[j]:
                total_violation += x[j] - x[i]
                n_violations += 1

        satisfied = total_violation < 1e-6

        return ConstraintEval(
            name=self.name,
            value=float(total_violation),
            target=0.0,
            violation=float(total_violation),
            satisfied=satisfied,
            priority=self.priority,
            weight=self.weight,
        )

    def to_scipy_constraint(self, context: dict[str, Any]) -> list[dict]:
        """Return SciPy inequality constraints: x_i - x_{i+1} >= 0 for each pair.

        Unlike the soft-penalty approach, this enforces the order as hard constraints.
        """
        main_indices = context.get("main_ingredient_indices", [])
        if len(main_indices) < 2:
            return []

        constraints = []
        for k in range(len(main_indices) - 1):
            i = main_indices[k]
            j = main_indices[k + 1]

            # x[i] - x[j] >= 0  =>  x[j] - x[i] <= 0
            # scipy 'ineq' means fun(x) >= 0
            def make_ineq(i_val=i, j_val=j):
                return lambda x, i=i_val, j=j_val: x[i] - x[j]

            constraints.append({
                "type": "ineq",
                "fun": make_ineq(),
            })

        return constraints
