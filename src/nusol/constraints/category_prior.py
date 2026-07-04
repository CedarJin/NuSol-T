"""P4: Category prior constraint — ingredient position / co-occurrence priors."""

from __future__ import annotations

from typing import Any

import numpy as np

from nusol.constraints.base import ConstraintBase, ConstraintEval
from nusol.core.enums import ConstraintPriority


class CategoryPriorConstraint(ConstraintBase):
    """Soft prior based on food category expectations.

    For example, in baked goods, flour is typically the first ingredient
    with a high fraction. This constraint penalizes large deviations from
    expected ingredient position-fraction patterns.

    Currently uses a simple uniform distribution prior — more sophisticated
    priors can be added as the project evolves.
    """

    priority = ConstraintPriority.P4
    name = "category_prior"
    slack_allowed = True
    weight = 0.1

    def evaluate(self, x: np.ndarray, context: dict[str, Any]) -> ConstraintEval:
        # For now, a minimal prior: penalize extreme fractions (> 0.8)
        # that are unlikely in real multi-ingredient products
        n = len(x)
        if n <= 1:
            return ConstraintEval(name=self.name, satisfied=True, priority=self.priority)

        violation = 0.0
        for i in range(n):
            if x[i] > 0.8:
                violation += (x[i] - 0.8) ** 2

        return ConstraintEval(
            name=self.name,
            value=float(violation),
            target=0.0,
            violation=float(violation),
            satisfied=violation < 1e-6,
            priority=self.priority,
            weight=self.weight,
        )
