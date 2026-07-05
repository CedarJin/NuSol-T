"""QPBoundSolver — feasible bounds via QP solve for each variable.

For each ingredient i:
  minimize x_i  (or maximize = minimize -x_i)
  subject to the same QP constraints as QPSolver

This gives the feasible range for each ingredient under all hard constraints.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import Bounds, minimize

from nusol.constraints.base import ConstraintBase, ConstraintBuilder
from nusol.core.schema import SolverResult


class BoundSolver:
    """Compute feasible lower/upper bounds for each ingredient via QP.

    Each bound solve is a linear program (linear objective + linear constraints)
    solvable in ~10ms by SLSQP.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        solver_cfg = self.config.get("solver", self.config)
        self.method = solver_cfg.get("qp_method", "SLSQP")
        self.max_iter = solver_cfg.get("max_iter", 300)
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
            constraints: Constraint list (unused; QP builds its own).
            context: Problem context.
            point_result: Optional point solution (used as warm start).
            builder: Unused.

        Returns:
            SolverResult with x_lower and x_upper dicts.
        """
        n = len(variables)
        context["n_variables"] = n
        context["ingredient_names"] = variables

        t0 = time.perf_counter()

        A = context.get("nutrient_matrix")
        nutrient_names = context.get("nutrient_names", [])
        target_intervals = context.get("target_intervals", {})
        main_indices = context.get("main_ingredient_indices", list(range(n)))

        if A is None:
            return SolverResult(success=False, message="No nutrient matrix")

        m = len(nutrient_names)
        lo = np.zeros(m)
        hi = np.full(m, 1e9)
        for j, name in enumerate(nutrient_names):
            interval = target_intervals.get(name)
            if interval is not None:
                lo[j] = interval[0]
                hi[j] = interval[1]

        nv = n + 2 * m

        # Warm start: use point result if available
        x0_base = np.zeros(nv)
        if point_result and point_result.success:
            for i, v in enumerate(variables):
                x0_base[i] = point_result.x_point.get(v, 1.0 / n)
        else:
            x0_base[:n] = 1.0 / n

        for j in range(m):
            pred = float(np.dot(x0_base[:n], A[:, j]))
            x0_base[n + j] = max(0.0, lo[j] - pred)
            x0_base[n + m + j] = max(0.0, pred - hi[j])

        # ── Build shared constraints (same as QPSolver) ──
        scipy_cons = [{"type": "eq", "fun": lambda x: np.sum(x[:n]) - 1.0}]

        if len(main_indices) >= 2:
            for k in range(len(main_indices) - 1):
                i_idx, j_idx = main_indices[k], main_indices[k + 1]
                scipy_cons.append({
                    "type": "ineq",
                    "fun": lambda x, i=i_idx, j=j_idx: x[i] - x[j],
                })

        for j in range(m):
            scipy_cons.append({
                "type": "ineq",
                "fun": lambda x, j=j: float(np.dot(x[:n], A[:, j])) + x[n + j] - lo[j],
            })
            scipy_cons.append({
                "type": "ineq",
                "fun": lambda x, j=j: hi[j] - float(np.dot(x[:n], A[:, j])) + x[n + m + j],
            })

        for j in range(2 * m):
            scipy_cons.append({"type": "ineq", "fun": lambda x, j=j: x[n + j]})

        bounds = Bounds([0.0] * nv, [1.0] * n + [1e6] * (2 * m))

        # Light slack penalty to keep solution feasible
        def slack_penalty(x: np.ndarray) -> float:
            s_lo = x[n : n + m]
            s_hi = x[n + m : n + 2 * m]
            return 1e-6 * float(np.dot(s_lo, s_lo) + np.dot(s_hi, s_hi))

        x_lower = {}
        x_upper = {}

        for i in range(n):
            # ── Lower bound: minimize x_i ──
            def obj_min(x, i=i):
                return x[i] + slack_penalty(x)

            try:
                res = minimize(
                    obj_min, x0_base, method=self.method,
                    bounds=bounds, constraints=scipy_cons,
                    options={"maxiter": self.max_iter, "ftol": self.tolerance},
                )
                if res.success:
                    x_lower[variables[i]] = float(np.clip(res.x[i], 0.0, 1.0))
                else:
                    x_lower[variables[i]] = float(np.clip(x0_base[i], 0.0, 1.0))
            except Exception:
                x_lower[variables[i]] = float(np.clip(x0_base[i], 0.0, 1.0))

            # ── Upper bound: minimize -x_i ──
            def obj_max(x, i=i):
                return -x[i] + slack_penalty(x)

            try:
                res = minimize(
                    obj_max, x0_base, method=self.method,
                    bounds=bounds, constraints=scipy_cons,
                    options={"maxiter": self.max_iter, "ftol": self.tolerance},
                )
                if res.success:
                    x_upper[variables[i]] = float(np.clip(res.x[i], 0.0, 1.0))
                else:
                    x_upper[variables[i]] = float(np.clip(x0_base[i], 0.0, 1.0))
            except Exception:
                x_upper[variables[i]] = float(np.clip(x0_base[i], 0.0, 1.0))

        solve_time = time.perf_counter() - t0

        return SolverResult(
            success=True,
            message=f"Bounds computed for {n} variables via QP",
            x_lower=x_lower,
            x_upper=x_upper,
            solver_name=f"qp_{self.method.lower()}_bound",
            solve_time_s=solve_time,
        )
