"""Synthetic fixture tests for legacy solver baseline (Phase 0).

These tests run the legacy QPSolver and BoundSolver against synthetic fixtures
and compare results with the expected snapshots from `snapshot_synthetic.py`.

Purpose:
  - Lock down legacy behavior before refactoring
  - Provide regression detection during refactoring
  - Run without external USDA data

NOTE: The expected snapshots capture CURRENT legacy behavior, which includes known bugs
(FIX_PLAN F0.2: BoundSolver returns success=True on infeasible, etc.).
These tests assert what the code DOES, not what it SHOULD do.
"""

from __future__ import annotations

import warnings
# Suppress legacy solver deprecation warning — these tests explicitly test legacy behavior
warnings.filterwarnings("ignore", message="nusol.solver is legacy")

import json
from pathlib import Path

import numpy as np
import pytest

from nusol.solver.qp_solver import QPSolver
from nusol.solver.bound_solver import BoundSolver

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "synthetic"
EXPECTED_DIR = FIXTURES_DIR / "expected"


def load_fixture(name: str) -> dict:
    path = FIXTURES_DIR / f"{name}.json"
    with open(path) as f:
        return json.load(f)


def load_expected(name: str) -> dict:
    path = EXPECTED_DIR / f"{name}_expected.json"
    with open(path) as f:
        return json.load(f)


def fixture_to_context(fixture: dict) -> dict:
    return {
        "nutrient_matrix": np.array(fixture["nutrient_matrix"], dtype=float),
        "nutrient_names": fixture["nutrient_names"],
        "target_intervals": fixture["target_intervals"],
        "main_ingredient_indices": fixture.get(
            "main_ingredient_indices",
            list(range(len(fixture["variables"]))),
        ),
    }


FIXTURE_NAMES = [
    "feasible_2_ingredient",
    "infeasible_conflict",
    "underdetermined_3_ingredient",
]


class TestQPSolverLegacy:
    """Legacy QPSolver behavior on synthetic fixtures."""

    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_qp_snapshot(self, name: str) -> None:
        """QPSolver result matches legacy snapshot."""
        fixture = load_fixture(name)
        expected = load_expected(name)
        context = fixture_to_context(fixture)

        solver = QPSolver()
        result = solver.solve(fixture["variables"], constraints=[], context=context)

        exp_qp = expected["qp"]

        # Compare success
        assert result.success == exp_qp["success"], (
            f"QP success mismatch: got {result.success}, expected {exp_qp['success']}"
        )

        # Compare x_point (within tolerance)
        for ing in fixture["variables"]:
            got = round(result.x_point.get(ing, -1), 4)
            exp = round(exp_qp["x_point"].get(ing, -1), 4)
            assert abs(got - exp) < 1e-4, (
                f"x_point[{ing}] mismatch: got {got}, expected {exp}"
            )

        # Compare active constraints
        assert set(result.active_constraints) == set(exp_qp["active_constraints"]), (
            f"active_constraints mismatch: got {result.active_constraints}, "
            f"expected {exp_qp['active_constraints']}"
        )


class TestBoundSolverLegacy:
    """Legacy BoundSolver behavior on synthetic fixtures."""

    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_bound_snapshot(self, name: str) -> None:
        """BoundSolver result matches legacy snapshot."""
        fixture = load_fixture(name)
        expected = load_expected(name)
        context = fixture_to_context(fixture)

        solver = BoundSolver()
        result = solver.solve(fixture["variables"], constraints=[], context=context)

        exp_bs = expected["bound"]

        # Compare success
        assert result.success == exp_bs["success"], (
            f"Bound success mismatch: got {result.success}, expected {exp_bs['success']}"
        )

        # Compare x_lower / x_upper (within tolerance)
        for ing in fixture["variables"]:
            lo_got = round(result.x_lower.get(ing, -1), 4)
            lo_exp = round(exp_bs["x_lower"].get(ing, -1), 4)
            assert abs(lo_got - lo_exp) < 1e-4, (
                f"x_lower[{ing}] mismatch: got {lo_got}, expected {lo_exp}"
            )

            hi_got = round(result.x_upper.get(ing, -1), 4)
            hi_exp = round(exp_bs["x_upper"].get(ing, -1), 4)
            assert abs(hi_got - hi_exp) < 1e-4, (
                f"x_upper[{ing}] mismatch: got {hi_got}, expected {hi_exp}"
            )


class TestSyntheticFixtures:
    """Property-based tests for synthetic fixtures (cross-solver invariants)."""

    @pytest.mark.parametrize("name", ["feasible_2_ingredient", "underdetermined_3_ingredient"])
    def test_properties_feasible(self, name: str) -> None:
        """Success case invariants: non-negative fractions, sum ≈ 1, bounds consistent."""
        fixture = load_fixture(name)
        context = fixture_to_context(fixture)
        variables = fixture["variables"]

        qp = QPSolver()
        qp_result = qp.solve(variables, constraints=[], context=context)
        bs = BoundSolver()
        bs_result = bs.solve(variables, constraints=[], context=context)

        x = qp_result.x_point

        # All fractions non-negative
        for ing in variables:
            v = x.get(ing, 0)
            assert v >= -1e-6, f"Negative fraction: {ing}={v}"

        # Sum ≈ 1
        total = sum(x.get(ing, 0) for ing in variables)
        assert abs(total - 1.0) < 1e-3, f"Fractions don't sum to 1: {total}"

        # point ≤ upper, point ≥ lower
        for ing in variables:
            lo = bs_result.x_lower.get(ing, 0)
            hi = bs_result.x_upper.get(ing, 1)
            pt = x.get(ing, 0)
            assert lo <= pt + 1e-6, f"Point below lower: {ing} point={pt} < lower={lo}"
            assert pt <= hi + 1e-6, f"Point above upper: {ing} point={pt} > upper={hi}"

    def test_infeasible_qp_has_high_objective(self) -> None:
        """Infeasible case: QP should have high objective (large slack)."""
        fixture = load_fixture("infeasible_conflict")
        context = fixture_to_context(fixture)

        qp = QPSolver()
        result = qp.solve(fixture["variables"], constraints=[], context=context)

        # QP with slack still returns success=True (known legacy behavior)
        # But the objective should be large due to slack violation
        if result.objective_value is not None:
            assert result.objective_value > 1e6, (
                f"Expected large objective for infeasible, got {result.objective_value}"
            )

    def test_infeasible_bound_has_full_width(self) -> None:
        """Infeasible case: BoundSolver returns [0,1] (known legacy bug F0.2)."""
        fixture = load_fixture("infeasible_conflict")
        context = fixture_to_context(fixture)

        bs = BoundSolver()
        result = bs.solve(fixture["variables"], constraints=[], context=context)

        # Legacy behavior: success=True with [0,1] bounds (known bug)
        # This test captures the baseline; Phase 4 changes this.
        assert result.success, "Legacy BoundSolver should return success=True"

        for ing in fixture["variables"]:
            lo = result.x_lower.get(ing, 0)
            hi = result.x_upper.get(ing, 1)
            assert lo == 0.0, f"Lower bound should be 0.0 for infeasible (legacy bug)"
            assert hi == 1.0, f"Upper bound should be 1.0 for infeasible (legacy bug)"

    @pytest.mark.parametrize("name", FIXTURE_NAMES)
    def test_snapshot_regenerated(self, name: str) -> None:
        """Verify that snapshot regeneration would produce identical results.

        If this test fails, run `uv run python tests/fixtures/snapshot_synthetic.py`
        and commit the updated snapshots.
        """
        fixture = load_fixture(name)
        expected = load_expected(name)
        context = fixture_to_context(fixture)

        qp = QPSolver()
        qp_result = qp.solve(fixture["variables"], constraints=[], context=context)

        bs = BoundSolver()
        bs_result = bs.solve(fixture["variables"], constraints=[], context=context)

        exp_qp = expected["qp"]
        exp_bs = expected["bound"]

        # Check QP results (tolerant comparison)
        assert qp_result.success == exp_qp["success"]
        for ing in fixture["variables"]:
            g = qp_result.x_point.get(ing, 0)
            e = exp_qp["x_point"].get(ing, 0)
            assert abs(g - e) < 1e-5, f"QP x_point drift on {ing}: {g} vs {e}"

        # Check Bound results
        assert bs_result.success == exp_bs["success"]
        for ing in fixture["variables"]:
            g_lo = bs_result.x_lower.get(ing, 0)
            e_lo = exp_bs["x_lower"].get(ing, 0)
            assert abs(g_lo - e_lo) < 1e-5, f"Bound x_lower drift on {ing}: {g_lo} vs {e_lo}"
            g_hi = bs_result.x_upper.get(ing, 1)
            e_hi = exp_bs["x_upper"].get(ing, 1)
            assert abs(g_hi - e_hi) < 1e-5, f"Bound x_upper drift on {ing}: {g_hi} vs {e_hi}"
