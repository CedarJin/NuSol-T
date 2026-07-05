"""IngredientProblem — the typed domain model that replaces ``context dict``."""

from __future__ import annotations

import numpy as np
from pydantic import BaseModel, Field

from nusol.domain.composition import CompositionMatrix
from nusol.domain.ingredient import Ingredient


class IngredientProblem(BaseModel):
    """A fully-specified ingredient estimation problem.

    This is the typed domain model that replaces the legacy ``context: dict[str, Any]``.
    """

    model_config = {"arbitrary_types_allowed": True}

    problem_id: str = Field(..., description="Unique problem identifier")
    ingredients: tuple[Ingredient, ...] = Field(..., description="Ordered list of ingredients")
    composition: CompositionMatrix = Field(..., description="Ingredient × nutrient matrix")
    observation_nutrient_ids: tuple[str, ...] = Field(
        ..., description="Nutrient IDs with observations",
    )
    observation_intervals: dict[str, tuple[float, float]] = Field(
        default_factory=dict,
        description="Nutrient → (lo, hi) interval for each observed nutrient",
    )
    observation_exact: dict[str, float] = Field(
        default_factory=dict,
        description="Nutrient → exact value for each observed nutrient",
    )
    constraint_ids: tuple[str, ...] = Field(
        default_factory=tuple,
        description="IDs of enabled constraints",
    )
    constraint_types: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping from constraint ID → type name (e.g. {'total_mass': 'mass_balance'})",
    )
    constraint_configs: dict[str, dict] = Field(
        default_factory=dict,
        description="Mapping from constraint ID → configuration dict",
    )
    prior_ids: tuple[str, ...] = Field(
        default_factory=tuple,
        description="IDs of enabled priors",
    )
    variable_lower: float = 0.0
    variable_upper: float = 1.0

    @property
    def n_ingredients(self) -> int:
        return len(self.ingredients)

    @property
    def n_nutrients(self) -> int:
        return len(self.composition.nutrient_ids)

    @property
    def ingredient_ids(self) -> list[str]:
        return [i.id for i in self.ingredients]

    @property
    def nutrient_ids(self) -> tuple[str, ...]:
        return self.composition.nutrient_ids

    def to_array(self) -> np.ndarray:
        """Return the composition matrix as a numpy array (n_ingredients × n_nutrients)."""
        return self.composition.matrix

    def __repr__(self) -> str:
        return (
            f"IngredientProblem({self.problem_id}: "
            f"{self.n_ingredients} ingr × {self.n_nutrients} nu, "
            f"{len(self.observation_intervals) + len(self.observation_exact)} obs)"
        )
