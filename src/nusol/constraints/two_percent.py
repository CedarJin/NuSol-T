"""P1: Two percent rule constraint — ingredients in ≤2% group."""

from __future__ import annotations

from typing import Any

import numpy as np

from nusol.constraints.base import ConstraintBase, ConstraintEval
from nusol.core.enums import ConstraintPriority


class TwoPercentRuleConstraint(ConstraintBase):
    """Ingredients declared as 'contains 2% or less' must each be ≤ 0.02.

    When applied as scipy bounds, caps these variables at 0.02.
    """

    priority = ConstraintPriority.P1
    name = "two_percent_rule"
    slack_allowed = True
    weight = 1000.0

    def evaluate(self, x: np.ndarray, context: dict[str, Any]) -> ConstraintEval:
        two_pct_indices = context.get("two_percent_indices", [])

        total_violation = 0.0
        for i in two_pct_indices:
            if x[i] > 0.02:
                total_violation += x[i] - 0.02

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

    def to_scipy_bounds(self, context: dict[str, Any]) -> list[tuple[float, float]] | None:
        """Cap ≤2% ingredients at 0.02."""
        n = context.get("n_variables", len(context.get("ingredient_names", [])))
        two_pct_indices = context.get("two_percent_indices", [])
        bounds = [(0.0, 1.0)] * n
        for i in two_pct_indices:
            if i < n:
                bounds[i] = (0.0, 0.02)
        return bounds
