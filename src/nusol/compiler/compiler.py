"""ConstraintCompiler — IngredientProblem → CompiledProblem via constraint registry."""

from __future__ import annotations

from dataclasses import replace
from typing import Literal, cast

from nusol.compiler.ir import (
    CompiledProblem,
    LinearConstraintIR,
    QuadraticPenaltyIR,
    VariableIR,
)
from nusol.config.errors import UnsupportedConstraintError
from nusol.constraints.registry import get_constraint_registry
from nusol.domain.problem import IngredientProblem


def compile_problem(problem: IngredientProblem) -> CompiledProblem:
    """Compile an IngredientProblem into solver-neutral IR.

    Args:
        problem: Validated IngredientProblem.
        constraint_configs: Optional dict of {constraint_id: config} from YAML.
            If None, uses default config for each enabled constraint.

    Returns:
        A CompiledProblem ready for backend capability check and solving.

    Raises:
        UnsupportedConstraintError: If an enabled constraint type is not registered.
    """
    n_ingredients = problem.n_ingredients
    n_vars = n_ingredients  # No slack/moisture variables in IR (added by backend)

    ingredient_ids = problem.ingredient_ids
    nutrient_ids = list(problem.nutrient_ids)
    matrix = problem.to_array()
    constraint_configs = problem.constraint_configs

    # Initialize IR components
    variables = tuple(
        VariableIR(
            id=ing.id,
            lower=problem.variable_lower,
            upper=problem.variable_upper,
        )
        for ing in problem.ingredients
    )

    linear_constraints: list[LinearConstraintIR] = []
    quadratic_penalties: list[QuadraticPenaltyIR] = []

    registry = get_constraint_registry()

    # Process nutrient_interval constraints from observations.
    # Use mode/weight from the YAML constraint if declared.
    default_nu_mode: Literal["hard", "soft"] = "soft"
    default_nu_weight = 10.0
    nu_mode: Literal["hard", "soft"] = default_nu_mode
    nu_weight = default_nu_weight
    nu_source_id: str | None = None
    # Look for a nutrient_interval-type constraint in the YAML config
    for c_id, c_info in constraint_configs.items():
        if c_info.get("type") == "nutrient_interval":
            nu_mode = cast(
                Literal["hard", "soft"], c_info.get("mode", default_nu_mode)
            )
            nu_weight = c_info.get("weight", default_nu_weight)
            nu_source_id = c_id
            break

    for nut_id, (lo, hi) in problem.observation_intervals.items():
        j = nutrient_ids.index(nut_id)
        coeff_lo = -matrix[:, j].copy()
        coeff_hi = matrix[:, j].copy()

        linear_constraints.append(
            LinearConstraintIR(
                id=f"nu_lo_{nut_id}",
                coefficients=coeff_lo,
                upper=-lo,
                mode=nu_mode,
                weight=nu_weight,
                source_id=nu_source_id,
            ),
        )
        linear_constraints.append(
            LinearConstraintIR(
                id=f"nu_hi_{nut_id}",
                coefficients=coeff_hi,
                upper=hi,
                mode=nu_mode,
                weight=nu_weight,
                source_id=nu_source_id,
            ),
        )

    for nut_id, val in problem.observation_exact.items():
        j = nutrient_ids.index(nut_id)
        coeff = matrix[:, j].copy()
        linear_constraints.append(
            LinearConstraintIR(
                id=f"nu_eq_{nut_id}",
                coefficients=coeff,
                lower=val,
                upper=val,
                mode=nu_mode,
                weight=nu_weight,
                source_id=nu_source_id,
            ),
        )

    # Process registered constraints from constraint_ids
    for c_id in problem.constraint_ids:
        # Look up type from problem.constraint_types
        c_type = problem.constraint_types.get(c_id)
        if c_type is None:
            c_type = constraint_configs.get(c_id, {}).get("type")

        if c_type is None:
            raise UnsupportedConstraintError(
                f"Constraint '{c_id}' has no type specified. "
                "Ensure it is passed via constraint_types or constraint_configs."
            )

        # Observation intervals are compiled above because they need the
        # composition matrix. Do not invoke the marker-only builtin again.
        if c_type == "nutrient_interval":
            continue

        # Handle plugin constraints (type: plugin → look up actual name in config)
        plugin_name = c_type
        plugin_version = None
        if c_type == "plugin":
            c_cfg = problem.constraint_configs.get(c_id, {})
            plugin_name = c_cfg.get("config", {}).get("plugin", "")
            plugin_version = c_cfg.get("config", {}).get("version", None)
            if not plugin_name:
                raise UnsupportedConstraintError(
                    f"Constraint '{c_id}' type='plugin' but no 'plugin' name in config"
                )

        if not registry.has(plugin_name):
            raise UnsupportedConstraintError(
                f"Constraint '{c_id}' has unknown type/plugin '{plugin_name}'. "
                f"Available types: {registry.names()}"
            )

        plugin = registry.get(plugin_name)

        # Version check if specified in YAML
        if plugin_version and plugin.version != plugin_version:
            raise UnsupportedConstraintError(
                f"Constraint '{c_id}' requires plugin '{plugin_name}' version "
                f"'{plugin_version}' but installed version is '{plugin.version}'"
            )

        cfg = problem.constraint_configs.get(c_id, {})
        validated_params = plugin.validate_params(cfg.get("config", {}))
        # Pass ingredient group metadata so constraints can be declaration-aware
        validated_params["_ingredient_groups"] = [
            ing.declaration_group for ing in problem.ingredients
        ]
        ir_fragments = plugin.compile(
            validated_params, ingredient_ids, nutrient_ids, n_vars,
        )
        for frag in ir_fragments:
            if isinstance(frag, LinearConstraintIR):
                linear_constraints.append(
                    replace(
                        frag,
                        mode=cfg.get("mode", "hard"),
                        weight=cfg.get("weight", 1.0),
                        source_id=c_id,
                    )
                )
            elif isinstance(frag, QuadraticPenaltyIR):
                quadratic_penalties.append(
                    replace(
                        frag,
                        weight=cfg.get("weight", 1.0),
                        source_id=c_id,
                    )
                )
            else:
                raise UnsupportedConstraintError(
                    f"Constraint '{c_id}' returned unsupported IR fragment "
                    f"{type(frag).__name__}"
                )

    # Build CompiledProblem
    compiled = CompiledProblem(
        variables=variables,
        linear_constraints=tuple(linear_constraints),
        quadratic_penalties=tuple(quadratic_penalties),
        ingredient_ids=tuple(ingredient_ids),
        nutrient_ids=tuple(nutrient_ids),
    )

    return compiled
