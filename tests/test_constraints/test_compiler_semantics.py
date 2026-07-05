from __future__ import annotations

import numpy as np

from nusol.compiler.compiler import compile_problem
from nusol.compiler.ir import QuadraticPenaltyIR
from nusol.config.loader import ConfigLoader
from nusol.constraints.registry import get_constraint_registry
from nusol.domain.builder import build_problem


def test_generic_constraint_mode_weight_and_source_are_preserved() -> None:
    doc = ConfigLoader().load_from_path("examples/bread_minimal.yaml")
    constraint_type = type(doc.constraints[0])
    doc.constraints.append(
        constraint_type(
            id="oil_limit",
            type="linear_expression",
            mode="soft",
            weight=7.0,
            config={"coefficients": {"oil": 1.0}, "upper": 0.2},
        )
    )

    compiled = compile_problem(build_problem(doc))
    constraint = next(
        item for item in compiled.linear_constraints if item.source_id == "oil_limit"
    )

    assert constraint.mode == "soft"
    assert constraint.weight == 7.0


def test_quadratic_plugin_fragment_is_preserved() -> None:
    registry = get_constraint_registry()
    name = "test_quadratic_penalty"
    if not registry.has(name):
        @registry.register(name, capabilities=frozenset({"quadratic_objective"}))
        def compile_quadratic(params, ingredient_ids, nutrient_ids, n_vars):
            return [
                QuadraticPenaltyIR(
                    id="quadratic",
                    quadratic=np.eye(n_vars),
                    linear=np.zeros(n_vars),
                )
            ]

    doc = ConfigLoader().load_from_path("examples/bread_minimal.yaml")
    constraint_type = type(doc.constraints[0])
    doc.constraints.append(
        constraint_type(
            id="quadratic_prior",
            type=name,
            mode="soft",
            weight=3.0,
        )
    )

    compiled = compile_problem(build_problem(doc))

    assert len(compiled.quadratic_penalties) == 1
    assert compiled.quadratic_penalties[0].source_id == "quadratic_prior"
    assert compiled.quadratic_penalties[0].weight == 3.0
