"""BoundSolver — find feasible min/max for each ingredient."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import minimize, Bounds

from nusol.constraints.base import ConstraintBase, ConstraintBuilder
from nusol.core.schema import SolverResult
from nusol.solver.objective import build_objective


class BoundSolver:
    """Find feasible lower and upper bounds for each ingredient fraction.

    For each ingredient i:
      minimize x_i subject to all constraints → lower bound
      maximize x_i subject to all constraints → upper bound

    This reveals which ingredients are well-identified vs poorly-identified.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        solver_cfg = self.config.get("solver", {})
        bound_cfg = solver_cfg.get("bound_solver", {})
        self.method = solver_cfg.get("point_solver", "trust-constr")
        self.max_iter = solver_cfg.get("max_iter", 500)
        self.tolerance = solver_cfg.get("tolerance", 1e-8)

    def solve(
        self,
        variables: list[str],
        constraints: list[ConstraintBase],
        context: dict[str, Any],
        point_result: SolverResult | None = None,
        builder: ConstraintBuilder | None = None,
    ) -> SolverResult:
        """Compute lower and upper bounds for each variable.

        Args:
            variables: Ingredient names.
            constraints: Constraint list.
            context: Problem context.
            point_result: Optional point solution to use as starting point.
            builder: Optional ConstraintBuilder.

        Returns:
            SolverResult with x_lower and x_upper dicts.
        """
        n = len(variables)
        context["n_variables"] = n
        context["ingredient_names"] = variables

        t0 = time.perf_counter()

        if builder is None:
            builder = ConstraintBuilder(self.config)
        scipy_constraints = builder.build_scipy_constraints(constraints, context)

        scipy_bounds_list = builder.build_scipy_bounds(constraints, context)
        scipy_bounds = Bounds(
            [b[0] for b in scipy_bounds_list],
            [b[1] for b in scipy_bounds_list],
        )

        # Use uniform starting point
        x0_base = np.ones(n) / n
        if point_result and point_result.success:
            x0_base = np.array([point_result.x_point.get(v, 1.0 / n) for v in variables])

        objective = build_objective(constraints, context)

        x_lower = {}
        x_upper = {}

        for i in range(n):
            # Minimize x_i
            try:
                res_min = minimize(
                    lambda x: x[i] + 0.01 * objective(x),
                    x0_base,
                    method=self.method,
                    bounds=scipy_bounds,
                    constraints=scipy_constraints,
                    options={"maxiter": self.max_iter, "xtol": self.tolerance},
                )
                if res_min.success:
                    val = float(np.clip(res_min.x[i], 0.0, 1.0))
                else:
                    val = float(np.clip(x0_base[i], 0.0, 1.0))
                x_lower[variables[i]] = val
            except Exception:
                x_lower[variables[i]] = float(np.clip(x0_base[i], 0.0, 1.0))

            # Maximize x_i = minimize -x_i
            try:
                res_max = minimize(
                    lambda x: -x[i] + 0.01 * objective(x),
                    x0_base,
                    method=self.method,
                    bounds=scipy_bounds,
                    constraints=scipy_constraints,
                    options={"maxiter": self.max_iter, "xtol": self.tolerance},
                )
                if res_max.success:
                    val = float(np.clip(res_max.x[i], 0.0, 1.0))
                else:
                    val = float(np.clip(x0_base[i], 0.0, 1.0))
                x_upper[variables[i]] = val
            except Exception:
                x_upper[variables[i]] = float(np.clip(x0_base[i], 0.0, 1.0))

        solve_time = time.perf_counter() - t0

        return SolverResult(
            success=True,
            message=f"Bounds computed for {n} variables",
            x_lower=x_lower,
            x_upper=x_upper,
            solver_name=f"{self.method}_bound",
            solve_time_s=solve_time,
        )
