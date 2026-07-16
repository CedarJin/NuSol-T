"""Nutrient value model with four-state missingness."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Four-state missingness
Missingness = Literal["measured", "calculated", "below_loq", "missing"]


class NutrientValue(BaseModel):
    """A single nutrient value with provenance and missingness."""

    value: float | None = Field(
        default=None,
        description="Numeric value; None if missing or below_loq",
    )
    unit: str = Field(..., description="Unit of measurement")
    basis: str = Field(
        default="per_100g_finished_product",
        description="Reference basis for the value",
    )
    status: Missingness = Field(
        default="measured",
        description="Data status: measured/calculated/below_loq/missing",
    )
    loq: float | None = Field(
        default=None,
        description="Limit of quantification (for below_loq values)",
    )
    lower: float | None = Field(
        default=None,
        description="Lower bound of possible true value",
    )
    upper: float | None = Field(
        default=None,
        description="Upper bound of possible true value",
    )
    provenance: dict[str, str] = Field(
        default_factory=dict,
        description="Source provenance: data source, method, version",
    )

    @property
    def is_missing(self) -> bool:
        """Return True if this value cannot be used for computation."""
        return self.status == "missing" or self.value is None

    @property
    def is_below_loq(self) -> bool:
        """Return True if the value is below the limit of quantification."""
        return self.status == "below_loq"

    def effective_value(self) -> float | None:
        """Return the value usable in computation, or None if missing.

        For below_loq values, returns loq/2 as a rough imputation
        (caller should be aware of this approximation).
        """
        if self.status == "missing" or (self.value is None and self.status != "below_loq"):
            return None
        if self.status == "below_loq":
            return (self.loq or 0) / 2 if self.loq else 0.0
        return self.value

    def __repr__(self) -> str:
        status_sym = {"measured": "✓", "calculated": "△", "below_loq": "↓", "missing": "✗"}
        sym = status_sym.get(self.status, "?")
        val_str = f"{self.value}" if self.value is not None else "-"
        return f"NutrientValue({sym} {val_str} {self.unit})"


# ── Canonical nutrient mapping ───────────────────────────────────────────────
# Maps canonical IDs → (preferred_name, unit, [usda_ids], [aliases])
# Used for standardization across data sources.

CANONICAL_NUTRIENT_MAP: dict[str, tuple[str, str, list[int], list[str]]] = {
    "energy_kcal": ("Energy", "kcal", [1008], ["Energy (kcal)", "Energy (kilocalories)"]),
    "protein_g": ("Protein", "g", [1003], ["Protein, total", "Total protein"]),
    "fat_g": ("Total lipid (fat)", "g", [1004], ["Fat", "Total Fat", "Total lipid"]),
    "saturated_fat_g": (
        "Fatty acids, total saturated", "g", [1258],  # Correct USDA ID (was 1292)
        ["Saturated Fat", "Saturated fatty acids", "Saturates"],
    ),
    "monounsaturated_fat_g": (
        "Fatty acids, total monounsaturated", "g", [1292],  # Correct USDA ID (was 1293)
        ["Monounsaturated Fat", "Monounsaturates"],
    ),
    "polyunsaturated_fat_g": (
        "Fatty acids, total polyunsaturated", "g", [1293],  # Correct USDA ID (was 1294)
        ["Polyunsaturated Fat", "Polyunsaturates"],
    ),
    "trans_fat_g": (
        "Fatty acids, total trans", "g", [1257],
        ["Trans Fat", "Trans fatty acids"],
    ),
    "cholesterol_mg": (
        "Cholesterol", "mg", [1253],
        ["Total Cholesterol"],
    ),
    "carbohydrate_g": (
        "Carbohydrate, by difference", "g", [1005],
        ["Carbohydrate", "Total Carbohydrate", "Carbs"],
    ),
    "fiber_g": (
        "Fiber, total dietary", "g", [1079],
        ["Dietary Fiber", "Fiber"],
    ),
    "sugars_g": (
        "Total Sugars", "g", [2000],
        ["Sugars", "Sugar", "Total Sugars"],
    ),
    "added_sugars_g": (
        "Sugars, added", "g", [1063],
        ["Added Sugars", "Added Sugar"],
    ),
    "sodium_mg": (
        "Sodium, Na", "mg", [1093],
        ["Sodium"],
    ),
    "calcium_mg": (
        "Calcium, Ca", "mg", [1087],
        ["Calcium"],
    ),
    "iron_mg": (
        "Iron, Fe", "mg", [1089],
        ["Iron"],
    ),
    "potassium_mg": (
        "Potassium, K", "mg", [1092],
        ["Potassium"],
    ),
    "vitamin_d_mcg": (
        "Vitamin D (D2 + D3)", "µg", [1112],
        ["Vitamin D", "Vit D"],
    ),
    "vitamin_d_iu": (
        "Vitamin D", "IU", [1110],
        [],
    ),
}
