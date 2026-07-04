"""Objective function construction for the inverse solver.

The objective is a weighted sum of soft-constraint penalties (P2-P4).
Hard constraints (P0, P1) are enforced by SciPy's constraint mechanism.
"""

from __future__ import annotations

from typing import Any, Callable

import numpy as np

from nusol.constraints.base import ConstraintBase
from nusol.core.enums import ConstraintPriority


def build_objective(
    constraints: list[ConstraintBase],
    context: dict[str, Any],
) -> Callable[[np.ndarray], float]:
    """Build the objective function for optimization.

    The objective is: Σ w_c × violation_c² for all soft constraints (P2-P4).

    Hard constraints (P0, P1) are NOT included in the objective — they
    are handled as SciPy constraints.

    Args:
        constraints: List of all constraints.
        context: Problem context dict.

    Returns:
        A callable f(x) → float that evaluates the objective at x.
    """
    # Collect only soft constraints (P2-P4)
    soft_constraints = [
        c for c in constraints
        if c.enabled and c.priority >= ConstraintPriority.P2
    ]

    def objective(x: np.ndarray) -> float:
        total = 0.0
        for c in soft_constraints:
            ev = c.evaluate(x, context)
            total += ev.penalty
        return total

    return objective


def build_constraint_violation_gradient(
    constraints: list[ConstraintBase],
    context: dict[str, Any],
) -> Callable[[np.ndarray], np.ndarray]:
    """Build a numerical gradient of the objective using finite differences.

    Args:
        constraints: List of constraints.
        context: Problem context.

    Returns:
        A callable f(x) → gradient array.
    """
    soft_constraints = [
        c for c in constraints
        if c.enabled and c.priority >= ConstraintPriority.P2
    ]

    def objective(x: np.ndarray) -> float:
        total = 0.0
        for c in soft_constraints:
            ev = c.evaluate(x, context)
            total += ev.penalty
        return total

    def gradient(x: np.ndarray) -> np.ndarray:
        eps = 1e-6
        grad = np.zeros_like(x)
        f0 = objective(x)
        for i in range(len(x)):
            x_pert = x.copy()
            x_pert[i] += eps
            grad[i] = (objective(x_pert) - f0) / eps
        return grad

    return gradient
