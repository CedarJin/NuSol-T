"""Australia Food Composition Database (AFCD) adapter — Excel-based.

AFCD Release 3 provides:
  - Recipes: food → ingredient keys with weights and yield (moisture loss %)
  - Food Details: food names, groups
  - Nutrient profiles: per-100g nutrient values for all foods

Unlike FNDDS, AFCD has *built-in* yield factors (Total Weight Change %)
and much richer nutrient data (270 nutrients including amino acids, fatty acids).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

KJ_KCAL = 4.184

AFCD_NUTRIENTS = {
    "Energy with dietary fibre, equated \n(kJ)": ("energy_kj", "kJ"),
    "Protein \n(g)": ("protein_g", "g"),
    "Fat, total \n(g)": ("fat_g", "g"),
    "Carbohydrate, total \n(g)": ("carbohydrate_g", "g"),
    "Total dietary fibre \n(g)": ("fiber_g", "g"),
    "Total sugars \n(g)": ("sugars_g", "g"),
    "Saturated fat \n(g)": ("saturated_fat_g", "g"),
    "Cholesterol \n(mg)": ("cholesterol_mg", "mg"),
    "Sodium \n(mg)": ("sodium_mg", "mg"),
    "Calcium \n(mg)": ("calcium_mg", "mg"),
    "Iron \n(mg)": ("iron_mg", "mg"),
    "Potassium \n(mg)": ("potassium_mg", "mg"),
    "Vitamin D \n(µg)": ("vitamin_d_mcg", "mcg"),
}


class AFCDAdapter:
    """Adapter for the Australian Food Composition Database (Release 3)."""

    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else None
        self._recipes: pd.DataFrame | None = None
        self._foods: pd.DataFrame | None = None
        self._profiles: pd.DataFrame | None = None

    def load(self, base_dir: str | Path) -> None:
        path = Path(base_dir)
        self._recipes = pd.read_excel(
            path / "AFCD Release 3 - Recipes.xlsx",
            sheet_name="AFCD - Release 3", header=2,
        )
        self._recipes = self._recipes.dropna(subset=["Public Food Key"])
        self._recipes = self._recipes[self._recipes["Public Food Key"].str.match(r"^F\d+")]

        self._foods = pd.read_excel(
            path / "AFCD Release 3 - Food Details.xlsx",
            sheet_name="Food details", header=2,
        )

        self._profiles = pd.read_excel(
            path / "AFCD Release 3 - Nutrient profiles.xlsx",
            sheet_name="All solids & liquids per 100 g", header=2,
        )

    def get_recipes_with_ingredients(self, min_ingredients: int = 2) -> list[str]:
        if self._recipes is None:
            raise RuntimeError("Call .load() first")
        counts = self._recipes.groupby("Public Food Key").size()
        return [str(k) for k in counts[counts >= min_ingredients].index]

    def get_recipe(self, food_key: str) -> dict[str, Any] | None:
        if self._recipes is None:
            return None
        rows = self._recipes[self._recipes["Public Food Key"] == food_key]
        if len(rows) == 0:
            return None

        food_name = rows.iloc[0]["Food Name"]
        yield_pct = rows.iloc[0].get("Total Weight Change (%)", 0) or 0
        yield_factor = 100 / (100 - yield_pct) if yield_pct > 0 else 1.0

        ingredients = []
        for _, row in rows.iterrows():
            wt = float(row["Ingredient  Weight (g)"])
            ingredients.append({
                "ingredient_code": str(row["Ingredient Public Food Key"]),
                "description": str(row["Ingredient Name"]),
                "weight_g": wt,
            })

        total_wt = sum(i["weight_g"] for i in ingredients)
        for ing in ingredients:
            ing["fraction"] = ing["weight_g"] / total_wt if total_wt > 0 else 0

        # Final product nutrients
        final_prof = self._profiles[self._profiles["Public Food Key"] == food_key]
        final_nutrients = self._parse_nutrients(final_prof) if len(final_prof) > 0 else {}

        return {
            "food_key": food_key,
            "description": food_name,
            "yield_pct": yield_pct,
            "yield_factor": yield_factor,
            "ingredients": ingredients,
            "final_nutrients": final_nutrients,
        }

    def get_ingredient_nutrients(self, food_key: str) -> dict[str, float]:
        """Get per-100g nutrient values for an ingredient."""
        prof = self._profiles[self._profiles["Public Food Key"] == food_key]
        if len(prof) == 0:
            return {}
        return self._parse_nutrients(prof)

    def _parse_nutrients(self, profile_df: pd.DataFrame) -> dict[str, float]:
        """Convert AFCD nutrient row to flat dict of canonical_id → amount."""
        result = {}
        row = profile_df.iloc[0]
        for afcd_name, (canon_id, _unit) in AFCD_NUTRIENTS.items():
            if afcd_name in profile_df.columns:
                val = row[afcd_name]
                if pd.notna(val):
                    # Convert kJ to kcal, ensure plain Python float (not numpy scalar)
                    fval = float(val)
                    if canon_id == "energy_kj":
                        result["energy_kcal"] = round(fval / KJ_KCAL, 2)
                    else:
                        result[canon_id] = round(fval, 4)
        return result

    def __len__(self) -> int:
        return len(self._recipes) if self._recipes is not None else 0
