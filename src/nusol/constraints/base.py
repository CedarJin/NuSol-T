"""Base classes for constraints and constraint builder."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from nusol.core.enums import ConstraintPriority


@dataclass
class ConstraintEval:
    """Result of evaluating a constraint."""

    name: str = ""
    value: float = 0.0
    target: float = 0.0
    violation: float = 0.0
    slack: float = 0.0
    satisfied: bool = True
    weight: float = 1.0
    priority: ConstraintPriority = ConstraintPriority.P2

    @property
    def penalty(self) -> float:
        """Weighted penalty contribution for soft constraints."""
        if self.satisfied:
            return 0.0
        return self.weight * self.violation**2


class ConstraintBase:
    """Abstract base class for all constraints.

    Each constraint defines:
      - priority: P0 (hardest) → P4 (softest)
      - slack_allowed: whether the constraint can be relaxed
      - weight: penalty weight for soft constraints in the objective
    """

    priority: ConstraintPriority = ConstraintPriority.P2
    name: str = "base"
    enabled: bool = True
    slack_allowed: bool = False
    weight: float = 1.0

    def __init__(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def evaluate(self, x: np.ndarray, context: dict[str, Any]) -> ConstraintEval:
        """Evaluate the constraint at point x.

        Args:
            x: Decision variable array (ingredient fractions + optional params).
            context: Dict with problem metadata (ingredient names, nutrient data, etc.).

        Returns:
            ConstraintEval with violation and satisfaction info.
        """
        raise NotImplementedError

    def to_scipy_constraint(self, context: dict[str, Any]) -> dict | None:
        """Convert to SciPy constraint dict.

        Returns None if the constraint is handled as a penalty term.
        Only P0 (and some P1) constraints typically become scipy constraints.
        """
        return None

    def to_scipy_bounds(self, context: dict[str, Any]) -> list[tuple[float, float]] | None:
        """Convert to SciPy bounds for decision variables.

        Returns None if this constraint doesn't affect variable bounds.
        """
        return None


class ConstraintBuilder:
    """Builds a complete constraint set from configuration.

    Usage:
        builder = ConstraintBuilder(config)
        constraints = builder.build(product_obs)
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.constraint_cfg = self.config.get("constraints", {})

    def build(self, context: dict[str, Any]) -> list[ConstraintBase]:
        """Build all enabled constraints from configuration.

        The returned list is ordered by priority (P0 first).
        """
        from nusol.constraints.mass_balance import MassBalanceConstraint
        from nusol.constraints.ingredient_order import IngredientOrderConstraint
        from nusol.constraints.two_percent import TwoPercentRuleConstraint
        from nusol.constraints.label_interval import LabelIntervalFitConstraint
        from nusol.constraints.energy_closure import EnergyClosureConstraint
        from nusol.constraints.water_solid import WaterSolidBalanceConstraint
        from nusol.constraints.sodium_balance import SodiumBalanceConstraint
        from nusol.constraints.added_sugar_balance import AddedSugarBalanceConstraint
        from nusol.constraints.fatty_acid_closure import FattyAcidClosureConstraint
        from nusol.constraints.category_prior import CategoryPriorConstraint

        constraint_classes = {
            "mass_balance": MassBalanceConstraint,
            "ingredient_order": IngredientOrderConstraint,
            "two_percent_rule": TwoPercentRuleConstraint,
            "label_interval_fit": LabelIntervalFitConstraint,
            "energy_closure": EnergyClosureConstraint,
            "water_solid_balance": WaterSolidBalanceConstraint,
            "sodium_balance": SodiumBalanceConstraint,
            "added_sugar_balance": AddedSugarBalanceConstraint,
            "fatty_acid_closure": FattyAcidClosureConstraint,
            "category_prior": CategoryPriorConstraint,
        }

        constraints = []
        for name, cls in constraint_classes.items():
            cfg = self.constraint_cfg.get(name, {})
            if not cfg.get("enabled", True):
                continue

            instance = cls()
            instance.enabled = cfg.get("enabled", True)
            instance.weight = cfg.get("weight", cfg.get("penalty_weight", instance.weight))
            if hasattr(instance, "slack_allowed"):
                instance.slack_allowed = cfg.get("slack", False)

            constraints.append(instance)

        # Sort by priority (P0 first)
        constraints.sort(key=lambda c: c.priority)
        return constraints

    def build_scipy_constraints(
        self, constraints: list[ConstraintBase], context: dict[str, Any]
    ) -> list[dict]:
        """Convert applicable constraints to SciPy format."""
        scipy_cons = []
        for c in constraints:
            sc = c.to_scipy_constraint(context)
            if sc is not None:
                if isinstance(sc, list):
                    scipy_cons.extend(sc)
                else:
                    scipy_cons.append(sc)
        return scipy_cons

    def build_scipy_bounds(
        self, constraints: list[ConstraintBase], context: dict[str, Any]
    ) -> list[tuple[float, float]]:
        """Build variable bounds from constraints."""
        n = context.get("n_variables", len(context.get("ingredient_names", [])))
        bounds = [(0.0, 1.0)] * n  # Default: [0, 1]

        for c in constraints:
            b = c.to_scipy_bounds(context)
            if b is not None:
                for i, bi in enumerate(b):
                    if i < n:
                        # Combine: take the tighter bound
                        lo = max(bounds[i][0], bi[0])
                        hi = min(bounds[i][1], bi[1])
                        bounds[i] = (lo, hi)

        return bounds

    def evaluate_all(
        self, constraints: list[ConstraintBase], x: np.ndarray, context: dict[str, Any]
    ) -> list[ConstraintEval]:
        """Evaluate all enabled constraints."""
        results = []
        for c in constraints:
            if c.enabled:
                results.append(c.evaluate(x, context))
        return results

    def total_penalty(
        self, constraints: list[ConstraintBase], x: np.ndarray, context: dict[str, Any]
    ) -> float:
        """Compute total weighted penalty for all soft constraints (P2-P4)."""
        total = 0.0
        for c in constraints:
            if c.enabled and c.priority >= ConstraintPriority.P2:
                ev = c.evaluate(x, context)
                total += ev.penalty
        return total
