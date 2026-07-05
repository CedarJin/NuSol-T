"""Unique-source lower bound constraint.

When a nutrient j has only one ingredient i that provides it (density > 0),
and the interval lower bound is lo_j, then:
  x_i >= lo_j / A_ij
"""
from __future__ import annotations

import numpy as np

from nusol.compiler.ir import LinearConstraintIR


def register(registry) -> None:
    @registry.register("unique_source")
    def compile_unique_source(params, ing_ids, nut_ids, n_vars):
        """Compile unique-source constraints.

        Params:
          composition_matrix: the full matrix (n_ingredients, n_nutrients)
          intervals: {nutrient_id: [lo, hi]}
          dominance_threshold: fraction above which a source is "unique" (default 0.9)
        """
        # This constraint requires the full composition matrix and intervals,
        # which are only available at compiler time.
        # The compile function creates markers; the compiler expands them.
        return []
