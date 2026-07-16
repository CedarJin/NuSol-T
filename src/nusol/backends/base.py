"""Backend protocol — all solvers implement this interface."""

from __future__ import annotations

from typing import Any, Protocol

from nusol.compiler.ir import CompiledProblem


class SolveStats:
    """Statistics from a backend solve attempt."""

    def __init__(
        self,
        success: bool,
        status: str,
        message: str,
        objective_value: float | None = None,
        iterations: int | None = None,
        solve_time_s: float = 0.0,
        extra: dict[str, Any] | None = None,
    ) -> None:
        self.success = success
        self.status = status       # "optimal" / "infeasible" / "unbounded" / "error"
        self.message = message
        self.objective_value = objective_value
        self.iterations = iterations
        self.solve_time_s = solve_time_s
        self.extra = extra or {}

    def as_dict(self) -> dict[str, Any]:
        data = {
            "success": self.success,
            "status": self.status,
            "message": self.message,
            "objective_value": self.objective_value,
            "iterations": self.iterations,
            "solve_time_s": self.solve_time_s,
        }
        data.update(self.extra)
        return data


class PointBackend(Protocol):
    """Protocol for point-estimate solvers."""

    capabilities: frozenset[str]
    name: str

    def solve_point(
        self,
        problem: CompiledProblem,
    ) -> tuple[dict[str, float], SolveStats]:
        """Solve for a point estimate.

        Args:
            problem: The compiled problem to solve.

        Returns:
            (fractions_dict, stats) where fractions_dict maps ingredient_id → fraction.

        Raises:
            SolverError: If the problem is infeasible or solving fails.
        """
        ...


class BoundsBackend(Protocol):
    """Protocol for feasible-bounds solvers."""

    capabilities: frozenset[str]
    name: str

    def solve_bounds(
        self,
        problem: CompiledProblem,
    ) -> tuple[dict[str, tuple[float, float]], SolveStats]:
        """Solve for feasible lower/upper bounds for each variable.

        Args:
            problem: The compiled problem to solve.

        Returns:
            (bounds_dict, stats) where bounds_dict maps ingredient_id → (lo, hi).

        Raises:
            SolverError: If the problem is infeasible.
        """
        ...
