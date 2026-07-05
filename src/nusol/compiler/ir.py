"""Solver-neutral Intermediate Representation for compiled constraints."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np


@dataclass(frozen=True)
class VariableIR:
    """A decision variable in the compiled problem."""

    id: str
    lower: float | None = 0.0
    upper: float | None = 1.0
    kind: Literal["continuous", "integer", "binary"] = "continuous"


@dataclass(frozen=True)
class LinearConstraintIR:
    """A linear inequality/equality constraint: lower ≤ c·x ≤ upper."""

    id: str
    coefficients: np.ndarray = field(repr=False)  # shape (n_variables,)
    lower: float | None = None
    upper: float | None = None
    mode: Literal["hard", "soft"] = "hard"
    weight: float = 1.0
    source_id: str | None = None

    def __post_init__(self) -> None:
        if self.lower is None and self.upper is None:
            raise ValueError(
                f"LinearConstraintIR '{self.id}' must have at least one bound"
            )


@dataclass(frozen=True)
class QuadraticPenaltyIR:
    """A quadratic penalty term: weight * (||Q·x||² + 2·c·x + k) for soft constraints."""

    id: str
    quadratic: np.ndarray = field(repr=False)  # shape (n_vars, n_vars), symmetric PSD
    linear: np.ndarray = field(repr=False)  # shape (n_vars,)
    constant: float = 0.0
    weight: float = 1.0
    source_id: str | None = None


@dataclass(frozen=True)
class CompiledProblem:
    """A fully compiled problem ready for backend solving.

    All constraints have been lowered to solver-neutral IR.
    Backend capability check has NOT yet been performed (done separately).
    """

    variables: tuple[VariableIR, ...]
    linear_constraints: tuple[LinearConstraintIR, ...]
    quadratic_penalties: tuple[QuadraticPenaltyIR, ...]
    ingredient_ids: tuple[str, ...]
    nutrient_ids: tuple[str, ...]

    @property
    def n_variables(self) -> int:
        return len(self.variables)

    @property
    def required_capabilities(self) -> frozenset[str]:
        """Aggregate capabilities required by this problem."""
        caps: set[str] = {"continuous"}
        if self.quadratic_penalties:
            caps.add("quadratic_objective")
        if self.linear_constraints:
            caps.add("linear_constraints")
        if any(c.mode == "soft" for c in self.linear_constraints):
            caps.add("soft_constraints")
        return frozenset(caps)

    def __repr__(self) -> str:
        return (
            f"CompiledProblem({self.n_variables} vars, "
            f"{len(self.linear_constraints)} linear cons, "
            f"{len(self.quadratic_penalties)} quad penalties)"
        )
