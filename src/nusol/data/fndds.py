"""FNDDS (Survey Food) data adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nusol.core.schema import (
    IngredientNode,
    IngredientTree,
    NutrientProfile,
    NutrientRecord,
    ProductObservation,
)
from nusol.data.base import DataAdapterBase


class FNDDSDataAdapter(DataAdapterBase):
    """Adapter for USDA FNDDS (Food and Nutrient Database for Dietary Studies).

    FNDDS contains:
      - foodNutrients: final product nutrient values per 100g
      - inputFoods: ingredients with weights (g per 100g finished product),
        retention codes, and sequence numbers
      - foodPortions: serving size information

    This is the core validation dataset for NuSol-T Phase 1-4.
    """

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        super().__init__(config)
        self._data: dict[int, dict] = {}  # fdc_id → food record
        self._by_code: dict[str, dict] = {}  # foodCode → food record
        self._ingredient_nutrients: dict[int, NutrientProfile] = {}  # ingredient_code → profile

    def load(self, path: str | Path) -> None:
        """Load FNDDS JSON.

        Expected JSON structure: {"SurveyFoods": [{...}, ...]}
        """
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            raw = json.load(f)

        foods = raw.get("SurveyFoods", [])
        self._data.clear()
        self._by_code.clear()

        for food in foods:
            fdc_id = food.get("fdcId")
            if fdc_id is not None:
                self._data[fdc_id] = food
            food_code = food.get("foodCode")
            if food_code is not None:
                self._by_code[food_code] = food

    def _parse_nutrients(self, food: dict) -> NutrientProfile:
        """Parse nutrient records from an FNDDS food dict."""
        nutrients = []
        for fn in food.get("foodNutrients", []):
            nut_info = fn.get("nutrient", {})
            nutrients.append(NutrientRecord(
                nutrient_id=nut_info.get("id", 0),
                nutrient_number=str(nut_info.get("number", "")),
                name=nut_info.get("name", ""),
                amount=fn.get("amount", 0.0),
                unit=nut_info.get("unitName", "g"),
                rank=nut_info.get("rank"),
            ))

        return NutrientProfile(
            fdc_id=food.get("fdcId"),
            description=food.get("description", ""),
            nutrients=nutrients,
            basis="per_100g",
        )

    def get_nutrient_profile(self, fdc_id: int) -> NutrientProfile | None:
        """Get the final product nutrient profile."""
        food = self._data.get(fdc_id)
        if food is None:
            return None
        return self._parse_nutrients(food)

    def get_recipe(self, fdc_id: int) -> dict[str, Any] | None:
        """Get the complete recipe data for an FNDDS food.

        Returns a dict with:
          - fdc_id, description, food_code
          - final_nutrients: NutrientProfile of the finished product
          - ingredients: list of ingredient dicts each with:
              - ingredient_code, description, weight_g (per 100g product),
              - retention_code, sequence_number
          - food_portions: serving size info
        """
        food = self._data.get(fdc_id)
        if food is None:
            return None

        ingredients = []
        for inf in food.get("inputFoods", []):
            ingredients.append({
                "ingredient_code": inf.get("ingredientCode"),
                "ingredient_fdc_id": inf.get("fdcId"),
                "description": inf.get("ingredientDescription", inf.get("foodDescription", "")),
                "weight_g": inf.get("ingredientWeight", inf.get("amount", 0.0)),
                "retention_code": inf.get("retentionCode", 0),
                "sequence_number": inf.get("sequenceNumber", 0),
                "unit": inf.get("unit", "GM"),
            })

        # Calculate fractions from weights
        total_weight = sum(ing["weight_g"] for ing in ingredients)
        for ing in ingredients:
            ing["fraction"] = ing["weight_g"] / total_weight if total_weight > 0 else 0.0

        return {
            "fdc_id": fdc_id,
            "description": food.get("description", ""),
            "food_code": food.get("foodCode", ""),
            "final_nutrients": self._parse_nutrients(food),
            "ingredients": ingredients,
            "food_portions": food.get("foodPortions", []),
            "data_type": food.get("dataType", ""),
            "publication_date": food.get("publicationDate", ""),
        }

    def get_ingredient_fractions(self, fdc_id: int) -> dict[str, float]:
        """Get true ingredient mass fractions for an FNDDS recipe.

        Returns {ingredient_description: fraction} dict.
        """
        recipe = self.get_recipe(fdc_id)
        if recipe is None:
            return {}

        total = sum(ing["weight_g"] for ing in recipe["ingredients"])
        if total == 0:
            return {}

        return {
            ing["description"]: ing["weight_g"] / total
            for ing in recipe["ingredients"]
        }

    # Fortificant ingredient codes (999xxx series)
    FORTIFICANT_CODES: set[str] = {
        "999328",  # Vitamin D as ingredient
        "999301",  # Calcium as ingredient
        "999303",  # Iron as ingredient
        "999401",  # Vitamin C as ingredient
        "999431",  # Folic acid as ingredient
        "999418",  # Vitamin B-12 as ingredient
        "999001",  # Vitamin B composite in cereals
        "999291",  # Fiber, total dietary, as ingredient
    }

    def map_ingredient_to_profile(
        self,
        ingredient_code: int,
        ingredient_description: str,
        foundation_db: DataAdapterBase | None = None,
        sr_legacy_db: DataAdapterBase | None = None,
    ) -> tuple[NutrientProfile | None, str, float]:
        """Map a single FNDDS ingredient code to a nutrient profile.

        Four-level fallback (prefer most current / authoritative data):
          L1: ingredientCode → FNDDS foodCode (self-lookup, same source)
          L2: ingredientCode → Foundation Foods ndbNumber (most current, 2026)
          L3: ingredientCode → SR Legacy ndbNumber (comprehensive, 2018 frozen)
          L4: ingredientDescription → SR Legacy fuzzy search

        Args:
            ingredient_code: FNDDS ingredientCode.
            ingredient_description: Human-readable ingredient name.
            foundation_db: Foundation Foods adapter (preferred, optional).
            sr_legacy_db: SR Legacy adapter (fallback, required).

        Returns:
            (profile, match_method, confidence)
        """
        code_str = str(ingredient_code)

        # Fortificant check — pure nutrient additives, skip mapping
        if code_str in self.FORTIFICANT_CODES:
            return None, "fortificant", 1.0

        # L1: ingredientCode → FNDDS foodCode (self-lookup, same data source)
        fndds_food = self._by_code.get(code_str)
        if fndds_food is not None:
            profile = self._parse_nutrients(fndds_food)
            if profile and len(profile.nutrients) > 0:
                return profile, "fndds_self", 1.0

        # L2: ingredientCode → Foundation Foods ndbNumber (gold standard, 2026)
        if foundation_db is not None and hasattr(foundation_db, "get_by_ndb_number"):
            profile = foundation_db.get_by_ndb_number(code_str)
            if profile is not None:
                return profile, "foundation_ndb", 0.98

        # L3: ingredientCode → SR Legacy ndbNumber (comprehensive fallback)
        if sr_legacy_db is not None and hasattr(sr_legacy_db, "get_by_ndb_number"):
            profile = sr_legacy_db.get_by_ndb_number(code_str)
            if profile is not None:
                return profile, "sr_legacy_ndb", 0.95

        # L4: ingredientDescription → SR Legacy fuzzy search
        if sr_legacy_db is not None and hasattr(sr_legacy_db, "search"):
            results = sr_legacy_db.search(ingredient_description)
            if results:
                profile, score = results[0]
                confidence = score / 100.0
                return profile, "fuzzy", confidence

        return None, "none", 0.0

    def get_ingredient_nutrient_matrix(
        self,
        fdc_id: int,
        foundation_db: DataAdapterBase | None = None,
        sr_legacy_db: DataAdapterBase | None = None,
        nutrient_names: list[str] | None = None,
        skip_zero_weight: bool = True,
    ) -> tuple[dict, dict[str, NutrientProfile], list[str], dict[str, dict]]:
        """Build the ingredient nutrient matrix for a recipe.

        Uses 4-level fallback: FNDDS self → Foundation → SR Legacy → fuzzy.
        Filters out zero-weight ingredients by default.

        Args:
            fdc_id: FNDDS food FDC ID.
            foundation_db: Foundation Foods adapter (L2, optional).
            sr_legacy_db: SR Legacy adapter (L3-L4, required).
            nutrient_names: Nutrient names to include (all if None).
            skip_zero_weight: If True, exclude ingredients with weight=0.

        Returns:
            (matrix, profiles, nutrient_names, mapping_meta)
        """
        recipe = self.get_recipe(fdc_id)
        if recipe is None:
            return {}, {}, [], {}

        if nutrient_names is None:
            nutrient_names = recipe["final_nutrients"].nutrient_names()

        # Filter zero-weight ingredients
        ingredients = recipe["ingredients"]
        if skip_zero_weight:
            ingredients = [ing for ing in ingredients if ing.get("weight_g", 0) > 0]

        matrix = {}
        profiles = {}
        mapping_meta = {}

        for ing in ingredients:
            name = ing["description"]
            code = ing.get("ingredient_code", 0)

            profile, method, conf = self.map_ingredient_to_profile(
                code, name,
                foundation_db=foundation_db,
                sr_legacy_db=sr_legacy_db,
            )

            mapping_meta[name] = {
                "method": method,
                "confidence": conf,
                "code": code,
            }

            if profile is None:
                profile = NutrientProfile(description=name, nutrients=[])

            profiles[name] = profile
            matrix[name] = {}
            for nut_name in nutrient_names:
                nut = profile.get_nutrient_by_name(nut_name)
                matrix[name][nut_name] = nut.amount if nut else 0.0

        return matrix, profiles, nutrient_names, mapping_meta

    def to_product_observation(self, fdc_id: int) -> ProductObservation | None:
        """Convert an FNDDS recipe to a ProductObservation."""
        recipe = self.get_recipe(fdc_id)
        if recipe is None:
            return None

        # Build ingredient tree
        root_ingredients = []
        for ing in sorted(recipe["ingredients"], key=lambda x: x["sequence_number"]):
            pos = ing["sequence_number"] - 1  # 0-based
            node = IngredientNode(
                name=ing["description"],
                normalized_name=ing["description"].lower().strip(),
                position=pos,
            )
            root_ingredients.append(node)

        ingredient_tree = IngredientTree(
            raw_text=", ".join(ing["description"] for ing in recipe["ingredients"]),
            root_ingredients=root_ingredients,
        )

        # Compute true fractions
        fractions = self.get_ingredient_fractions(fdc_id)

        # Get a representative serving size from the first food portion
        serving_size_g = 100.0
        portions = recipe.get("food_portions", [])
        if portions:
            serving_size_g = portions[0].get("gramWeight", 100.0)
            if serving_size_g <= 0:
                serving_size_g = 100.0

        return ProductObservation(
            fdc_id=fdc_id,
            description=recipe["description"],
            source="FNDDS",
            label_nutrients=recipe["final_nutrients"].nutrients,
            serving_size_g=serving_size_g,
            ingredient_tree=ingredient_tree,
            food_code=recipe["food_code"],
            true_ingredient_fractions=fractions,
            true_nutrient_profile=recipe["final_nutrients"],
        )

    def get_recipes_with_ingredients(
        self, min_ingredients: int = 2, max_ingredients: int = 50
    ) -> list[int]:
        """Return FDC IDs of recipes that have inputFoods."""
        result = []
        for fdc_id, food in self._data.items():
            n = len(food.get("inputFoods", []))
            if min_ingredients <= n <= max_ingredients:
                result.append(fdc_id)
        return result

    def get_serving_size_g(self, fdc_id: int) -> float:
        """Get the serving size in grams for a food."""
        food = self._data.get(fdc_id)
        if food is None:
            return 100.0
        portions = food.get("foodPortions", [])
        if portions:
            gw = portions[0].get("gramWeight", 100.0)
            if gw > 0:
                return gw
        return 100.0

    @staticmethod
    def load_validation_ids(config_path: str = "config/validation_recipes.json") -> list[int]:
        """Load the fixed validation set of 200 FDC IDs.

        Args:
            config_path: Path to the validation recipes JSON file.

        Returns:
            List of 200 FDC IDs (fixed, seed=42).
        """
        import json
        from pathlib import Path

        path = Path(config_path)
        if not path.exists():
            raise FileNotFoundError(
                f"Validation recipes file not found: {path}. "
                "Run the sampling script to generate it."
            )
        with open(path) as f:
            data = json.load(f)
        return data["fdc_ids"]

    def load_validation_set(
        self, config_path: str = "config/validation_recipes.json"
    ) -> list[dict]:
        """Load the 200 sampled validation recipes.

        Returns list of recipe dicts (same format as get_recipe).
        """
        ids = self.load_validation_ids(config_path)
        recipes = []
        for fdc_id in ids:
            recipe = self.get_recipe(fdc_id)
            if recipe is not None:
                recipes.append(recipe)
        return recipes

    def __len__(self) -> int:
        return len(self._data)

    def __contains__(self, fdc_id: int) -> bool:
        return fdc_id in self._data
