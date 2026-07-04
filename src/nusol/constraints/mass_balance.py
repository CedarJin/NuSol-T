"""P0: Mass balance constraint — Σx_i = 1, x_i ≥ 0."""

from __future__ import annotations

from typing import Any

import numpy as np

from nusol.constraints.base import ConstraintBase, ConstraintEval
from nusol.core.enums import ConstraintPriority


class MassBalanceConstraint(ConstraintBase):
    """Total mass must sum to 1 (100% of finished product weight)."""

    priority = ConstraintPriority.P0
    name = "mass_balance"
    slack_allowed = False
    weight = 0.0  # Hard constraint — no penalty weight needed

    def evaluate(self, x: np.ndarray, context: dict[str, Any]) -> ConstraintEval:
        total = float(np.sum(x))
        violation = abs(total - 1.0)
        return ConstraintEval(
            name=self.name,
            value=total,
            target=1.0,
            violation=violation,
            satisfied=violation < 1e-6,
            priority=self.priority,
            weight=self.weight,
        )

    def to_scipy_constraint(self, context: dict[str, Any]) -> dict:
        """Return SciPy equality constraint: Σx_i - 1 = 0."""
        return {
            "type": "eq",
            "fun": lambda x: np.sum(x) - 1.0,
        }

    def to_scipy_bounds(self, context: dict[str, Any]) -> list[tuple[float, float]] | None:
        """All variables ≥ 0."""
        n = context.get("n_variables", len(context.get("ingredient_names", [])))
        return [(0.0, 1.0)] * n
