"""TrustReport builder — assembles results into a comprehensive report.

LEGACY MODULE — Not yet ported to the YAML solver framework.
Current public solve path is ``nusol.solve(yaml_path)``.
TrustReport + TrustGrade are planned for Phase 6+.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from nusol.core.schema import (
    TrustReport,
    IngredientEstimate,
    NutrientEstimate,
    IdentifiabilityReport,
    MappingProvenance,
    ProductObservation,
    SolverResult,
)
from nusol.report.trust_grade import compute_trust_grade


class TrustReportBuilder:
    """Build a TrustReport from solver results and product data."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        rep_cfg = self.config.get("reporting", {})

    def build(
        self,
        obs: ProductObservation,
        point: SolverResult,
        bounds: SolverResult | None = None,
        ensemble: SolverResult | None = None,
        mapping_provenance: list[MappingProvenance] | None = None,
    ) -> TrustReport:
        """Build a complete TrustReport for a product.

        Args:
            obs: Product observation.
            point: PointSolver result.
            bounds: Optional BoundSolver result.
            ensemble: Optional EnsembleSolver result.
            mapping_provenance: Optional ingredient mapping provenance.

        Returns:
            TrustReport with all estimates, quality metrics, and trust grade.
        """
        # Build ingredient estimates
        ingredient_estimates = self._build_ingredient_estimates(
            obs, point, bounds, ensemble
        )

        # Build identifiability report
        identifiability = self._build_identifiability(obs, point, bounds)

        # Build warnings
        warnings = self._build_warnings(point, bounds)

        # Compute trust grade
        grade, score = compute_trust_grade(
            point=point,
            bounds=bounds,
            identifiability=identifiability,
            obs=obs,
        )

        # Data source versions
        data_source_version = self._get_data_versions(obs)

        return TrustReport(
            fdc_id=obs.fdc_id,
            description=obs.description,
            ingredient_estimates=ingredient_estimates,
            expanded_nutrients=[],  # Filled in Phase 6
            nutrient_residuals=point.nutrient_residuals,
            constraint_slacks=point.constraint_slacks,
            constraint_conflicts=point.active_constraints,
            identifiability_report=identifiability,
            mapping_provenance=mapping_provenance or [],
            data_source_version=data_source_version,
            warnings=warnings,
            trust_grade=grade,
            trust_score=score,
            solver_name=point.solver_name,
            solve_time_s=point.solve_time_s,
            n_iterations=point.n_iterations,
        )

    def _build_ingredient_estimates(
        self,
        obs: ProductObservation,
        point: SolverResult,
        bounds: SolverResult | None,
        ensemble: SolverResult | None,
    ) -> list[IngredientEstimate]:
        """Build ingredient estimate list."""
        estimates = []
        for name, val in sorted(point.x_point.items(), key=lambda x: x[1], reverse=True):
            lo = bounds.x_lower.get(name, 0.0) if bounds else 0.0
            hi = bounds.x_upper.get(name, 1.0) if bounds else 1.0

            if ensemble:
                p5 = ensemble.x_lower.get(name, lo)
                p95 = ensemble.x_upper.get(name, hi)
            else:
                p5, p95 = lo, hi

            estimates.append(IngredientEstimate(
                ingredient_name=name,
                point_estimate=val,
                lower_bound=lo,
                upper_bound=hi,
                interval_80=(p5, p95),
                interval_95=(p5, p95),
                mapping_confidence=1.0,
            ))
        return estimates

    def _build_identifiability(
        self,
        obs: ProductObservation,
        point: SolverResult,
        bounds: SolverResult | None,
    ) -> IdentifiabilityReport:
        """Build identifiability report."""
        n_ingredients = len(point.x_point)
        n_label_nutrients = len(point.nutrient_residuals) if point.nutrient_residuals else 0
        degrees_of_freedom = max(0, n_ingredients - n_label_nutrients - 1)

        # Classify ingredients
        identifiable = []
        poorly_identified = []
        widths = []

        for name in point.x_point:
            lo = bounds.x_lower.get(name, 0.0) if bounds else 0.0
            hi = bounds.x_upper.get(name, 1.0) if bounds else 1.0
            w = hi - lo
            widths.append(w)
            if w < 0.2:
                identifiable.append(name)
            else:
                poorly_identified.append(name)

        median_width = float(np.median(widths)) if widths else 0.0

        return IdentifiabilityReport(
            n_ingredients=n_ingredients,
            n_label_nutrients=n_label_nutrients,
            degrees_of_freedom=degrees_of_freedom,
            identifiable_ingredients=identifiable,
            poorly_identified_ingredients=poorly_identified,
            interval_width_median=median_width,
        )

    def _build_warnings(
        self,
        point: SolverResult,
        bounds: SolverResult | None,
    ) -> list[str]:
        """Generate warning messages."""
        warnings = []
        if not point.success:
            warnings.append("Solver did not converge to optimal solution")
        if point.active_constraints:
            for c in point.active_constraints:
                warnings.append(f"Constraint '{c}' is violated")
        if point.nutrient_residuals:
            max_residual = max(point.nutrient_residuals.values())
            if max_residual > 10:
                warnings.append(f"Large nutrient residuals detected (max={max_residual:.1f})")
        return warnings

    def _get_data_versions(self, obs: ProductObservation) -> dict[str, str]:
        """Collect data source versions."""
        versions = {}
        if obs.source == "FNDDS":
            versions["FNDDS"] = "2021-2023"
        elif obs.source == "BRANDED":
            versions["BrandedFood"] = "2026-04-30"
        versions["SR_Legacy"] = "2018-04"
        return versions
