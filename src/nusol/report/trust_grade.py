"""Trust grade computation — assign A/B/C/D grade based on solution quality.

LEGACY MODULE — Not yet ported to the YAML solver framework.
Current public solve path is ``nusol.solve(yaml_path)``.
"""

from __future__ import annotations

from nusol.core.schema import SolverResult, IdentifiabilityReport, ProductObservation


def compute_trust_grade(
    point: SolverResult,
    bounds: SolverResult | None = None,
    identifiability: IdentifiabilityReport | None = None,
    obs: ProductObservation | None = None,
) -> tuple[str, float]:
    """Compute trust grade and score from solver results.

    Grade criteria:
      A: Label intervals fit well, narrow intervals, no conflicts. Score ≥ 80.
      B: Most labels fit, few soft conflicts, reasonable intervals. Score ≥ 60.
      C: Wide intervals, mapping/label uncertainty. Score ≥ 40.
      D: Not interpretable. Score < 40.

    Returns:
        (grade, score) where grade ∈ {"A", "B", "C", "D"} and score ∈ [0, 100].
    """
    score = 100.0

    # 1. Solver success (0-20 points)
    if not point.success:
        score -= 20.0

    # 2. Active constraints (0-30 points)
    n_conflicts = len(point.active_constraints) if point.active_constraints else 0
    score -= n_conflicts * 10.0

    # 3. Nutrient residuals (0-20 points)
    residuals = point.nutrient_residuals
    if residuals:
        max_residual = max(residuals.values())
        if max_residual > 1.0:
            score -= 5.0
        if max_residual > 5.0:
            score -= 10.0
        if max_residual > 20.0:
            score -= 15.0

    # 4. Interval width (0-20 points)
    if identifiability and identifiability.interval_width_median > 0:
        w = identifiability.interval_width_median
        if w > 0.5:
            score -= 10.0
        elif w > 0.3:
            score -= 5.0

    # 5. Degrees of freedom penalty (0-10 points)
    if identifiability and identifiability.degrees_of_freedom > 5:
        score -= 10.0
    elif identifiability and identifiability.degrees_of_freedom > 3:
        score -= 5.0

    # Clamp score
    score = max(0.0, min(100.0, score))

    # Assign grade
    if score >= 80:
        grade = "A"
    elif score >= 60:
        grade = "B"
    elif score >= 40:
        grade = "C"
    else:
        grade = "D"

    return grade, score
