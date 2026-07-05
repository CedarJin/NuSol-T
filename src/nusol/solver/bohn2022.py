"""Bohn2022 solver — replicates the method from Bohn et al. (2022).

Key characteristics of the paper:
  - Big7 nutrients only (energy, fat, sat fat, carbs, sugar, protein, salt)
  - EU regulatory tolerance intervals (not FDA rounding)
  - Constrained least squares: min ||(Ax - b) / tolerance||²
  - Processing water as virtual ingredient when infeasible
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
from scipy.optimize import minimize, Bounds

from nusol.core.schema import SolverResult


# Big7 nutrient names as used in USDA/FNDDS
BIG7_NAMES = [
    "Energy",
    "Total lipid (fat)",
    "Fatty acids, total saturated",
    "Carbohydrate, by difference",
    "Total Sugars",
    "Protein",
    "Sodium, Na",
]

# EU tolerance rules (Table 1, Bohn et al. 2022)
# (threshold_low, threshold_high, tolerance_type, tolerance_value)
# tolerance_type: "abs" = absolute, "rel" = relative (fraction)
EU_TOLERANCE_RULES = {
    "Energy": [],  # No specific EU tolerance for energy; use ±10% as reasonable
    "Total lipid (fat)": [
        (0, 10, "abs", 1.5),
        (10, 40, "rel", 0.20),
        (40, float("inf"), "rel", 0.08),
    ],
    "Fatty acids, total saturated": [
        (0, 4, "abs", 0.6),
        (4, float("inf"), "rel", 0.20),
    ],
    "Carbohydrate, by difference": [
        (0, 10, "abs", 2.0),
        (10, 40, "rel", 0.20),
        (40, float("inf"), "rel", 0.08),
    ],
    "Total Sugars": [
        (0, 10, "abs", 2.0),
        (10, 40, "rel", 0.20),
        (40, float("inf"), "rel", 0.08),
    ],
    "Protein": [
        (0, 10, "abs", 2.0),
        (10, 40, "rel", 0.20),
        (40, float("inf"), "rel", 0.08),
    ],
    "Sodium, Na": [  # Paper uses "salt"; we use sodium
        (0, 0.5, "abs", 0.15),     # salt < 1.25g → Na < 0.5g → ±0.15g
        (0.5, float("inf"), "rel", 0.20),  # salt ≥ 1.25g → Na ≥ 0.5g → ±20%
    ],
}


def get_eu_tolerance(value_per_100g: float, nutrient_name: str) -> float:
    """Get EU regulatory tolerance for a nutrient value (per 100g)."""
    rules = EU_TOLERANCE_RULES.get(nutrient_name, [])
    for lo, hi, tol_type, tol_val in rules:
        if lo <= value_per_100g < hi:
            if tol_type == "abs":
                return tol_val
            else:  # relative
                return tol_val * value_per_100g
    # Default: ±20% or ±2 (whichever is larger)
    return max(0.20 * value_per_100g, 2.0)


class Bohn2022Solver:
    """Replicates Bohn et al. (2022) constrained least squares approach.

    Uses Big7 nutrients + EU tolerance intervals + constrained LS minimization.
    Optionally adds processing water as virtual ingredient when infeasible.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self.use_water = self.config.get("use_processing_water", True)

    def solve(
        self,
        variables: list[str],
        constraints: list[Any],
        context: dict[str, Any],
        builder: Any = None,
    ) -> SolverResult:
        n = len(variables)
        t0 = time.perf_counter()

        A = context.get("nutrient_matrix")
        nutrient_names = context.get("nutrient_names", [])
        main_indices = context.get("main_ingredient_indices", list(range(n)))

        if A is None or len(nutrient_names) == 0:
            return SolverResult(success=False, message="No nutrient matrix")

        # ── Big7: extract the subset of nutrients ──
        big7_idx = []
        big7_names = []
        for j, name in enumerate(nutrient_names):
            if name in BIG7_NAMES:
                big7_idx.append(j)
                big7_names.append(name)

        if not big7_idx:
            # Fallback: use first 7 nutrients
            big7_idx = list(range(min(7, len(nutrient_names))))
            big7_names = [nutrient_names[i] for i in big7_idx]

        A_big7 = A[:, big7_idx]
        m = len(big7_names)

        # ── Get product Big7 values from target intervals (use midpoints) ──
        target_intervals = context.get("target_intervals", {})
        b = np.zeros(m)       # target Big7 values (midpoint of interval)
        tol = np.ones(m)      # tolerance per Big7

        for j, name in enumerate(big7_names):
            interval = target_intervals.get(name)
            if interval is not None:
                lo, hi = interval
                b[j] = (lo + hi) / 2.0
                tol[j] = get_eu_tolerance(b[j], name)
            else:
                b[j] = 10.0  # fallback
                tol[j] = 2.0

        # ── Weight matrix: 1/tolerance for normalization ──
        weights = 1.0 / np.maximum(tol, 0.01)

        # ── Decision variables: [x_0..x_{n-1}, x_water] ──
        has_water = self.use_water
        nv = n + (1 if has_water else 0)

        # Objective: weighted least squares ||W·(Ax - b)||²
        def objective(x: np.ndarray) -> float:
            x_ing = x[:n]
            pred = x_ing @ A_big7
            residuals = (pred - b) * weights
            return float(np.dot(residuals, residuals))

        # Constraints
        scipy_cons = []

        # Mass balance: Σx_i + x_water = 1
        if has_water:
            scipy_cons.append({"type": "eq", "fun": lambda x: np.sum(x[:n]) + x[n] - 1.0})
        else:
            scipy_cons.append({"type": "eq", "fun": lambda x: np.sum(x[:n]) - 1.0})

        # Ingredient order: x_i >= x_{i+1} (same as paper)
        if len(main_indices) >= 2:
            for k in range(len(main_indices) - 1):
                i, j = main_indices[k], main_indices[k + 1]
                scipy_cons.append({"type": "ineq", "fun": lambda x, i=i, j=j: x[i] - x[j]})

        # Bounds: x_i ∈ [0,1], x_water ∈ [-0.5, 0.5]
        if has_water:
            bounds = Bounds([0.0]*n + [-0.5], [1.0]*n + [0.5])
            x0 = np.zeros(nv)
            x0[n] = 0.0  # water starts at 0
        else:
            bounds = Bounds([0.0]*n, [1.0]*n)
            x0 = np.zeros(nv)

        x0[:n] = 1.0 / n

        # Solve
        try:
            result = minimize(
                objective, x0, method="SLSQP",
                bounds=bounds, constraints=scipy_cons,
                options={"maxiter": 500, "ftol": 1e-8},
            )
            success = result.success
            message = result.message
            x_ing = np.clip(result.x[:n], 0.0, 1.0)
            total = x_ing.sum()
            if total > 0:
                x_ing = x_ing / total
            x_water = float(result.x[n]) if has_water else 0.0
        except Exception as e:
            success = False
            message = str(e)
            x_ing = np.ones(n) / n
            x_water = 0.0

        solve_time = time.perf_counter() - t0

        # Compute residuals
        pred_full = x_ing @ A
        nutrient_predicted = {}
        nutrient_residuals = {}
        for j, name in enumerate(nutrient_names):
            nutrient_predicted[name] = float(pred_full[j])

        return SolverResult(
            success=success,
            message=message,
            x_point={variables[i]: float(x_ing[i]) for i in range(n)},
            moisture_change=x_water,
            objective_value=float(result.fun) if success else 0.0,
            nutrient_predicted=nutrient_predicted,
            nutrient_residuals=nutrient_residuals,
            solver_name="bohn2022_ls",
            n_iterations=result.nit if success and hasattr(result, "nit") else 0,
            solve_time_s=solve_time,
        )
