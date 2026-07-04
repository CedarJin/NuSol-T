"""USDA Branded Food data adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nusol.core.schema import NutrientProfile, NutrientRecord, ProductObservation
from nusol.data.base import DataAdapterBase


class BrandedDataAdapter(DataAdapterBase):
    """Adapter for USDA Branded Food Database (real packaged food labels)."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._data: dict[int, dict] = {}

    def load(self, path: str | Path) -> None:
        """Load Branded Food JSON.

        Expected JSON structure: {"BrandedFoods": [{...}, ...]}
        """
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)

        foods = raw.get("BrandedFoods", [])
        self._data.clear()

        for food in foods:
            fdc_id = food.get("fdcId")
            if fdc_id is not None:
                self._data[fdc_id] = food

    def _parse_nutrients(self, nutrients_list: list[dict]) -> list[NutrientRecord]:
        """Parse nutrient records from Branded Food nutrient list."""
        result = []
        for fn in nutrients_list:
            nut_info = fn.get("nutrient", {})
            result.append(NutrientRecord(
                nutrient_id=nut_info.get("id", 0),
                nutrient_number=str(nut_info.get("number", "")),
                name=nut_info.get("name", ""),
                amount=fn.get("amount", 0.0),
                unit=nut_info.get("unitName", "g"),
                rank=nut_info.get("rank"),
                derivation_code=(
                    fn.get("foodNutrientDerivation", {}).get("code")
                    if "foodNutrientDerivation" in fn
                    else None
                ),
                source_description=(
                    fn.get("foodNutrientDerivation", {}).get("description")
                    if "foodNutrientDerivation" in fn
                    else None
                ),
            ))
        return result

    def get_nutrient_profile(self, fdc_id: int) -> NutrientProfile | None:
        """Get the nutrient profile for a branded food product."""
        food = self._data.get(fdc_id)
        if food is None:
            return None

        nutrients = self._parse_nutrients(food.get("foodNutrients", []))
        return NutrientProfile(
            fdc_id=fdc_id,
            description=food.get("description", ""),
            nutrients=nutrients,
            basis="per_serving" if food.get("servingSize") else "per_100g",
        )

    def get_product_info(self, fdc_id: int) -> dict[str, Any] | None:
        """Get product information for a branded food."""
        food = self._data.get(fdc_id)
        if food is None:
            return None

        return {
            "fdc_id": fdc_id,
            "description": food.get("description", ""),
            "brand_owner": food.get("brandOwner", ""),
            "brand_name": food.get("brandName", ""),
            "gtin_upc": food.get("gtinUpc", ""),
            "ingredients": food.get("ingredients", ""),
            "serving_size": food.get("servingSize", 0),
            "serving_size_unit": food.get("servingSizeUnit", "g"),
            "household_serving": food.get("householdServingFullText", ""),
            "branded_food_category": food.get("brandedFoodCategory", ""),
            "market_country": food.get("marketCountry", ""),
            "nutrients": self._parse_nutrients(food.get("foodNutrients", [])),
        }

    def to_product_observation(self, fdc_id: int) -> ProductObservation | None:
        """Convert branded food to ProductObservation."""
        info = self.get_product_info(fdc_id)
        if info is None:
            return None

        serving_size_g = info["serving_size"]
        if isinstance(serving_size_g, str):
            try:
                serving_size_g = float(serving_size_g)
            except ValueError:
                serving_size_g = 100.0
        if serving_size_g <= 0:
            serving_size_g = 100.0

        return ProductObservation(
            fdc_id=fdc_id,
            description=info["description"],
            source="BRANDED",
            label_nutrients=info["nutrients"],
            serving_size_g=serving_size_g,
            brand_owner=info["brand_owner"],
            branded_category=info["branded_food_category"],
            gtin_upc=info["gtin_upc"],
        )

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, fdc_id: int) -> bool:
        return fdc_id in self._data
