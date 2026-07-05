"""IngredientMapper — multi-level ingredient-to-nutrient-profile mapping.

Four-level fallback (prefer most current / authoritative data):

    L1: ingredientCode → FNDDS foodCode (self-lookup, same source)
    L2: ingredientCode → Foundation Foods ndbNumber (2026 data)
    L3: ingredientCode → SR Legacy ndbNumber (2018 frozen)
    L4: ingredientDescription → SR Legacy fuzzy search

Fortificant (999xxx codes) are filtered and handled separately.
"""

from __future__ import annotations

from typing import Any

from nusol.core.schema import NutrientProfile

# Fortificant ingredient codes — pure nutrient additives with negligible weight
FORTIFICANT_CODES: set[str] = {
    "999328",  # Vitamin D as ingredient
    "999301",  # Calcium as ingredient
    "999303",  # Iron as ingredient
    "999401",  # Vitamin C as ingredient
    "999431",  # Folic acid as ingredient
    "999418",  # Vitamin B-12 as ingredient
    "999001",  # Vitamin B composite
    "999291",  # Fiber, total dietary, as ingredient
}


def is_fortificant(ingredient_code: int | str) -> bool:
    """Check if an ingredient code is a fortificant."""
    return str(ingredient_code) in FORTIFICANT_CODES


class MappingResult:
    """Result of mapping a single ingredient to a nutrient profile."""

    def __init__(
        self,
        profile: NutrientProfile | None,
        method: str,
        confidence: float,
        ingredient_code: int = 0,
        food_state: str = "unknown",
    ):
        self.profile = profile
        self.method = method  # "fndds_self" / "foundation_ndb" / "sr_legacy_ndb" / "fuzzy" / "fortificant" / "none"
        self.confidence = confidence
        self.ingredient_code = ingredient_code
        self.food_state = food_state

    @property
    def is_fortificant(self) -> bool:
        return self.method == "fortificant"

    @property
    def is_mapped(self) -> bool:
        return self.profile is not None


class IngredientMapper:
    """Map FNDDS ingredient codes to nutrient profiles via 4-level fallback.

    Usage::

        mapper = IngredientMapper(fndds_adapter)
        mapper.set_foundation_db(foundation_adapter)
        mapper.set_sr_legacy_db(sr_legacy_adapter)

        result = mapper.map("999301", "Calcium carbonate")  # → fortificant
        result = mapper.map("511", "Wheat flour")  # → FNDDS self
    """

    def __init__(self, fndds_adapter: Any | None = None) -> None:
        self._fndds = fndds_adapter
        self._foundation = None
        self._sr_legacy = None

    def set_foundation_db(self, adapter: Any) -> None:
        self._foundation = adapter

    def set_sr_legacy_db(self, adapter: Any) -> None:
        self._sr_legacy = adapter

    def map(
        self,
        ingredient_code: int,
        ingredient_description: str,
    ) -> MappingResult:
        """Map an ingredient code to a nutrient profile.

        Four-level fallback: FNDDS self → Foundation → SR Legacy → fuzzy.
        """
        code_str = str(ingredient_code)

        # Fortificant check
        if code_str in FORTIFICANT_CODES:
            return MappingResult(
                profile=None,
                method="fortificant",
                confidence=1.0,
                ingredient_code=ingredient_code,
            )

        # L1: FNDDS foodCode self-lookup
        if self._fndds is not None:
            try:
                food = self._fndds._by_code.get(code_str)
                if food is not None:
                    profile = self._fndds._parse_nutrients(food)
                    if profile and len(profile.nutrients) > 0:
                        return MappingResult(
                            profile=profile,
                            method="fndds_self",
                            confidence=1.0,
                            ingredient_code=ingredient_code,
                            food_state="as_purchased",
                        )
            except Exception:
                pass

        # L2: Foundation Foods ndbNumber
        if self._foundation is not None and hasattr(self._foundation, "get_by_ndb_number"):
            try:
                profile = self._foundation.get_by_ndb_number(code_str)
                if profile is not None:
                    return MappingResult(
                        profile=profile,
                        method="foundation_ndb",
                        confidence=0.98,
                        ingredient_code=ingredient_code,
                        food_state="as_purchased",
                    )
            except Exception:
                pass

        # L3: SR Legacy ndbNumber
        if self._sr_legacy is not None and hasattr(self._sr_legacy, "get_by_ndb_number"):
            try:
                profile = self._sr_legacy.get_by_ndb_number(code_str)
                if profile is not None:
                    return MappingResult(
                        profile=profile,
                        method="sr_legacy_ndb",
                        confidence=0.95,
                        ingredient_code=ingredient_code,
                        food_state="as_purchased",
                    )
            except Exception:
                pass

        # L4: SR Legacy fuzzy search
        if self._sr_legacy is not None and hasattr(self._sr_legacy, "search"):
            try:
                results = self._sr_legacy.search(ingredient_description)
                if results:
                    profile, score = results[0]
                    confidence = score / 100.0
                    return MappingResult(
                        profile=profile,
                        method="fuzzy",
                        confidence=confidence,
                        ingredient_code=ingredient_code,
                        food_state="estimated",
                    )
            except Exception:
                pass

        return MappingResult(
            profile=None,
            method="none",
            confidence=0.0,
            ingredient_code=ingredient_code,
        )

    def build_identifier(self, ingredient_code: int, sequence_number: int) -> str:
        """Build a stable ingredient identifier.

        Uses ``{code}_{seq}`` to avoid collisions when descriptions are identical
        but codes differ (fixes legacy FNDDS bug F4.1).
        """
        return f"{ingredient_code}_{sequence_number}"
