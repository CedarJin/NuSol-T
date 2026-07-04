"""Tests for ForwardNutritionModel."""

from __future__ import annotations

import numpy as np
import pytest


class TestForwardNutritionModel:
    """Tests for the forward nutrition calculation model."""

    def test_simple_linear_combination(self):
        from nusol.nutrition.forward import ForwardNutritionModel

        model = ForwardNutritionModel()
        # 2 ingredients, 3 nutrients
        x = np.array([0.6, 0.4])
        A = np.array([
            [10.0, 5.0, 0.0],   # ingredient 1
            [5.0, 0.0, 2.0],    # ingredient 2
        ])
        predicted = model.compute(x, A)
        # Ingredient 1 contributes 60%, ingredient 2 contributes 40%
        assert predicted[0] == pytest.approx(10.0 * 0.6 + 5.0 * 0.4)  # = 8.0
        assert predicted[1] == pytest.approx(5.0 * 0.6 + 0.0 * 0.4)   # = 3.0
        assert predicted[2] == pytest.approx(0.0 * 0.6 + 2.0 * 0.4)   # = 0.8

    def test_single_ingredient(self):
        from nusol.nutrition.forward import ForwardNutritionModel

        model = ForwardNutritionModel()
        x = np.array([1.0])
        A = np.array([[100.0, 20.0, 5.0]])
        predicted = model.compute(x, A)
        np.testing.assert_array_almost_equal(predicted, [100.0, 20.0, 5.0])

    def test_moisture_adjustment(self):
        from nusol.nutrition.forward import ForwardNutritionModel

        model = ForwardNutritionModel({
            "moisture": {"enabled": True},
        })
        x = np.array([1.0])
        A = np.array([[50.0]])

        # 10% moisture loss → nutrients concentrate
        predicted = model.compute(x, A, moisture_change=10.0)
        # yield_factor = 100/(100-10) = 1.111...
        expected = 50.0 * 1.1111111111111112
        assert predicted[0] == pytest.approx(expected, rel=1e-4)

    def test_no_moisture_change(self):
        from nusol.nutrition.forward import ForwardNutritionModel

        model = ForwardNutritionModel({
            "moisture": {"enabled": True},
        })
        x = np.array([0.5, 0.5])
        A = np.array([[10.0], [20.0]])
        predicted = model.compute(x, A, moisture_change=0.0)
        assert predicted[0] == pytest.approx(15.0)

    def test_with_retention_factors(self):
        from nusol.nutrition.forward import ForwardNutritionModel

        model = ForwardNutritionModel({
            "retention": {"enabled": True},
        })
        x = np.array([1.0])
        A = np.array([[100.0]])
        r = np.array([[0.5]])  # 50% retention
        predicted = model.compute(x, A, retention_factors=r)
        assert predicted[0] == pytest.approx(50.0)

    def test_retention_disabled(self):
        from nusol.nutrition.forward import ForwardNutritionModel

        model = ForwardNutritionModel({
            "retention": {"enabled": False},
        })
        x = np.array([1.0])
        A = np.array([[100.0]])
        r = np.array([[0.5]])
        predicted = model.compute(x, A, retention_factors=r)
        # Retention disabled → should ignore r
        assert predicted[0] == pytest.approx(100.0)

    def test_compute_from_dicts(self):
        from nusol.nutrition.forward import ForwardNutritionModel

        model = ForwardNutritionModel()
        fractions = {"flour": 0.7, "sugar": 0.3}
        matrix = {
            "flour": {"Energy": 364.0, "Protein": 10.0},
            "sugar": {"Energy": 387.0, "Protein": 0.0},
        }
        result = model.compute_from_dicts(fractions, matrix, ["Energy", "Protein"])
        assert result["Energy"] == pytest.approx(364 * 0.7 + 387 * 0.3)
        assert result["Protein"] == pytest.approx(10 * 0.7 + 0 * 0.3)

    def test_compute_from_dicts_missing_nutrient(self):
        from nusol.nutrition.forward import ForwardNutritionModel

        model = ForwardNutritionModel()
        fractions = {"a": 1.0}
        matrix = {"a": {"Energy": 100.0}}
        result = model.compute_from_dicts(fractions, matrix, ["Energy", "Protein"])
        assert result["Energy"] == 100.0
        assert result["Protein"] == 0.0

    def test_energy_from_macronutrients(self):
        from nusol.nutrition.forward import ForwardNutritionModel

        model = ForwardNutritionModel()
        energy = model.compute_energy_from_macronutrients(10.0, 20.0, 30.0)
        expected = 4 * 10 + 9 * 20 + 4 * 30  # = 340
        assert energy == pytest.approx(expected)

    def test_energy_with_fiber_and_alcohol(self):
        from nusol.nutrition.forward import ForwardNutritionModel

        model = ForwardNutritionModel()
        energy = model.compute_energy_from_macronutrients(10.0, 5.0, 20.0, fiber_g=5.0, alcohol_g=2.0)
        expected = 4 * 10 + 9 * 5 + 4 * 20 + 2 * 5 + 7 * 2  # = 199
        assert energy == pytest.approx(expected)

    def test_water_by_difference(self):
        from nusol.nutrition.forward import ForwardNutritionModel

        model = ForwardNutritionModel()
        fractions = np.array([0.6, 0.4])
        water = np.array([12.0, 0.1])  # g water per 100g of each ingredient
        result = model.compute_water_by_difference(fractions, water)
        assert result == pytest.approx(12.0 * 0.6 + 0.1 * 0.4)

    def test_mass_conservation_without_moisture(self):
        """Without moisture change, all mass fractions sum to 1 → nutrient should equal weighted sum."""
        from nusol.nutrition.forward import ForwardNutritionModel

        model = ForwardNutritionModel()
        # Create a mass-like nutrient (total should be 100g/100g)
        x = np.array([0.3, 0.5, 0.2])
        A = np.ones((3, 1)) * 100  # 100g per 100g for each ingredient
        predicted = model.compute(x, A)
        assert predicted[0] == pytest.approx(100.0)
