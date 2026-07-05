"""HighsLP bounds backend — feasible bounds via HiGHS simplex.

FIXES legacy BoundSolver bug F0.2: infeasible → success=False.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import linprog

from nusol.backends.base import BoundsBackend, SolveStats
from nusol.compiler.ir import CompiledProblem
from nusol.config.errors import SolveError


class HighsLPBackend(BoundsBackend):
    """Feasible-bounds solver using HiGHS simplex (via scipy.optimize.linprog).

    Computes the feasible minimum and maximum for each variable subject to
    HARD constraints only (soft constraints are not included in bounds).

    Capabilities: continuous, linear_constraints.
    Does NOT support soft constraints or quadratic objectives.

    Key fix over legacy BoundSolver:
    - Infeasible problem → SolveError raised (not success=True with [0,1] bounds)
    - Each bound LP independently may fail → reported in per-variable status
    """

    name = "highs_lp"
    capabilities = frozenset({"continuous", "linear_constraints"})

    def __init__(self, options: dict[str, Any] | None = None) -> None:
        self.options = options or {}

    def solve_bounds(
        self,
        problem: CompiledProblem,
    ) -> tuple[dict[str, tuple[float, float]], SolveStats]:
        t0 = time.perf_counter()
        n = problem.n_variables
        ing_ids = list(problem.ingredient_ids)

        # ── Build LP in standard form: A_ub @ x <= b_ub, A_eq @ x = b_eq ──

        A_ub_rows: list[np.ndarray] = []
        b_ub_vals: list[float] = []

        A_eq_rows: list[np.ndarray] = []
        b_eq_vals: list[float] = []

        for lc in problem.linear_constraints:
            coeff = lc.coefficients
            if coeff.shape[0] != n:
                raise SolveError(
                    f"Constraint '{lc.id}' has wrong shape {coeff.shape}"
                )

            if lc.mode != "hard":
                continue  # Soft constraints don't enter bounds

            lo = lc.lower if lc.lower is not None else -1e10
            hi = lc.upper if lc.upper is not None else 1e10

            if abs(lo - hi) < 1e-12:
                # Equality
                A_eq_rows.append(coeff)
                b_eq_vals.append(lo)
            else:
                # Lower: A @ x >= lo  →  -A @ x <= -lo
                if lo > -1e9:
                    A_ub_rows.append(-coeff)
                    b_ub_vals.append(-lo)
                # Upper: A @ x <= hi
                if hi < 1e9:
                    A_ub_rows.append(coeff)
                    b_ub_vals.append(hi)

        A_ub = np.array(A_ub_rows) if A_ub_rows else np.zeros((0, n))
        b_ub = np.array(b_ub_vals)
        A_eq = np.array(A_eq_rows) if A_eq_rows else np.zeros((0, n))
        b_eq = np.array(b_eq_vals)

        bounds = [(0.0, 1.0) for _ in range(n)]

        # ── Feasibility check: solve a dummy LP first ──
        # If no feasible point exists, all bound LPs will fail.
        # We check once upfront to give a clear error.
        c_dummy = np.zeros(n)
        feas_res = linprog(
            c_dummy, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
            bounds=bounds, method="highs",
        )
        if not feas_res.success:
            solve_time = time.perf_counter() - t0
            raise SolveError(
                f"Problem is INFEASIBLE: {feas_res.message}. "
                "No point satisfies all hard constraints."
            )

        # ── Solve each bound ──
        bounds_dict: dict[str, tuple[float, float]] = {}
        n_failed = 0

        for i, ing_id in enumerate(ing_ids):
            # Lower bound: minimize x_i
            c = np.zeros(n)
            c[i] = 1.0
            res_lo = linprog(
                c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                bounds=bounds, method="highs",
            )
            if res_lo.success:
                lo = float(np.clip(res_lo.x[i], 0.0, 1.0))
            else:
                lo = 0.0
                n_failed += 1

            # Upper bound: maximize x_i = minimize -x_i
            c = np.zeros(n)
            c[i] = -1.0
            res_hi = linprog(
                c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                bounds=bounds, method="highs",
            )
            if res_hi.success:
                hi = float(np.clip(res_hi.x[i], 0.0, 1.0))
            else:
                hi = 1.0
                n_failed += 1

            bounds_dict[ing_id] = (lo, hi)

        solve_time = time.perf_counter() - t0

        all_success = n_failed == 0
        stats = SolveStats(
            success=all_success,
            status="optimal" if all_success else "partial",
            message=(
                f"Bounds for {n} vars, {n_failed} bound LP(s) failed"
                if n_failed > 0
                else f"Bounds for {n} vars via LP"
            ),
            solve_time_s=solve_time,
        )

        return bounds_dict, stats
