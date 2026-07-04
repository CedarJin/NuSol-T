"""Enumeration types used across NuSol-T."""

from enum import IntEnum, StrEnum


class ConstraintPriority(IntEnum):
    """Constraint priority levels (P0 is hardest, P4 is softest)."""

    P0 = 0  # Non-relaxable mathematical constraints
    P1 = 1  # Regulatory structural constraints
    P2 = 2  # Label nutrient interval fitting
    P3 = 3  # Food science soft constraints
    P4 = 4  # Statistical or category priors


class TrustGrade(StrEnum):
    """Trust grade for a product's estimate quality."""

    A = "A"  # Good label fit, clear mappings, narrow intervals, no key conflicts
    B = "B"  # Most labels fit, few soft conflicts, stable estimates
    C = "C"  # Directional estimates only, wide intervals, mapping/label uncertainty
    D = "D"  # Not interpretable as formulation, suitable for conflict diagnosis only


class DataSource(StrEnum):
    """Supported data sources."""

    FNDDS = "FNDDS"
    BRANDED = "BRANDED"
    SR_LEGACY = "SR_LEGACY"
    FOUNDATION = "FOUNDATION"
    CUSTOM = "CUSTOM"


class NutrientBasis(StrEnum):
    """Nutrient value basis."""

    PER_100G = "per_100g"
    PER_SERVING = "per_serving"


class SolverType(StrEnum):
    """Types of solvers available."""

    POINT = "point"
    BOUND = "bound"
    ENSEMBLE = "ensemble"
