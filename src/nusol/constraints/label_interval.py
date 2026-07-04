"""P2: Label interval fit constraint — predicted nutrients within label-derived intervals."""

from __future__ import annotations

from typing import Any

import numpy as np

from nusol.constraints.base import ConstraintBase, ConstraintEval
from nusol.core.enums import ConstraintPriority


class LabelIntervalFitConstraint(ConstraintBase):
    """Penalize nutrient predictions that fall outside label-derived intervals.

    For each label nutrient j with interval [lo_j, hi_j]:
        if predicted_j < lo_j: penalty += (lo_j - predicted_j)²
        if predicted_j > hi_j: penalty += (predicted_j - hi_j)²
    """

    priority = ConstraintPriority.P2
    name = "label_interval_fit"
    slack_allowed = True
    weight = 10.0

    def evaluate(self, x: np.ndarray, context: dict[str, Any]) -> ConstraintEval:
        nutrient_matrix = context.get("nutrient_matrix")
        target_intervals = context.get("target_intervals", {})
        nutrient_names = context.get("nutrient_names", [])

        if nutrient_matrix is None:
            return ConstraintEval(
                name=self.name, satisfied=True, priority=self.priority
            )

        # Compute predicted nutrients
        predicted = x @ nutrient_matrix

        total_violation = 0.0
        for j, name in enumerate(nutrient_names):
            interval = target_intervals.get(name)
            if interval is None:
                continue
            lo, hi = interval
            pred_j = predicted[j]
            if pred_j < lo:
                total_violation += (lo - pred_j) ** 2
            elif pred_j >= hi:
                total_violation += (pred_j - hi) ** 2

        satisfied = total_violation < 1e-10

        return ConstraintEval(
            name=self.name,
            value=float(total_violation),
            target=0.0,
            violation=float(total_violation),
            satisfied=satisfied,
            priority=self.priority,
            weight=self.weight,
        )
