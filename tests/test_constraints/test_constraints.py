"""Tests for all constraint classes."""

from __future__ import annotations

import numpy as np
import pytest


class TestMassBalanceConstraint:
    """Tests for P0 mass balance."""

    def test_sum_to_one_satisfied(self):
        from nusol.constraints.mass_balance import MassBalanceConstraint

        c = MassBalanceConstraint()
        x = np.array([0.3, 0.5, 0.2])
        ev = c.evaluate(x, {})
        assert ev.satisfied
        assert ev.violation < 1e-6

    def test_not_sum_to_one_violated(self):
        from nusol.constraints.mass_balance import MassBalanceConstraint

        c = MassBalanceConstraint()
        x = np.array([0.3, 0.5, 0.1])
        ev = c.evaluate(x, {})
        assert not ev.satisfied

    def test_scipy_constraint(self):
        from nusol.constraints.mass_balance import MassBalanceConstraint

        c = MassBalanceConstraint()
        sc = c.to_scipy_constraint({})
        assert sc["type"] == "eq"
        x = np.array([0.3, 0.5, 0.2])
        assert abs(sc["fun"](x)) < 1e-10

    def test_bounds(self):
        from nusol.constraints.mass_balance import MassBalanceConstraint

        c = MassBalanceConstraint()
        bounds = c.to_scipy_bounds({"n_variables": 3})
        assert bounds == [(0.0, 1.0), (0.0, 1.0), (0.0, 1.0)]


class TestIngredientOrderConstraint:
    """Tests for P1 ingredient order."""

    def test_correct_order_satisfied(self):
        from nusol.constraints.ingredient_order import IngredientOrderConstraint

        c = IngredientOrderConstraint()
        x = np.array([0.5, 0.3, 0.2])
        ev = c.evaluate(x, {"main_ingredient_indices": [0, 1, 2]})
        assert ev.satisfied

    def test_wrong_order_violated(self):
        from nusol.constraints.ingredient_order import IngredientOrderConstraint

        c = IngredientOrderConstraint()
        x = np.array([0.2, 0.5, 0.3])  # First < second
        ev = c.evaluate(x, {"main_ingredient_indices": [0, 1, 2]})
        assert not ev.satisfied
        assert ev.violation > 0.1


class TestTwoPercentRule:
    """Tests for P1 two percent rule."""

    def test_within_limit(self):
        from nusol.constraints.two_percent import TwoPercentRuleConstraint

        c = TwoPercentRuleConstraint()
        x = np.array([0.01, 0.5, 0.49])
        ev = c.evaluate(x, {"two_percent_indices": [0]})
        assert ev.satisfied

    def test_exceeds_limit(self):
        from nusol.constraints.two_percent import TwoPercentRuleConstraint

        c = TwoPercentRuleConstraint()
        x = np.array([0.05, 0.5, 0.45])
        ev = c.evaluate(x, {"two_percent_indices": [0]})
        assert not ev.satisfied

    def test_bounds(self):
        from nusol.constraints.two_percent import TwoPercentRuleConstraint

        c = TwoPercentRuleConstraint()
        bounds = c.to_scipy_bounds({"n_variables": 3, "two_percent_indices": [0]})
        assert bounds[0] == (0.0, 0.02)
        assert bounds[1] == (0.0, 1.0)
        assert bounds[2] == (0.0, 1.0)


class TestLabelIntervalFit:
    """Tests for P2 label interval fit."""

    def test_within_interval(self):
        from nusol.constraints.label_interval import LabelIntervalFitConstraint

        c = LabelIntervalFitConstraint()
        # 1 ingredient, 1 nutrient
        x = np.array([0.5])
        A = np.array([[10.0]])  # nutrient value for ingredient
        predicted = x @ A  # = 5.0
        interval = (4.0, 6.0)

        ev = c.evaluate(x, {
            "nutrient_matrix": A,
            "nutrient_names": ["TestNutrient"],
            "target_intervals": {"TestNutrient": interval},
        })
        assert ev.satisfied

    def test_below_interval(self):
        from nusol.constraints.label_interval import LabelIntervalFitConstraint

        c = LabelIntervalFitConstraint()
        x = np.array([0.2])
        A = np.array([[10.0]])  # predicted = 2.0
        interval = (4.0, 6.0)

        ev = c.evaluate(x, {
            "nutrient_matrix": A,
            "nutrient_names": ["TestNutrient"],
            "target_intervals": {"TestNutrient": interval},
        })
        assert not ev.satisfied
        assert ev.violation > 0

    def test_above_interval(self):
        from nusol.constraints.label_interval import LabelIntervalFitConstraint

        c = LabelIntervalFitConstraint()
        x = np.array([0.8])
        A = np.array([[10.0]])  # predicted = 8.0
        interval = (4.0, 6.0)

        ev = c.evaluate(x, {
            "nutrient_matrix": A,
            "nutrient_names": ["TestNutrient"],
            "target_intervals": {"TestNutrient": interval},
        })
        assert not ev.satisfied


class TestEnergyClosure:
    """Tests for P3 energy closure."""

    def test_consistent_energy(self):
        from nusol.constraints.energy_closure import EnergyClosureConstraint

        c = EnergyClosureConstraint()
        # Perfect consistency: 10g protein (40) + 5g fat (45) + 20g carb (80) = 165 kcal
        # Energy, Protein, Fat, Carb, Fiber, Alcohol
        x = np.array([1.0])
        A = np.array([[165.0, 10.0, 5.0, 20.0, 0.0, 0.0]])
        names = ["Energy", "Protein", "Total lipid (fat)", "Carbohydrate, by difference",
                 "Fiber, total dietary", "Alcohol, ethyl"]

        ev = c.evaluate(x, {
            "nutrient_matrix": A,
            "nutrient_names": names,
        })
        assert ev.satisfied

    def test_inconsistent_energy(self):
        from nusol.constraints.energy_closure import EnergyClosureConstraint

        c = EnergyClosureConstraint()
        # Energy says 200 kcal but macronutrients give 165 kcal
        x = np.array([1.0])
        A = np.array([[200.0, 10.0, 5.0, 20.0, 0.0, 0.0]])
        names = ["Energy", "Protein", "Total lipid (fat)", "Carbohydrate, by difference",
                 "Fiber, total dietary", "Alcohol, ethyl"]

        ev = c.evaluate(x, {
            "nutrient_matrix": A,
            "nutrient_names": names,
        })
        assert not ev.satisfied
        assert ev.violation > 100  # (165-200)² = 1225
