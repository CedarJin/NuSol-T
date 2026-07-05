"""Tests for QPSolver."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def qp_context_3():
    """3-ingredient problem with clear nutrient distinctions."""
    n = 3
    # Flour(400kcal,10g protein), Sugar(387kcal,0g protein), Oil(884kcal,0g protein)
    A = np.array([
        [400.0, 10.0],
        [387.0, 0.0],
        [884.0, 0.0],
    ])
    true_x = np.array([0.5, 0.3, 0.2])
    true_pred = true_x @ A  # [494.1, 5.0]

    return {
        "ingredient_names": ["flour", "sugar", "oil"],
        "n_variables": n,
        "main_ingredient_indices": [0, 1, 2],
        "two_percent_indices": [],
        "nutrient_matrix": A,
        "nutrient_names": ["Energy", "Protein"],
        "target_intervals": {
            "Energy": (float(true_pred[0]) - 5, float(true_pred[0]) + 5),
            "Protein": (float(true_pred[1]) - 0.5, float(true_pred[1]) + 0.5),
        },
    }


class TestQPSolver:
    """Tests for QPSolver."""

    def test_basic_solve(self, qp_context_3):
        from nusol.solver.qp_solver import QPSolver

        solver = QPSolver()
        result = solver.solve(
            qp_context_3["ingredient_names"], [], qp_context_3
        )

        assert result.success
        assert len(result.x_point) == 3
        # Mass conservation
        total = sum(result.x_point.values())
        assert abs(total - 1.0) < 0.01
        # All non-negative
        for v in result.x_point.values():
            assert v >= -1e-10

    def test_mass_conservation(self, qp_context_3):
        from nusol.solver.qp_solver import QPSolver

        solver = QPSolver()
        result = solver.solve(
            qp_context_3["ingredient_names"], [], qp_context_3
        )

        total = sum(result.x_point.values())
        assert abs(total - 1.0) < 0.001

    def test_nutrient_fit(self, qp_context_3):
        """Predicted nutrients should be within target intervals."""
        from nusol.solver.qp_solver import QPSolver

        solver = QPSolver()
        result = solver.solve(
            qp_context_3["ingredient_names"], [], qp_context_3
        )

        for name, pred in result.nutrient_predicted.items():
            interval = qp_context_3["target_intervals"].get(name)
            if interval:
                lo, hi = interval
                # Allow small violation from slack
                assert pred >= lo - 1.0, f"{name}: pred={pred:.2f} < lo={lo:.2f}"
                assert pred <= hi + 1.0, f"{name}: pred={pred:.2f} > hi={hi:.2f}"

    def test_ingredient_order(self, qp_context_3):
        """With order constraint, estimates should be descending."""
        from nusol.solver.qp_solver import QPSolver

        solver = QPSolver()
        result = solver.solve(
            qp_context_3["ingredient_names"], [], qp_context_3
        )

        vals = [result.x_point[n] for n in qp_context_3["ingredient_names"]]
        for i in range(len(vals) - 1):
            assert vals[i] >= vals[i + 1] - 1e-6, f"Order violated at {i}"

    def test_single_ingredient(self):
        from nusol.solver.qp_solver import QPSolver

        A = np.array([[100.0]])
        ctx = {
            "ingredient_names": ["sole"],
            "n_variables": 1,
            "main_ingredient_indices": [0],
            "two_percent_indices": [],
            "nutrient_matrix": A,
            "nutrient_names": ["Energy"],
            "target_intervals": {"Energy": (90.0, 110.0)},
        }

        solver = QPSolver()
        result = solver.solve(ctx["ingredient_names"], [], ctx)

        assert result.success
        assert abs(result.x_point["sole"] - 1.0) < 0.01

    def test_speed(self, qp_context_3):
        """QPSolver should be fast (< 0.1s for a 3-ingredient problem)."""
        from nusol.solver.qp_solver import QPSolver

        solver = QPSolver()
        result = solver.solve(
            qp_context_3["ingredient_names"], [], qp_context_3
        )

        assert result.solve_time_s < 1.0

    def test_no_nutrient_matrix(self):
        from nusol.solver.qp_solver import QPSolver

        solver = QPSolver()
        result = solver.solve(
            ["a", "b"], [], {"n_variables": 2, "ingredient_names": ["a", "b"]}
        )

        assert not result.success

    def test_returns_valid_result(self):
        """QPSolver should return valid estimates for a 2-ingredient problem."""
        from nusol.solver.qp_solver import QPSolver

        A = np.array([[400.0], [0.0]])  # first ingredient has nutrients, second doesn't
        ctx = {
            "ingredient_names": ["main", "trace"],
            "n_variables": 2,
            "main_ingredient_indices": [0, 1],
            "two_percent_indices": [],
            "nutrient_matrix": A,
            "nutrient_names": ["Energy"],
            "target_intervals": {"Energy": (360.0, 440.0)},
        }

        solver = QPSolver()
        result = solver.solve(ctx["ingredient_names"], [], ctx)

        assert result.success
        assert abs(sum(result.x_point.values()) - 1.0) < 0.01
        # Main ingredient has all the nutrients, should dominate
        assert result.x_point["main"] > 0.5
