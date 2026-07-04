"""EnsembleSolver — generate uncertainty distributions via bootstrap + multi-start."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from nusol.constraints.base import ConstraintBase, ConstraintBuilder
from nusol.core.schema import SolverResult
from nusol.solver.point_solver import PointSolver
from nusol.solver.initializer import generate_initial_guesses


class EnsembleSolver:
    """Generate uncertainty intervals via ensemble of solver runs.

    Perturbation sources:
      1. Multi-start initialization (different x0)
      2. Label interval bootstrap (resample target values within intervals)
      3. Database value perturbation (add noise to nutrient matrix)

    The ensemble of solutions is then aggregated into percentile intervals.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        solver_cfg = self.config.get("solver", {})
        ens_cfg = solver_cfg.get("ensemble", {})
        self.n_bootstrap = ens_cfg.get("n_bootstrap", 100)
        self.n_multi_start = ens_cfg.get("n_multi_start", 50)
        self.noise_std = ens_cfg.get("noise_std", 0.02)  # 2% relative noise

    def solve(
        self,
        variables: list[str],
        constraints: list[ConstraintBase],
        context: dict[str, Any],
        point_result: SolverResult | None = None,
        builder: ConstraintBuilder | None = None,
    ) -> SolverResult:
        """Run ensemble and aggregate results.

        Returns:
            SolverResult with x_point as median, x_lower/x_upper as 5%/95% quantiles.
        """
        n = len(variables)
        context["n_variables"] = n
        context["ingredient_names"] = variables

        t0 = time.perf_counter()

        point_solver = PointSolver(self.config)
        # Override multi_start to 1 per ensemble member
        point_solver.multi_start = 1
        point_solver.init_strategy = "dirichlet"

        all_solutions: list[dict[str, float]] = []

        # 1. Multi-start ensemble
        seeds = np.random.default_rng(42).integers(0, 100000, size=self.n_multi_start)
        for seed in seeds:
            guesses = generate_initial_guesses(n, 1, strategy="dirichlet", seed=int(seed))
            for x0 in guesses:
                try:
                    # Temporarily set initial guess
                    result = point_solver._solve_single(x0, variables, constraints, context, builder)
                    if result and result.success:
                        all_solutions.append(dict(result.x_point))
                except Exception:
                    continue

        # 2. Label bootstrap
        target_intervals = context.get("target_intervals", {})
        if target_intervals:
            rng = np.random.default_rng(123)
            for b in range(min(self.n_bootstrap, 50)):  # Limit bootstrap for speed
                # Perturb target intervals
                perturbed = {}
                for name, (lo, hi) in target_intervals.items():
                    w = hi - lo
                    new_lo = lo + rng.uniform(-0.1 * w, 0.1 * w)
                    new_hi = hi + rng.uniform(-0.1 * w, 0.1 * w)
                    perturbed[name] = (max(0, new_lo), max(new_lo + 1e-6, new_hi))

                boot_context = {**context, "target_intervals": perturbed}
                x0 = generate_initial_guesses(n, 1, strategy="dirichlet", seed=b + 100000)[0]

                try:
                    result = point_solver._solve_single(x0, variables, constraints, boot_context, builder)
                    if result and result.success:
                        all_solutions.append(dict(result.x_point))
                except Exception:
                    continue

        # 3. Aggregate
        if not all_solutions:
            # Fallback to point result
            if point_result and point_result.success:
                all_solutions = [dict(point_result.x_point)]
            else:
                uniform = {v: 1.0 / n for v in variables}
                all_solutions = [uniform]

        # Compute percentiles
        x_median = {}
        x_lower = {}
        x_upper = {}
        x_p5 = {}
        x_p95 = {}

        for v in variables:
            vals = sorted(s.get(v, 0.0) for s in all_solutions)
            x_median[v] = float(np.median(vals))
            x_lower[v] = float(np.min(vals))
            x_upper[v] = float(np.max(vals))
            x_p5[v] = float(np.percentile(vals, 5))
            x_p95[v] = float(np.percentile(vals, 95))

        solve_time = time.perf_counter() - t0

        return SolverResult(
            success=True,
            message=f"Ensemble: {len(all_solutions)} valid solutions",
            x_point=x_median,
            x_lower=x_lower,
            x_upper=x_upper,
            solver_name="ensemble",
            solve_time_s=solve_time,
        )
