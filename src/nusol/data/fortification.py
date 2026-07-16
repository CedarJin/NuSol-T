"""Fortification policy helpers for FNDDS export.

This module does not try to solve micronutrient fortification amounts yet. Its
job is to keep fortificants out of ordinary ingredient-fraction variables and
to produce reproducible diagnostics for export / benchmark reporting.
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


@dataclass(frozen=True)
class FortificationIngredient:
    """A fortificant removed from ordinary ingredient-fraction solving."""

    name: str
    code: str
    weight_g: float
    weight_fraction_of_recipe: float
    suspected_nutrients: tuple[str, ...]
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "code": self.code,
            "weight_g": self.weight_g,
            "weight_fraction_of_recipe": self.weight_fraction_of_recipe,
            "suspected_nutrients": list(self.suspected_nutrients),
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
    return FortificationIngredient(
        name=name,
        code=code,
        weight_g=weight,
        weight_fraction_of_recipe=frac,
        suspected_nutrients=suspected_nutrients_for_fortificant(name),
        reason=reason,
    )


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
    return {
        "has_fortification": bool(fortificants),
        "failure_category": failure_category,
        "fortificant_ingredients": [item.as_dict() for item in fortificants],
        "suspected_fortified_nutrients": suspected,
        "skipped_nutrients": skipped_nutrients,
    }
