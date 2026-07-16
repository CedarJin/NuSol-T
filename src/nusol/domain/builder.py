"""ProblemBuilder — converts a validated SolveDocument into an IngredientProblem."""

from __future__ import annotations

from pathlib import Path

from nusol.config.schema import (
    InlineCompositionSpec,
    SolveDocument,
)
from nusol.domain.composition import CompositionMatrix
from nusol.domain.ingredient import Ingredient
from nusol.domain.problem import IngredientProblem
from nusol.domain.validation import validate_problem


def build_problem(
    doc: SolveDocument,
    base_dir: str | Path | None = None,
) -> IngredientProblem:
    """Build an IngredientProblem from a validated SolveDocument.

    Args:
        doc: A validated SolveDocument (already parsed and schema-checked).

    Returns:
        A fully-validated IngredientProblem ready for compilation.

    Raises:
        CompileError: If domain-level validation fails.
    """
    # 1. Build ingredients
    ingredients = tuple(
        Ingredient(
            id=ing.id,
            name=ing.name,
            declaration_position=ing.declaration_position,
            declaration_group=ing.declaration_group.value,
        )
        for ing in doc.ingredients
    )
    ingredient_ids = [i.id for i in ingredients]

    # 2. Build composition matrix
    nutrient_ids = [n.id for n in doc.composition.nutrients]
    units = [n.unit for n in doc.composition.nutrients]

    comp = doc.composition
    if isinstance(comp, InlineCompositionSpec):
        composition = CompositionMatrix.from_inline_dict(
            values=comp.values,
            ingredient_ids=ingredient_ids,
            nutrient_ids=nutrient_ids,
            units=units,
        )
    else:
        # CSV source — load from file path with YAML ingredient order (R0.1)
        csv_path = Path(comp.path)
        if not csv_path.is_absolute() and base_dir is not None:
            csv_path = Path(base_dir) / csv_path
        composition = CompositionMatrix.from_csv(
            path=csv_path,
            key_column=comp.key_column,
            missing_value_policy=comp.missing_value_policy.value,
            yaml_ingredient_ids=ingredient_ids,
            yaml_nutrient_ids=nutrient_ids,
            yaml_units=units,
            allow_extra_nutrients=comp.allow_extra_nutrients,
            sha256=comp.sha256,
        )

    # 3. Build observations
    intervals: dict[str, tuple[float, float]] = {}
    exact: dict[str, float] = {}

    for obs in doc.observations:
        nut_id = obs.nutrient
        if obs.interval is not None:
            intervals[nut_id] = (obs.interval[0], obs.interval[1])
        elif obs.exact is not None:
            exact[nut_id] = obs.exact
        # less_than: convert to interval [0, val]
        elif obs.less_than is not None:
            intervals[nut_id] = (0.0, obs.less_than)

    # 4. Build constraint/prior IDs
    enabled_constraints = [c for c in doc.constraints if c.enabled]
    constraint_ids = tuple(c.id for c in enabled_constraints)
    constraint_types = {c.id: c.type for c in enabled_constraints}
    constraint_configs = {
        c.id: {
            "type": c.type,
            "mode": c.mode.value,
            "weight": c.weight,
            "config": c.config,
        }
        for c in enabled_constraints
    }
    enabled_priors = [p for p in doc.priors if p.enabled]
    prior_ids = tuple(p.id for p in enabled_priors)
    prior_types = {p.id: p.type for p in enabled_priors}
    prior_configs = {
        p.id: {
            "type": p.type,
            "weight": p.weight,
            "config": p.config,
            "evidence": p.evidence.model_dump(mode="json"),
        }
        for p in enabled_priors
    }

    # 5. Assemble problem
    problem = IngredientProblem(
        problem_id=doc.problem_id,
        ingredients=ingredients,
        composition=composition,
        observation_nutrient_ids=tuple(intervals.keys()) + tuple(exact.keys()),
        observation_intervals=intervals,
        observation_exact=exact,
        constraint_ids=constraint_ids,
        constraint_types=constraint_types,
        constraint_configs=constraint_configs,
        prior_ids=prior_ids,
        prior_types=prior_types,
        prior_configs=prior_configs,
        variable_lower=doc.variables.ingredient_fractions.lower,
        variable_upper=doc.variables.ingredient_fractions.upper,
    )

    # 6. Validate
    validate_problem(problem)

    return problem
