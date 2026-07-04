"""PointSolver — find a single optimal ingredient fraction estimate."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import minimize, Bounds

from nusol.constraints.base import ConstraintBase, ConstraintBuilder
from nusol.core.schema import SolverResult
from nusol.solver.objective import build_objective
from nusol.solver.initializer import generate_initial_guesses


class PointSolver:
    """Find a single optimal point estimate for ingredient fractions.

    Uses SciPy's trust-constr (preferred) or SLSQP to minimize the weighted
    soft-constraint penalty subject to hard P0/P1 constraints.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        solver_cfg = self.config.get("solver", {})
        self.method = solver_cfg.get("point_solver", "trust-constr")
        self.multi_start = solver_cfg.get("multi_start", 50)
        self.max_iter = solver_cfg.get("max_iter", 1000)
        self.tolerance = solver_cfg.get("tolerance", 1e-8)
        self.init_strategy = solver_cfg.get("init_strategy", "dirichlet")

    def solve(
        self,
        variables: list[str],
        constraints: list[ConstraintBase],
        context: dict[str, Any],
        builder: ConstraintBuilder | None = None,
    ) -> SolverResult:
        """Solve for optimal ingredient fractions.

        Args:
            variables: Ingredient names (for output labeling).
            constraints: List of enabled constraints.
            context: Problem context with nutrient_matrix, target_intervals, etc.
            builder: Optional ConstraintBuilder for scipy conversion.

        Returns:
            SolverResult with point estimates and fit quality.
        """
        n = len(variables)
        context["n_variables"] = n
        context["ingredient_names"] = variables

        t0 = time.perf_counter()

        # Build scipy constraints (P0 + P1)
        if builder is None:
            builder = ConstraintBuilder(self.config)
        scipy_constraints = builder.build_scipy_constraints(constraints, context)

        # Build variable bounds
        scipy_bounds_list = builder.build_scipy_bounds(constraints, context)
        scipy_bounds = Bounds(
            [b[0] for b in scipy_bounds_list],
            [b[1] for b in scipy_bounds_list],
        )

        # Build objective (P2-P4 penalties)
        objective = build_objective(constraints, context)

        # Multi-start optimization
        best_x = None
        best_fun = float("inf")
        n_evals = 0
        n_iter = 0

        initial_guesses = generate_initial_guesses(
            n, self.multi_start, strategy=self.init_strategy
        )

        for x0 in initial_guesses:
            try:
                result = minimize(
                    objective,
                    x0,
                    method=self.method,
                    bounds=scipy_bounds,
                    constraints=scipy_constraints,
                    options={"maxiter": self.max_iter, "xtol": self.tolerance},
                )
                n_evals += result.nfev if hasattr(result, "nfev") else 0
                n_iter += result.nit if hasattr(result, "nit") else 0

                if result.success and result.fun < best_fun:
                    best_fun = result.fun
                    best_x = result.x.copy()
            except Exception:
                continue

        solve_time = time.perf_counter() - t0

        if best_x is None:
            # Fallback: uniform distribution
            best_x = np.ones(n) / n
            success = False
            message = "All solver attempts failed; returning uniform fallback"
        else:
            success = True
            message = "Optimal point found via multi-start"

        # Compute predictions and residuals
        nutrient_matrix = context.get("nutrient_matrix")
        nutrient_names = context.get("nutrient_names", [])
        nutrient_predicted = {}
        nutrient_residuals = {}

        if nutrient_matrix is not None:
            pred = best_x @ nutrient_matrix
            for j, name in enumerate(nutrient_names):
                nutrient_predicted[name] = float(pred[j])
                target_intervals = context.get("target_intervals", {})
                interval = target_intervals.get(name)
                if interval is not None:
                    lo, hi = interval
                    if pred[j] < lo:
                        nutrient_residuals[name] = float(lo - pred[j])
                    elif pred[j] >= hi:
                        nutrient_residuals[name] = float(pred[j] - hi)
                    else:
                        nutrient_residuals[name] = 0.0

        # Build constraint evaluation
        constraint_values = {}
        constraint_slacks = {}
        active_constraints = []
        for c in constraints:
            if c.enabled:
                ev = c.evaluate(best_x, context)
                constraint_values[c.name] = ev.value
                constraint_slacks[c.name] = ev.slack
                if not ev.satisfied:
                    active_constraints.append(c.name)

        return SolverResult(
            success=success,
            message=message,
            x_point={variables[i]: float(best_x[i]) for i in range(n)},
            objective_value=float(best_fun),
            nutrient_predicted=nutrient_predicted,
            nutrient_residuals=nutrient_residuals,
            constraint_values=constraint_values,
            constraint_slacks=constraint_slacks,
            active_constraints=active_constraints,
            solver_name=self.method,
            n_iterations=n_iter,
            n_func_evals=n_evals,
            solve_time_s=solve_time,
        )

    def _solve_single(
        self,
        x0: np.ndarray,
        variables: list[str],
        constraints: list[ConstraintBase],
        context: dict[str, Any],
        builder: ConstraintBuilder | None = None,
    ) -> SolverResult | None:
        """Solve from a single starting point. Used by EnsembleSolver."""
        n = len(variables)

        if builder is None:
            builder = ConstraintBuilder(self.config)
        scipy_constraints = builder.build_scipy_constraints(constraints, context)
        scipy_bounds_list = builder.build_scipy_bounds(constraints, context)
        scipy_bounds = Bounds(
            [b[0] for b in scipy_bounds_list],
            [b[1] for b in scipy_bounds_list],
        )
        objective = build_objective(constraints, context)

        try:
            result = minimize(
                objective,
                x0,
                method=self.method,
                bounds=scipy_bounds,
                constraints=scipy_constraints,
                options={"maxiter": self.max_iter, "xtol": self.tolerance},
            )
            if result.success:
                return SolverResult(
                    success=True,
                    x_point={variables[i]: float(result.x[i]) for i in range(n)},
                    objective_value=float(result.fun),
                    solver_name=self.method,
                )
        except Exception:
            pass
        return None
