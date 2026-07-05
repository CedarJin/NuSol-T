"""Domain-level validation for IngredientProblem construction.

Rules:
  - Shape consistency: ingredient count matches composition rows
  - Nutrient existence: observation nutrients must exist in composition
  - Interval sanity: lo <= hi, non-negative
  - No NaN in observed nutrients (missing values disallowed for observed nutrients)
  - No Inf values
"""

from __future__ import annotations

import math

import numpy as np

from nusol.config.errors import CompileError, MissingNutrientError
from nusol.domain.composition import CompositionMatrix
from nusol.domain.problem import IngredientProblem


def validate_ingredient_ids_match_composition(
    ingredient_ids: list[str],
    composition: CompositionMatrix,
) -> None:
    """Check that all ingredient IDs appear in the composition."""
    comp_ids = set(composition.ingredient_ids)
    for ing_id in ingredient_ids:
        if ing_id not in comp_ids:
            raise CompileError(
                f"Ingredient '{ing_id}' has no composition data"
            )


def validate_observation_nutrients_exist(
    observation_ids: list[str],
    composition: CompositionMatrix,
) -> None:
    """Check that observation nutrients exist in the composition matrix."""
    comp_nutrients = set(composition.nutrient_ids)
    for nut_id in observation_ids:
        if nut_id not in comp_nutrients:
            raise MissingNutrientError(
                f"Observation references nutrient '{nut_id}' which is not "
                f"in the composition matrix. Available: {sorted(comp_nutrients)}"
            )


def validate_no_missing_in_observations(
    observation_ids: list[str],
    composition: CompositionMatrix,
) -> None:
    """Check that no observed nutrient has missing data for any ingredient."""
    for nut_id in observation_ids:
        missing_ingredients = composition.missing_for_nutrient(nut_id)
        if missing_ingredients:
            raise MissingNutrientError(
                f"Observed nutrient '{nut_id}' has missing values for "
                f"ingredients: {missing_ingredients}. "
                "Missing values are not allowed for observed nutrients."
            )


def validate_intervals(intervals: dict[str, tuple[float, float]]) -> None:
    """Check interval sanity."""
    for nut_id, (lo, hi) in intervals.items():
        if math.isnan(lo) or math.isnan(hi):
            raise CompileError(f"NaN interval for '{nut_id}'")
        if math.isinf(lo) or math.isinf(hi):
            raise CompileError(f"Infinite interval for '{nut_id}'")
        if lo < 0:
            raise CompileError(f"Negative interval lower bound for '{nut_id}': {lo}")
        if lo > hi:
            raise CompileError(
                f"Interval lower > upper for '{nut_id}': {lo} > {hi}"
            )


def validate_matrix(composition: CompositionMatrix) -> None:
    """Check for NaN/Inf in the composition matrix."""
    mat = composition.matrix
    if np.any(np.isinf(mat)):
        raise CompileError("Composition matrix contains Inf values")


def validate_problem(problem: IngredientProblem) -> None:
    """Run all validations on a constructed IngredientProblem."""
    ingredient_ids = [i.id for i in problem.ingredients]

    validate_ingredient_ids_match_composition(ingredient_ids, problem.composition)
    validate_matrix(problem.composition)

    all_obs_ids = list(problem.observation_intervals.keys()) + list(problem.observation_exact.keys())
    validate_observation_nutrients_exist(all_obs_ids, problem.composition)
    validate_no_missing_in_observations(all_obs_ids, problem.composition)
    validate_intervals(problem.observation_intervals)
