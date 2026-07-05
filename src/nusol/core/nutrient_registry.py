"""Canonical Nutrition Model — standardized nutrient codes and units."""

from __future__ import annotations

from typing import Optional


# Core nutrient definitions: (nutrient_id, nutrient_number, name, unit, rank)
# Taken from USDA FoodData Central nutrient dictionary
CORE_NUTRIENTS: list[tuple[int, str, str, str, int]] = [
    # Proximates
    (1003, "203", "Protein", "g", 600),
    (1004, "204", "Total lipid (fat)", "g", 800),
    (1005, "205", "Carbohydrate, by difference", "g", 1110),
    (1008, "208", "Energy", "kcal", 300),
    # Note: Energy in kJ (1062) is stored separately as "Energy (kJ)" to avoid name collision
    (1062, "268", "Energy (kJ)", "kJ", 400),
    (1079, "291", "Fiber, total dietary", "g", 1200),
    (2000, "269", "Total Sugars", "g", 1510),
    (1063, "269.3", "Sugars, added", "g", 1520),
    (1051, "255", "Water", "g", 100),
    (1007, "207", "Ash", "g", 1000),
    # Lipids
    (1257, "605", "Fatty acids, total trans", "g", 15400),
    (1258, "606", "Fatty acids, total saturated", "g", 970),
    (1292, "607", "Fatty acids, total monounsaturated", "g", 11400),
    (1293, "608", "Fatty acids, total polyunsaturated", "g", 11500),
    (1253, "601", "Cholesterol", "mg", 15700),
    # Minerals
    (1087, "301", "Calcium, Ca", "mg", 5300),
    (1089, "303", "Iron, Fe", "mg", 5400),
    (1090, "304", "Magnesium, Mg", "mg", 5500),
    (1091, "305", "Phosphorus, P", "mg", 5600),
    (1092, "306", "Potassium, K", "mg", 5700),
    (1093, "307", "Sodium, Na", "mg", 5800),
    (1095, "309", "Zinc, Zn", "mg", 5900),
    (1098, "312", "Copper, Cu", "mg", 6000),
    (1101, "315", "Manganese, Mn", "mg", 6100),
    (1102, "317", "Selenium, Se", "µg", 6200),
    # Vitamins
    (1106, "320", "Vitamin A, RAE", "µg", 7400),
    (1165, "401", "Vitamin C, total ascorbic acid", "mg", 11600),
    (1112, "328", "Vitamin D (D2 + D3)", "µg", 8700),
    (1109, "323", "Vitamin E (alpha-tocopherol)", "mg", 7900),
    (1110, "324", "Vitamin D", "IU", 8600),
    (1175, "415", "Vitamin B-6", "mg", 14000),
    (1176, "418", "Vitamin B-12", "µg", 14100),
    (1177, "410", "Folate, total", "µg", 13200),
    (1178, "435", "Folate, DFE", "µg", 13300),
    (1185, "421", "Choline, total", "mg", 11900),
    # Other
    (1057, "262", "Caffeine", "mg", 18300),
    (1058, "263", "Theobromine", "mg", 18400),
    (1018, "221", "Alcohol, ethyl", "g", 18200),
    (1242, "573", "Vitamin E, added", "mg", 8000),
    (1246, "578", "Vitamin B-12, added", "µg", 14110),
]

# USDA label nutrients (the "Big 7" + common label nutrients)
LABEL_NUTRIENT_NAMES: set[str] = {
    "Energy",
    "Total lipid (fat)",
    "Fatty acids, total saturated",
    "Fatty acids, total trans",
    "Cholesterol",
    "Sodium, Na",
    "Carbohydrate, by difference",
    "Fiber, total dietary",
    "Total Sugars",
    "Sugars, added",
    "Protein",
    "Vitamin D (D2 + D3)",
    "Calcium, Ca",
    "Iron, Fe",
    "Potassium, K",
}


class NutrientRegistry:
    """Central registry mapping nutrient IDs, numbers, names, and units.

    Provides canonical lookup across all data sources.
    """

    def __init__(self) -> None:
        self._by_id: dict[int, dict] = {}
        self._by_name: dict[str, dict] = {}
        self._by_number: dict[str, dict] = {}

        for nut_id, nut_num, name, unit, rank in CORE_NUTRIENTS:
            entry = {
                "nutrient_id": nut_id,
                "nutrient_number": nut_num,
                "name": name,
                "unit": unit,
                "rank": rank,
            }
            self._by_id[nut_id] = entry
            self._by_name[name.lower()] = entry
            self._by_number[nut_num] = entry

    def get_by_id(self, nutrient_id: int) -> Optional[dict]:
        """Look up nutrient by USDA nutrient ID."""
        return self._by_id.get(nutrient_id)

    def get_by_name(self, name: str) -> Optional[dict]:
        """Look up nutrient by standard name (case-insensitive)."""
        return self._by_name.get(name.lower())

    def get_by_number(self, number: str) -> Optional[dict]:
        """Look up nutrient by USDA nutrient number (e.g. '208')."""
        return self._by_number.get(number)

    def get_unit(self, name: str) -> Optional[str]:
        """Get the standard unit for a nutrient name."""
        entry = self.get_by_name(name)
        return entry["unit"] if entry else None

    def is_label_nutrient(self, name: str) -> bool:
        """Check if a nutrient is typically on a Nutrition Facts label."""
        return name in LABEL_NUTRIENT_NAMES

    @property
    def all_names(self) -> list[str]:
        """Return all registered nutrient names."""
        return [e["name"] for e in self._by_name.values()]

    @property
    def label_nutrient_names(self) -> list[str]:
        """Return names of label nutrients."""
        return sorted(LABEL_NUTRIENT_NAMES)

    @property
    def nutrient_count(self) -> int:
        """Total number of registered nutrients."""
        return len(self._by_id)

    def __len__(self) -> int:
        return self.nutrient_count

    def __contains__(self, name: str) -> bool:
        return name.lower() in self._by_name


# Singleton instance
_nutrient_registry: Optional[NutrientRegistry] = None


def get_nutrient_registry() -> NutrientRegistry:
    """Get or create the global nutrient registry singleton."""
    global _nutrient_registry
    if _nutrient_registry is None:
        _nutrient_registry = NutrientRegistry()
    return _nutrient_registry
