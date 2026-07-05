"""Nutrient interval constraint: lo <= Ax <= hi for observed nutrients.

Each observed nutrient generates two half-inequalities:
  -lower: A[j]·x >= lo[j]  →  -A[j]·x <= -lo[j]
  -upper:  A[j]·x <= hi[j]
"""
from __future__ import annotations

import numpy as np

from nusol.compiler.ir import LinearConstraintIR, QuadraticPenaltyIR


def register(registry) -> None:
    @registry.register(
        "nutrient_interval",
        capabilities=frozenset({"linear_constraints", "quadratic_objective"}),
    )
    def compile_nutrient_interval(params, ing_ids, nut_ids, n_vars):
        """Generate interval constraints for observed nutrients.

        Params:
          intervals: {nutrient_id: [lo, hi]}
          loss: "squared_hinge" (default) — penalize only violation
                "least_squares" — penalize distance from midpoint
          weight: weight for soft constraints
        """
        intervals = params.get("intervals", {})
        loss = params.get("loss", "squared_hinge")
        weight = params.get("weight", 1.0)
        mode = params.get("mode", "soft")

        result: list = []

        for nut_id, (lo, hi) in intervals.items():
            if nut_id not in nut_ids:
                raise ValueError(
                    f"nutrient_interval references '{nut_id}' "
                    f"which is not in the composition matrix"
                )
            j = nut_ids.index(nut_id)

            if mode == "hard":
                # Hard interval: lo <= A[j]·x <= hi
                coeff = np.zeros(n_vars)
                coeff[:] = 0.0  # Will be filled by compiler with A[:, j]
                # These are placeholder — the compiler fills in the matrix coefficients
                result.append(
                    LinearConstraintIR(
                        id=f"nu_lo_{nut_id}",
                        coefficients=np.array([j]),  # marker for compiler
                        lower=lo,
                        mode="hard",
                    ),
                )
                result.append(
                    LinearConstraintIR(
                        id=f"nu_hi_{nut_id}",
                        coefficients=np.array([j]),
                        upper=hi,
                        mode="hard",
                    ),
                )
            elif loss == "squared_hinge":
                # Slack-based: min Σs², s.t. Ax + s >= lo, Ax - s <= hi
                # This is handled by the compiler by adding slack variables
                # For now, just generate the base constraints
                result.append(
                    LinearConstraintIR(
                        id=f"nu_lo_{nut_id}",
                        coefficients=np.array([j]),
                        lower=lo,
                        mode="soft",
                        weight=weight,
                    ),
                )
                result.append(
                    LinearConstraintIR(
                        id=f"nu_hi_{nut_id}",
                        coefficients=np.array([j]),
                        upper=hi,
                        mode="soft",
                        weight=weight,
                    ),
                )

        return result
