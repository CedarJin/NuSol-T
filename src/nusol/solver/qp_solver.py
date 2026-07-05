"""QPSolver — convex quadratic programming formulation for inverse ingredient estimation.

Reformulates the constrained optimization as a convex QP with slack variables:

    minimize   Σ_j (s_j_lo² + s_j_hi²)
    subject to Σx_i = 1, x_i ≥ 0, x_i ≥ x_{i+1}  (mass balance + order)
              Σx_i·A_ij + s_j_lo ≥ lo_j           (label interval lower)
              Σx_i·A_ij - s_j_hi ≤ hi_j           (label interval upper)
              s ≥ 0

This is a convex QP → unique global minimum → no multi-start needed.
Typically 20-400ms per recipe with SLSQP, vs 3-8s with trust-constr multi-start.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import Bounds, minimize

from nusol.constraints.base import ConstraintBase, ConstraintBuilder
from nusol.core.schema import SolverResult
from nusol.core.nutrient_registry import LABEL_NUTRIENT_NAMES


class QPSolver:
    """Solve inverse ingredient estimation as a convex quadratic program.

    Replaces PointSolver. Uses slack variables for label interval constraints,
    making the problem a convex QP solvable in a single SLSQP pass.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        solver_cfg = self.config.get("solver", self.config)
        self.method = solver_cfg.get("qp_method", "SLSQP")
        self.max_iter = solver_cfg.get("max_iter", 500)
        self.tolerance = solver_cfg.get("tolerance", 1e-8)

    def solve(
        self,
        variables: list[str],
        constraints: list[ConstraintBase],
        context: dict[str, Any],
        builder: ConstraintBuilder | None = None,
    ) -> SolverResult:
        """Solve via convex QP with slack variables.

        Args:
            variables: Ingredient names.
            constraints: Constraint list (unused; QP builds its own from context).
            context: Problem context with nutrient_matrix, target_intervals, etc.
            builder: Optional ConstraintBuilder (unused).

        Returns:
            SolverResult with point estimates.
        """
        n = len(variables)
        context["n_variables"] = n
        context["ingredient_names"] = variables

        t0 = time.perf_counter()

        # Extract data from context
        A = context.get("nutrient_matrix")
        nutrient_names = context.get("nutrient_names", [])
        target_intervals = context.get("target_intervals", {})
        main_indices = context.get("main_ingredient_indices", list(range(n)))

        if A is None:
            return SolverResult(success=False, message="No nutrient matrix in context")

        m = len(nutrient_names)
        lo = np.zeros(m)
        hi = np.full(m, 1e9)

        for j, name in enumerate(nutrient_names):
            interval = target_intervals.get(name)
            if interval is not None:
                lo[j] = interval[0]
                hi[j] = interval[1]

        # Decision vector: [x_0..x_{n-1}, s_0_lo..s_{m-1}_lo, s_0_hi..s_{m-1}_hi]
        nv = n + 2 * m

        # Initial guess
        x0 = np.zeros(nv)
        x0[:n] = 1.0 / n
        for j in range(m):
            pred = float(np.dot(x0[:n], A[:, j]))
            x0[n + j] = max(0.0, lo[j] - pred)
            x0[n + m + j] = max(0.0, pred - hi[j])

        # ── Objective: Σ s_lo² + Σ s_hi² ──
        def objective(x: np.ndarray) -> float:
            s_lo = x[n : n + m]
            s_hi = x[n + m : n + 2 * m]
            return float(np.dot(s_lo, s_lo) + np.dot(s_hi, s_hi))

        # ── Constraints ──
        scipy_cons = []

        # P0: mass balance Σx = 1
        scipy_cons.append({"type": "eq", "fun": lambda x: np.sum(x[:n]) - 1.0})

        # P1: ingredient order x_i ≥ x_{i+1} for consecutive main ingredients
        if len(main_indices) >= 2:
            for k in range(len(main_indices) - 1):
                i = main_indices[k]
                j = main_indices[k + 1]
                scipy_cons.append({
                    "type": "ineq",
                    "fun": lambda x, i=i, j=j: x[i] - x[j],
                })

        # P2: label interval lower: pred + s_lo ≥ lo
        for j in range(m):
            scipy_cons.append({
                "type": "ineq",
                "fun": lambda x, j=j: float(np.dot(x[:n], A[:, j])) + x[n + j] - lo[j],
            })

        # P2: label interval upper: pred - s_hi ≤ hi  →  hi - pred + s_hi ≥ 0
        for j in range(m):
            scipy_cons.append({
                "type": "ineq",
                "fun": lambda x, j=j: hi[j] - float(np.dot(x[:n], A[:, j])) + x[n + m + j],
            })

        # Slack non-negativity: s ≥ 0
        for j in range(2 * m):
            scipy_cons.append({
                "type": "ineq",
                "fun": lambda x, j=j: x[n + j],
            })

        # Bounds: x_i ∈ [0, 1], slack ∈ [0, ∞)
        bounds = Bounds([0.0] * nv, [1.0] * n + [1e6] * (2 * m))

        # ── Solve ──
        try:
            result = minimize(
                objective,
                x0,
                method=self.method,
                bounds=bounds,
                constraints=scipy_cons,
                options={"maxiter": self.max_iter, "ftol": self.tolerance},
            )
            success = result.success
            message = result.message
            x_opt = result.x
            x_ing = np.clip(x_opt[:n], 0.0, 1.0)

            # Re-normalize to ensure Σx=1 (SLSQP may have tiny violation)
            total = x_ing.sum()
            if total > 0:
                x_ing = x_ing / total

        except Exception as e:
            success = False
            message = str(e)
            x_ing = np.ones(n) / n

        solve_time = time.perf_counter() - t0

        # ── Compute residuals and constraint evals ──
        nutrient_predicted = {}
        nutrient_residuals = {}

        if A is not None:
            pred = x_ing @ A
            for j, name in enumerate(nutrient_names):
                nutrient_predicted[name] = float(pred[j])
                interval = target_intervals.get(name)
                if interval is not None:
                    lo_j, hi_j = interval
                    if pred[j] < lo_j:
                        nutrient_residuals[name] = float(lo_j - pred[j])
                    elif pred[j] >= hi_j:
                        nutrient_residuals[name] = float(pred[j] - hi_j)
                    else:
                        nutrient_residuals[name] = 0.0

        # Check constraint satisfaction
        constraint_values = {"mass_balance": float(x_ing.sum())}
        constraint_slacks = {"mass_balance": float(abs(x_ing.sum() - 1.0))}
        active_constraints = []

        if abs(x_ing.sum() - 1.0) > 1e-4:
            active_constraints.append("mass_balance")

        # Check order violations
        if len(main_indices) >= 2:
            order_violations = 0.0
            for k in range(len(main_indices) - 1):
                i = main_indices[k]
                j = main_indices[k + 1]
                if x_ing[i] < x_ing[j]:
                    order_violations += x_ing[j] - x_ing[i]
            constraint_values["ingredient_order"] = float(order_violations)
            constraint_slacks["ingredient_order"] = float(order_violations)
            if order_violations > 1e-4:
                active_constraints.append("ingredient_order")

        # Check label fit
        label_violations = 0.0
        for name, res in nutrient_residuals.items():
            label_violations += res ** 2
        constraint_values["label_interval_fit"] = float(label_violations)
        constraint_slacks["label_interval_fit"] = float(label_violations)
        if label_violations > 1e-4:
            active_constraints.append("label_interval_fit")

        return SolverResult(
            success=success,
            message=message,
            x_point={variables[i]: float(x_ing[i]) for i in range(n)},
            objective_value=float(objective(x_opt)) if success else 0.0,
            nutrient_predicted=nutrient_predicted,
            nutrient_residuals=nutrient_residuals,
            constraint_values=constraint_values,
            constraint_slacks=constraint_slacks,
            active_constraints=active_constraints,
            solver_name=f"qp_{self.method.lower()}",
            n_func_evals=result.nfev if success and hasattr(result, "nfev") else 0,
            n_iterations=result.nit if success and hasattr(result, "nit") else 0,
            solve_time_s=solve_time,
        )
