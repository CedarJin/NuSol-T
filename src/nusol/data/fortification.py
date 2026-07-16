"""Fortification policy helpers for FNDDS export.

This module keeps fortificants out of ordinary ingredient-fraction variables and
provides conservative contribution estimates only when the mass→nutrient mapping
is chemically explicit enough to be reproducible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

FORTIFICANT_CODES: frozenset[str] = frozenset({
    "999328",  # Vitamin D as ingredient
    "999301",  # Calcium as ingredient
    "999303",  # Iron as ingredient
    "999401",  # Vitamin C as ingredient
    "999431",  # Folic acid as ingredient
    "999418",  # Vitamin B-12 as ingredient
    "999001",  # Vitamin B composite in cereals
    "999291",  # Fiber, total dietary, as ingredient
})

FORTIFICANT_RE = re.compile(
    r"("
    r"vitamin\s+[a-z0-9\-]+(?:\s+\([^)]+\))?\s+as\s+ingredient"
    r"|calcium\s+as\s+ingredient"
    r"|iron\s+as\s+ingredient"
    r"|zinc\s+as\s+ingredient"
    r"|potassium\s+as\s+ingredient"
    r"|folic\s+acid\s+as\s+ingredient"
    r"|fiber,\s*total\s+dietary,\s*as\s+ingredient"
    r"|vitamin\s+b\s+composite\s+in\s+cereals"
    r"|reduced\s+iron"
    r"|ferrous\s+sulfate"
    r"|calcium\s+carbonate"
    r"|niacinamide"
    r"|riboflavin"
    r"|thiamin\s+mononitrate"
    r"|folic\s+acid"
    r")",
    re.IGNORECASE,
)

NUTRIENT_HINTS: dict[str, tuple[str, ...]] = {
    "vitamin_d_mcg": ("vitamin d",),
    "calcium_mg": ("calcium", "calcium carbonate"),
    "iron_mg": ("iron", "reduced iron", "ferrous"),
    "fiber_g": ("fiber",),
    "vitamin_b12_mcg": ("b-12", "b12", "vitamin b composite"),
    "folate_mcg": ("folic acid",),
}

CODE_CONTRIBUTION_FACTORS: dict[str, dict[str, float]] = {
    # FNDDS "X as ingredient" codes are represented as nutrient mass per 100 g
    # recipe input. These are safe direct conversions from g to label units.
    "999301": {"calcium_mg": 1000.0},
    "999303": {"iron_mg": 1000.0},
    "999291": {"fiber_g": 1.0},
}

NAME_CONTRIBUTION_FACTORS: tuple[tuple[re.Pattern[str], dict[str, float], str], ...] = (
    (
        re.compile(r"\breduced\s+iron\b", re.IGNORECASE),
        {"iron_mg": 1000.0},
        "elemental_name_match",
    ),
    (
        re.compile(r"\bcalcium\s+carbonate\b", re.IGNORECASE),
        {"calcium_mg": 400.4},
        "stoichiometric_estimate",
    ),
)


@dataclass(frozen=True)
class FortificationIngredient:
    """A fortificant removed from ordinary ingredient-fraction solving."""

    name: str
    code: str
    weight_g: float
    weight_fraction_of_recipe: float
    suspected_nutrients: tuple[str, ...]
    estimated_contributions: dict[str, float]
    contribution_basis: str | None
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "code": self.code,
            "weight_g": self.weight_g,
            "weight_fraction_of_recipe": self.weight_fraction_of_recipe,
            "suspected_nutrients": list(self.suspected_nutrients),
            "estimated_contributions": self.estimated_contributions,
            "contribution_basis": self.contribution_basis,
            "reason": self.reason,
        }


def is_fortificant(code: int | str | None, name: str) -> bool:
    """Return True if an ingredient should be treated as a fortificant."""
    code_str = "" if code is None else str(code)
    return code_str in FORTIFICANT_CODES or bool(FORTIFICANT_RE.search(name))


def suspected_nutrients_for_fortificant(name: str) -> tuple[str, ...]:
    """Infer likely nutrients affected by a fortificant ingredient name."""
    lower = name.lower()
    nutrients = [
        nutrient_id
        for nutrient_id, hints in NUTRIENT_HINTS.items()
        if any(hint in lower for hint in hints)
    ]
    return tuple(nutrients)


def build_fortification_ingredient(
    ingredient: dict[str, Any],
    total_weight_g: float,
) -> FortificationIngredient:
    """Build structured fortification metadata from an FNDDS ingredient."""
    name = ingredient.get("description", "")
    code = str(ingredient.get("ingredient_code", ""))
    weight = float(ingredient.get("weight_g", 0.0) or 0.0)
    frac = weight / total_weight_g if total_weight_g > 0 else 0.0
    reason = "fortificant_code" if code in FORTIFICANT_CODES else "fortificant_name"
    estimated_contributions, contribution_basis = estimate_contribution(
        code,
        name,
        weight,
    )
    return FortificationIngredient(
        name=name,
        code=code,
        weight_g=weight,
        weight_fraction_of_recipe=frac,
        suspected_nutrients=suspected_nutrients_for_fortificant(name),
        estimated_contributions=estimated_contributions,
        contribution_basis=contribution_basis,
        reason=reason,
    )


def estimate_contribution(
    code: str,
    name: str,
    weight_g: float,
) -> tuple[dict[str, float], str | None]:
    """Estimate fortificant nutrient contribution per 100 g product.

    The estimate is intentionally conservative. It is only returned when the
    ingredient represents an elemental nutrient mass or a simple compound with a
    well-defined stoichiometric conversion. Potency-dependent vitamin premixes
    return no numeric estimate.
    """
    if code in CODE_CONTRIBUTION_FACTORS:
        return (
            {
                nutrient_id: weight_g * factor
                for nutrient_id, factor in CODE_CONTRIBUTION_FACTORS[code].items()
            },
            "fndds_direct_nutrient_mass",
        )

    for pattern, factors, basis in NAME_CONTRIBUTION_FACTORS:
        if pattern.search(name):
            return (
                {
                    nutrient_id: weight_g * factor
                    for nutrient_id, factor in factors.items()
                },
                basis,
            )

    return {}, None


def aggregate_contributions(
    fortificants: list[FortificationIngredient],
) -> dict[str, float]:
    """Aggregate estimated fortificant contributions by nutrient ID."""
    totals: dict[str, float] = {}
    for fortificant in fortificants:
        for nutrient_id, amount in fortificant.estimated_contributions.items():
            totals[nutrient_id] = totals.get(nutrient_id, 0.0) + amount
    return totals


def classify_export_failure(
    n_regular_ingredients: int,
    n_fortificants: int,
    n_collapsed_candidates: int = 0,
    no_observable_nutrients: bool = False,
) -> str:
    """Classify why an FNDDS recipe cannot be exported to ordinary solve YAML."""
    if n_regular_ingredients <= 1 and n_fortificants > 0:
        return "single_base_with_fortification"
    if n_collapsed_candidates > 0:
        return "canonical_variant_collapse_needed"
    if no_observable_nutrients and n_fortificants > 0:
        return "fortification_dominated_observations"
    if no_observable_nutrients:
        return "no_observable_nutrients"
    return "insufficient_regular_ingredients"


def fortification_diagnostics(
    fortificants: list[FortificationIngredient],
    skipped_nutrients: list[dict[str, Any]],
    failure_category: str | None = None,
) -> dict[str, Any]:
    """Build JSON-serializable fortification diagnostics."""
    suspected = sorted({
        nutrient
        for fortificant in fortificants
        for nutrient in fortificant.suspected_nutrients
    })
    estimated = aggregate_contributions(fortificants)
    return {
        "has_fortification": bool(fortificants),
        "failure_category": failure_category,
        "fortificant_ingredients": [item.as_dict() for item in fortificants],
        "suspected_fortified_nutrients": suspected,
        "estimated_contributions": estimated,
        "skipped_nutrients": skipped_nutrients,
    }
