"""QPBoundSolver — feasible bounds via linear programming for each variable.

For each ingredient i:
  minimize x_i  (or maximize = minimize -x_i)
  subject to linear constraints (mass balance, order, label intervals).

Uses scipy.optimize.linprog (HiGHS simplex) for speed — each bound solves in ~1-5ms.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import linprog

from nusol.constraints.base import ConstraintBase, ConstraintBuilder
from nusol.core.schema import SolverResult


class BoundSolver:
    """Compute feasible lower/upper bounds via linear programming.

    Each bound is an LP with linear objective (x_i or -x_i) and linear constraints.
    Solved with HiGHS simplex in ~1-5ms per bound.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        solver_cfg = self.config.get("solver", self.config)
        self.method = solver_cfg.get("lp_method", "highs")

    def solve(
        self,
        variables: list[str],
        constraints: list[ConstraintBase],
        context: dict[str, Any],
        point_result: SolverResult | None = None,
        builder: ConstraintBuilder | None = None,
    ) -> SolverResult:
        n = len(variables)
        context["n_variables"] = n
        context["ingredient_names"] = variables

        t0 = time.perf_counter()

        A_mat = context.get("nutrient_matrix")
        nutrient_names = context.get("nutrient_names", [])
        target_intervals = context.get("target_intervals", {})
        main_indices = context.get("main_ingredient_indices", list(range(n)))

        if A_mat is None:
            return SolverResult(success=False, message="No nutrient matrix")

        m = len(nutrient_names)
        lo = np.zeros(m)
        hi = np.full(m, 1e9)
        for j, name in enumerate(nutrient_names):
            interval = target_intervals.get(name)
            if interval is not None:
                lo[j] = interval[0]
                hi[j] = interval[1]

        # ── Build LP constraints in standard form: A_ub @ x <= b_ub, A_eq @ x = b_eq ──
        # Variables: [x_0..x_{n-1}]

        # Equality: sum(x) = 1
        A_eq = np.ones((1, n))
        b_eq = np.array([1.0])

        # Inequality constraints:
        # 1. Order: x_i - x_{i+1} >= 0  →  -x_i + x_{i+1} <= 0
        # 2. Label lower: pred + s >= lo → -(x @ A[:,j]) <= -lo[j]  (no slack in LP → hard feat)
        #    Actually: x @ A[:,j] >= lo[j] → -x @ A[:,j] <= -lo[j]
        # 3. Label upper: x @ A[:,j] <= hi[j]

        A_ub_rows = []
        b_ub_vals = []

        # Order: -x_i + x_{i+1} <= 0
        if len(main_indices) >= 2:
            for k in range(len(main_indices) - 1):
                i, j = main_indices[k], main_indices[k + 1]
                row = np.zeros(n)
                row[i] = -1.0
                row[j] = 1.0
                A_ub_rows.append(row)
                b_ub_vals.append(0.0)

        # Label lower: -x @ A[:,j] <= -lo[j]
        for j in range(m):
            row = -A_mat[:, j].copy()
            A_ub_rows.append(row)
            b_ub_vals.append(-lo[j])

        # Label upper: x @ A[:,j] <= hi[j]
        for j in range(m):
            row = A_mat[:, j].copy()
            A_ub_rows.append(row)
            b_ub_vals.append(hi[j])

        A_ub = np.array(A_ub_rows) if A_ub_rows else np.zeros((0, n))
        b_ub = np.array(b_ub_vals)

        # Bounds: x_i ∈ [0, 1]
        bounds = [(0.0, 1.0) for _ in range(n)]

        # ── Solve each bound ──
        x_lower = {}
        x_upper = {}

        for i in range(n):
            # Lower bound: minimize x_i
            c = np.zeros(n)
            c[i] = 1.0
            try:
                res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                              bounds=bounds, method=self.method)
                if res.success:
                    x_lower[variables[i]] = float(np.clip(res.x[i], 0.0, 1.0))
                else:
                    x_lower[variables[i]] = 0.0
            except Exception:
                x_lower[variables[i]] = 0.0

            # Upper bound: maximize x_i = minimize -x_i
            c = np.zeros(n)
            c[i] = -1.0
            try:
                res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                              bounds=bounds, method=self.method)
                if res.success:
                    x_upper[variables[i]] = float(np.clip(res.x[i], 0.0, 1.0))
                else:
                    x_upper[variables[i]] = 1.0
            except Exception:
                x_upper[variables[i]] = 1.0

        solve_time = time.perf_counter() - t0

        return SolverResult(
            success=True,
            message=f"Bounds for {n} vars via LP ({self.method})",
            x_lower=x_lower,
            x_upper=x_upper,
            solver_name=f"lp_{self.method}_bound",
            solve_time_s=solve_time,
        )
