"""Tests for TrustReport and TrustGrade."""

from __future__ import annotations

import pytest


class TestTrustGrade:
    """Tests for trust grade computation."""

    def test_perfect_grade_A(self):
        from nusol.report.trust_grade import compute_trust_grade
        from nusol.core.schema import SolverResult, IdentifiabilityReport

        point = SolverResult(
            success=True,
            nutrient_residuals={"Energy": 0.0},
            active_constraints=[],
        )
        ident = IdentifiabilityReport(interval_width_median=0.1, degrees_of_freedom=1)

        grade, score = compute_trust_grade(point=point, identifiability=ident)
        assert grade == "A"
        assert score >= 80

    def test_failed_solve_grade_d(self):
        from nusol.report.trust_grade import compute_trust_grade
        from nusol.core.schema import SolverResult

        point = SolverResult(
            success=False,
            nutrient_residuals={"Energy": 50.0},
            active_constraints=["mass_balance", "label_interval_fit", "ingredient_order"],
        )

        grade, score = compute_trust_grade(point=point)
        assert grade == "D"
        assert score < 40

    def test_moderate_grade_b_or_c(self):
        from nusol.report.trust_grade import compute_trust_grade
        from nusol.core.schema import SolverResult, IdentifiabilityReport

        point = SolverResult(
            success=True,
            nutrient_residuals={"Energy": 3.0},
            active_constraints=["label_interval_fit"],
        )
        ident = IdentifiabilityReport(interval_width_median=0.35, degrees_of_freedom=4)

        grade, score = compute_trust_grade(point=point, identifiability=ident)
        assert grade in ("B", "C")
        assert 40 <= score < 80

    def test_score_clamped(self):
        from nusol.report.trust_grade import compute_trust_grade
        from nusol.core.schema import SolverResult

        # Extremely bad
        point = SolverResult(
            success=False,
            active_constraints=[f"conflict_{i}" for i in range(20)],
            nutrient_residuals={"Energy": 500.0},
        )

        grade, score = compute_trust_grade(point=point)
        assert score >= 0.0
        assert grade == "D"


class TestTrustReportBuilder:
    """Tests for TrustReportBuilder."""

    def test_build_basic_report(self, sample_product_observation):
        from nusol.report.trust import TrustReportBuilder
        from nusol.core.schema import SolverResult

        point = SolverResult(
            success=True,
            x_point={"enriched flour": 0.6, "sugar": 0.25, "vegetable oil": 0.15},
            nutrient_residuals={"Energy": 0.5},
            active_constraints=[],
            solver_name="trust-constr",
        )
        bounds = SolverResult(
            x_lower={"enriched flour": 0.5, "sugar": 0.15, "vegetable oil": 0.05},
            x_upper={"enriched flour": 0.7, "sugar": 0.35, "vegetable oil": 0.25},
        )

        builder = TrustReportBuilder()
        report = builder.build(sample_product_observation, point, bounds)

        assert report.fdc_id == 999999
        assert report.trust_grade == "A"  # No conflicts, reasonable intervals
        assert len(report.ingredient_estimates) == 3
        assert report.ingredient_estimates[0].ingredient_name == "enriched flour"

    def test_build_with_warnings(self, sample_product_observation):
        from nusol.report.trust import TrustReportBuilder
        from nusol.core.schema import SolverResult

        point = SolverResult(
            success=False,
            x_point={"enriched flour": 0.6, "sugar": 0.4},
            nutrient_residuals={"Energy": 20.0},
            active_constraints=["ingredient_order"],
        )

        builder = TrustReportBuilder()
        report = builder.build(sample_product_observation, point)

        assert len(report.warnings) >= 2  # success + constraint violation
        assert report.trust_grade in ("D", "C")
