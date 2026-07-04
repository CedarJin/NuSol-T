"""Foundation Foods data adapter — USDA's most current nutrient data (2026)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nusol.core.schema import NutrientProfile, NutrientRecord
from nusol.data.base import DataAdapterBase


class FoundationFoodsAdapter(DataAdapterBase):
    """Adapter for USDA Foundation Foods database.

    Foundation Foods contains the most current, comprehensively profiled
    food items. It has fewer entries (~363) than SR Legacy but each entry
    is maintained and updated. Preferred over SR Legacy when available.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._data: dict[int, dict] = {}           # fdcId → food record
        self._profiles: dict[int, NutrientProfile] = {}  # cached profiles
        self._ndb_index: dict[str, int] = {}        # ndbNumber → fdcId

    def load(self, path: str | Path) -> None:
        """Load Foundation Foods JSON.

        Expected JSON structure: {"FoundationFoods": [{...}, ...]}
        """
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)

        foods = raw.get("FoundationFoods", [])
        self._data.clear()
        self._profiles.clear()
        self._ndb_index.clear()

        for food in foods:
            if food is None:
                continue
            fdc_id = food.get("fdcId")
            if fdc_id is None:
                continue
            self._data[fdc_id] = food

            ndb = str(food.get("ndbNumber", ""))
            if ndb:
                self._ndb_index[ndb] = fdc_id

    def get_nutrient_profile(self, fdc_id: int) -> NutrientProfile | None:
        """Get nutrient profile by FDC ID."""
        if fdc_id in self._profiles:
            return self._profiles[fdc_id]

        food = self._data.get(fdc_id)
        if food is None:
            return None

        profile = self._parse_nutrients(food)
        self._profiles[fdc_id] = profile
        return profile

    def get_by_ndb_number(self, ndb_number: str | int) -> NutrientProfile | None:
        """Get nutrient profile by NDB number."""
        key = str(ndb_number)
        fdc_id = self._ndb_index.get(key)
        if fdc_id is None:
            return None
        return self.get_nutrient_profile(fdc_id)

    def has_ndb(self, ndb_number: str | int) -> bool:
        """Check if an ndbNumber exists."""
        return str(ndb_number) in self._ndb_index

    def _parse_nutrients(self, food: dict) -> NutrientProfile:
        """Parse nutrient records from a Foundation Foods dict."""
        nutrients = []
        for fn in food.get("foodNutrients", []):
            nut_info = fn.get("nutrient", {})
            nutrients.append(NutrientRecord(
                nutrient_id=nut_info.get("id", 0),
                nutrient_number=str(nut_info.get("number", "")),
                name=nut_info.get("name", ""),
                amount=fn.get("amount", 0.0),
                unit=nut_info.get("unitName", "g") or "g",
                rank=nut_info.get("rank"),
                derivation_code=(
                    fn.get("foodNutrientDerivation", {}).get("code")
                    if "foodNutrientDerivation" in fn
                    else None
                ),
            ))

        return NutrientProfile(
            fdc_id=food.get("fdcId"),
            description=food.get("description", ""),
            nutrients=nutrients,
            basis="per_100g",
        )

    def to_product_observation(self, fdc_id: int) -> None:
        return None

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, fdc_id: int) -> bool:
        return fdc_id in self._data
