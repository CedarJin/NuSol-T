"""ScipySLSQP point backend — solves CompiledProblem via SLSQP with slack variables.

Uses the proven slack-based formulation from the legacy QPSolver:
  decision vars: [x_0..x_{n-1}, s_lo_0..s_lo_{m-1}, s_hi_0..s_hi_{m-1}]
  objective: min Σ(s_lo² + s_hi²)
  constraints: Ax + s_lo >= lo, Ax - s_hi <= hi, s >= 0
  plus mass_balance, ingredient_order, and other hard constraints from IR.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import Bounds, minimize

from nusol.backends.base import PointBackend, SolveStats
from nusol.compiler.ir import CompiledProblem
from nusol.config.errors import SolveError


class ScipySLSQPBackend(PointBackend):
    """Point-estimate solver using SciPy SLSQP with slack variables.

    Reformulates soft nutrient-interval constraints as slack variables.
    Hard constraints are enforced directly as SciPy constraints.
    """

    name = "scipy_slsqp"
    capabilities = frozenset({"continuous", "linear_constraints", "soft_constraints"})

    def __init__(self, options: dict[str, Any] | None = None) -> None:
        self.options = {
            "max_iterations": 500,
            "tolerance": 1e-8,
            **(options or {}),
        }

    def solve_point(
        self,
        problem: CompiledProblem,
    ) -> tuple[dict[str, float], SolveStats]:
        t0 = time.perf_counter()
        n = problem.n_variables
        ing_ids = list(problem.ingredient_ids)

        # ── Separate constraints ──
        # Hard constraints go to SciPy directly
        # Soft interval constraints → slack variables
        A_hard = []
        lb_hard = []
        ub_hard = []
        soft_intervals: list[tuple[np.ndarray, float, float, float]] = []
        # (coefficients, lower, upper, weight)

        for lc in problem.linear_constraints:
            coeff = lc.coefficients
            if coeff.shape[0] != n:
                raise SolveError(
                    f"Constraint '{lc.id}' has wrong shape {coeff.shape}"
                )
            if lc.mode == "hard":
                A_hard.append(coeff)
                lb_hard.append(lc.lower if lc.lower is not None else -1e10)
                ub_hard.append(lc.upper if lc.upper is not None else 1e10)
            elif lc.mode == "soft":
                lo = lc.lower if lc.lower is not None else None
                hi = lc.upper if lc.upper is not None else None
                if lo is not None:
                    soft_intervals.append((coeff.copy(), lo, None, lc.weight))
                if hi is not None:
                    soft_intervals.append((coeff.copy(), None, hi, lc.weight))
                if lo is None and hi is None:
                    # No bounds — warn and skip
                    pass

        # ── Count slack variables ──
        n_slack = len(soft_intervals)
        nv = n + n_slack

        # ── Feasibility: check if there's a point satisfying all hard constraints ──
        # Use a single SLSQP solve with a zero objective to check feasibility
        n_hard = len(A_hard)

        if n_hard > 0:
            A_h = np.array(A_hard)
            lb_h = np.array(lb_hard)
            ub_h = np.array(ub_hard)

            def objective_feas(x: np.ndarray) -> float:
                return 0.0

            scipy_cons_feas = []
            for i in range(n_hard):
                row = A_h[i]
                lo, hi = lb_h[i], ub_h[i]
                if abs(lo - hi) < 1e-12:
                    scipy_cons_feas.append({
                        "type": "eq",
                        "fun": lambda x, r=row, t=lo: float(r @ x - t),
                    })
                else:
                    if lo > -1e9:
                        scipy_cons_feas.append({
                            "type": "ineq",
                            "fun": lambda x, r=row, l=lo: float(r @ x - l),
                        })
                    if hi < 1e9:
                        scipy_cons_feas.append({
                            "type": "ineq",
                            "fun": lambda x, r=row, h=hi: float(h - r @ x),
                        })

            bounds_feas = Bounds([0.0] * n, [1.0] * n)
            x0_feas = np.ones(n) / max(n, 1)

            res_feas = minimize(
                objective_feas, x0_feas,
                method="SLSQP",
                bounds=bounds_feas,
                constraints=scipy_cons_feas,
                options={"maxiter": 500, "ftol": 1e-8, "disp": False},
            )

            if not res_feas.success:
                solve_time = time.perf_counter() - t0
                raise SolveError(
                    f"Problem is INFEASIBLE: {res_feas.message}. "
                    "No point satisfies all hard constraints."
                )

            # Try a few initial guesses for better convergence
            x0_ing = res_feas.x.copy()
        else:
            x0_ing = np.ones(n) / max(n, 1)

        # ── Build full objective: min Σ(weight_i * s_i²) ──
        slack_weights = np.ones(n_slack)
        for si, (_, lo, hi, w) in enumerate(soft_intervals):
            slack_weights[si] = w

        def objective(x: np.ndarray) -> float:
            s = x[n:]
            return float(np.dot(slack_weights * s, s))

        # ── Build constraints ──
        scipy_cons = []

        # Hard constraints (same as feasibility)
        for i in range(n_hard):
            row = A_hard[i]
            lo, hi = lb_hard[i], ub_hard[i]
            if abs(lo - hi) < 1e-12:
                scipy_cons.append({
                    "type": "eq",
                    "fun": lambda x, r=row, t=lo: float(r @ x[:n] - t),
                })
            else:
                if lo > -1e9:
                    scipy_cons.append({
                        "type": "ineq",
                        "fun": lambda x, r=row, l=lo: float(r @ x[:n] - l),
                    })
                if hi < 1e9:
                    scipy_cons.append({
                        "type": "ineq",
                        "fun": lambda x, r=row, h=hi: float(h - r @ x[:n]),
                    })

        # Slack constraints: Ax + s_lo >= lo, Ax - s_hi <= hi
        slack_idx = 0
        for coeff, lo, hi, weight in soft_intervals:
            if lo is not None:
                # -Ax - s <= -lo
                scipy_cons.append({
                    "type": "ineq",
                    "fun": lambda x, c=coeff, l=lo, si=slack_idx: (
                        float(c @ x[:n]) + x[n + si] - l
                    ),
                })
                slack_idx += 1
            elif hi is not None:
                # Ax - s <= hi
                scipy_cons.append({
                    "type": "ineq",
                    "fun": lambda x, c=coeff, h=hi, si=slack_idx: (
                        float(h - c @ x[:n] + x[n + si])
                    ),
                })
                slack_idx += 1

        # Slack non-negativity
        for si in range(n_slack):
            scipy_cons.append({
                "type": "ineq",
                "fun": lambda x, si=si: x[n + si],
            })

        # Bounds: x ∈ [0, 1], slack ∈ [0, ∞)
        bounds = Bounds(
            [0.0] * n + [0.0] * n_slack,
            [1.0] * n + [1e6] * n_slack,
        )

        # Initial guess for slack variables
        x0 = np.zeros(nv)
        x0[:n] = x0_ing
        for si in range(n_slack):
            coeff, lo, hi, weight = soft_intervals[si]
            pred = float(coeff @ x0_ing)
            if lo is not None:
                x0[n + si] = max(0.0, lo - pred)
            elif hi is not None:
                x0[n + si] = max(0.0, pred - hi)

        # ── Solve ──
        try:
            result = minimize(
                objective, x0,
                method="SLSQP",
                bounds=bounds,
                constraints=scipy_cons,
                options={
                    "maxiter": self.options["max_iterations"],
                    "ftol": self.options["tolerance"],
                    "disp": False,
                },
            )

            solve_time = time.perf_counter() - t0

            x_opt = np.clip(result.x[:n], 0.0, 1.0)
            total = x_opt.sum()
            if total > 0:
                x_opt = x_opt / total

            # Verify hard constraint satisfaction
            for i in range(n_hard):
                val = A_hard[i] @ x_opt
                if val < lb_hard[i] - 1e-4 or val > ub_hard[i] + 1e-4:
                    # Hard constraint violated — try re-optimizing from a better start
                    for seed in range(10):
                        rng = np.random.default_rng(seed)
                        x0_retry = np.zeros(nv)
                        x0_retry[:n] = rng.dirichlet(np.ones(n))
                        for si, (c, lo, hi, w) in enumerate(soft_intervals):
                            pred = float(c @ x0_retry[:n])
                            if lo is not None:
                                x0_retry[n + si] = max(0.0, lo - pred)
                            elif hi is not None:
                                x0_retry[n + si] = max(0.0, pred - hi)
                        result = minimize(
                            objective, x0_retry,
                            method="SLSQP",
                            bounds=bounds,
                            constraints=scipy_cons,
                            options={
                                "maxiter": self.options["max_iterations"],
                                "ftol": self.options["tolerance"],
                                "disp": False,
                            },
                        )
                        x_opt = np.clip(result.x[:n], 0.0, 1.0)
                        total = x_opt.sum()
                        if total > 0:
                            x_opt = x_opt / total
                        all_ok = True
                        for j in range(n_hard):
                            v = A_hard[j] @ x_opt
                            if v < lb_hard[j] - 1e-4 or v > ub_hard[j] + 1e-4:
                                all_ok = False
                                break
                        if all_ok:
                            break

            if result.success:
                fractions = {ing_ids[k]: float(x_opt[k]) for k in range(n)}
                stats = SolveStats(
                    success=True,
                    status="optimal",
                    message=result.message,
                    objective_value=float(objective(result.x)),
                    iterations=result.nit if hasattr(result, "nit") else None,
                    solve_time_s=solve_time,
                )
                return fractions, stats
            else:
                raise SolveError(f"SLSQP did not converge: {result.message}")

        except SolveError:
            raise
        except Exception as e:
            solve_time = time.perf_counter() - t0
            raise SolveError(f"SLSQP solve failed: {e}") from e
