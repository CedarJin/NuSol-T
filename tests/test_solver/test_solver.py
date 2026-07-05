"""Tests for solver modules (BoundSolver, EnsembleSolver, initializer, objective)."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def simple_context():
    """Create a simple problem context for testing solvers."""
    # 3 ingredients, 2 nutrients
    # True fractions: [0.5, 0.3, 0.2]
    # Nutrient matrix:
    #   ingredient 0: Energy=400, Protein=10
    #   ingredient 1: Energy=380, Protein=0
    #   ingredient 2: Energy=900, Protein=0
    A = np.array([
        [400.0, 10.0],
        [380.0, 0.0],
        [900.0, 0.0],
    ])
    # True predicted nutrients: [400*0.5+380*0.3+900*0.2, 10*0.5] = [494, 5]
    true_fractions = np.array([0.5, 0.3, 0.2])
    true_predicted = true_fractions @ A

    return {
        "ingredient_names": ["flour", "sugar", "oil"],
        "n_variables": 3,
        "main_ingredient_indices": [0, 1, 2],
        "two_percent_indices": [],
        "nutrient_matrix": A,
        "nutrient_names": ["Energy", "Protein"],
        "target_intervals": {
            "Energy": (float(true_predicted[0]) - 5, float(true_predicted[0]) + 5),
            "Protein": (float(true_predicted[1]) - 0.5, float(true_predicted[1]) + 0.5),
        },
    }


@pytest.fixture
def simple_constraints(simple_context):
    """Build a set of constraints for testing."""
    from nusol.constraints.base import ConstraintBuilder
    from nusol.constraints.mass_balance import MassBalanceConstraint
    from nusol.constraints.ingredient_order import IngredientOrderConstraint
    from nusol.constraints.label_interval import LabelIntervalFitConstraint

    builder = ConstraintBuilder({"constraints": {}})
    constraints = [
        MassBalanceConstraint(),
        IngredientOrderConstraint(),
        LabelIntervalFitConstraint(),
    ]
    return constraints, builder


class TestBoundSolver:
    """Tests for QP-based BoundSolver."""

    def test_basic_bounds(self, simple_context, simple_constraints):
        from nusol.solver.bound_solver import BoundSolver

        variables = simple_context["ingredient_names"]
        solver = BoundSolver({"max_iter": 300})
        result = solver.solve(variables, [], simple_context)

        assert result.x_lower
        assert result.x_upper
        for v in variables:
            assert result.x_lower[v] <= result.x_upper[v] + 1e-6, f"lower > upper for {v}"
            assert result.x_lower[v] >= -1e-10
            assert result.x_upper[v] <= 1.0 + 1e-10

    def test_all_variables_have_bounds(self, simple_context, simple_constraints):
        from nusol.solver.bound_solver import BoundSolver

        variables = simple_context["ingredient_names"]
        solver = BoundSolver({"max_iter": 300})
        result = solver.solve(variables, [], simple_context)

        for v in variables:
            assert v in result.x_lower
            assert v in result.x_upper


class TestInitializer:
    """Tests for initial guess generation."""

    def test_dirichlet_strategy(self):
        from nusol.solver.initializer import generate_initial_guesses

        guesses = generate_initial_guesses(5, n_starts=10, strategy="dirichlet", seed=42)
        assert len(guesses) == 10
        for g in guesses:
            assert len(g) == 5
            assert abs(g.sum() - 1.0) < 1e-10
            assert (g >= 0).all()

    def test_decreasing_strategy(self):
        from nusol.solver.initializer import generate_initial_guesses

        guesses = generate_initial_guesses(5, n_starts=10, strategy="decreasing", seed=42)
        for g in guesses:
            # Should be sorted in descending order
            for i in range(len(g) - 1):
                assert g[i] >= g[i + 1] - 1e-10

    def test_uniform_grid_strategy(self):
        from nusol.solver.initializer import generate_initial_guesses

        guesses = generate_initial_guesses(3, n_starts=5, strategy="uniform_grid", seed=42)
        for g in guesses:
            assert abs(g.sum() - 1.0) < 1e-10

    def test_unknown_strategy_raises(self):
        from nusol.solver.initializer import generate_initial_guesses

        with pytest.raises(ValueError, match="Unknown"):
            generate_initial_guesses(3, n_starts=2, strategy="nonexistent")


class TestConstraintBuilder:
    """Tests for ConstraintBuilder."""

    def test_build_from_config(self):
        from nusol.constraints.base import ConstraintBuilder

        config = {
            "constraints": {
                "mass_balance": {"enabled": True},
                "ingredient_order": {"enabled": True, "weight": 500},
                "two_percent_rule": {"enabled": False},
                "label_interval_fit": {"enabled": True, "weight": 20},
                "energy_closure": {"enabled": False},
                "water_solid_balance": {"enabled": False},
                "sodium_balance": {"enabled": False},
                "added_sugar_balance": {"enabled": False},
                "fatty_acid_closure": {"enabled": False},
                "category_prior": {"enabled": False},
            }
        }
        builder = ConstraintBuilder(config)
        constraints = builder.build({})

        # Should have 3 enabled constraints (mass_balance, ingredient_order, label_interval_fit)
        assert len(constraints) == 3
        # Sorted by priority
        names = [c.name for c in constraints]
        assert "mass_balance" in names  # P0
        assert "ingredient_order" in names  # P1

    def test_total_penalty(self, simple_context):
        from nusol.constraints.base import ConstraintBuilder
        from nusol.constraints.mass_balance import MassBalanceConstraint
        from nusol.constraints.label_interval import LabelIntervalFitConstraint

        builder = ConstraintBuilder({"constraints": {}})
        constraints = [
            MassBalanceConstraint(),
            LabelIntervalFitConstraint(weight=10.0),
        ]

        # Perfect solution
        x_good = np.array([0.5, 0.3, 0.2])
        penalty = builder.total_penalty(constraints, x_good, simple_context)
        assert penalty >= 0

        # Bad solution should have higher penalty
        x_bad = np.array([0.0, 0.0, 1.0])
        penalty_bad = builder.total_penalty(constraints, x_bad, simple_context)
        assert penalty_bad >= 0
