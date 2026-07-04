"""Labelized simulation — converting exact nutrients to simulated label values.

This simulates the process of:
  exact per 100g → per serving → FDA rounding → Nutrition Facts label
  → label interval → run inverse solver

This allows evaluation of NuSol-T's inverse performance when only
rounded label values (not exact database values) are available.
"""

from __future__ import annotations

from nusol.core.schema import NutrientRecord
from nusol.utils.numerics import apply_fda_rounding, label_value_to_interval
from nusol.core.units import convert_to_per_serving, convert_to_per_100g


def labelize_nutrients(
    true_nutrients: list[NutrientRecord],
    serving_size_g: float,
) -> list[NutrientRecord]:
    """Convert exact nutrient values to simulated Nutrition Facts label values.

    Process:
      per 100g true value → per serving → FDA rounding → rounded label value

    Args:
        true_nutrients: Exact nutrient values (per 100g).
        serving_size_g: Serving size in grams.

    Returns:
        Rounded label nutrient values (per serving).
    """
    labeled = []
    for nut in true_nutrients:
        # Convert to per serving
        per_serving = convert_to_per_serving(nut.amount, serving_size_g)

        # Apply FDA rounding
        rounded = apply_fda_rounding(per_serving, nut.name)

        labeled.append(NutrientRecord(
            nutrient_id=nut.nutrient_id,
            nutrient_number=nut.nutrient_number,
            name=nut.name,
            amount=rounded,
            unit=nut.unit,
            rank=nut.rank,
            derivation_code="SIMULATED_LABEL",
            source_description=f"Simulated from true value {nut.amount:.2f} per 100g",
        ))

    return labeled


def build_label_intervals(
    label_nutrients: list[NutrientRecord],
    serving_size_g: float,
) -> list[NutrientRecord]:
    """Build per-100g target intervals from label nutrients.

    Process:
      per serving label value → FDA interval (per serving) → convert to per 100g

    Args:
        label_nutrients: Label nutrient values (per serving, rounded).
        serving_size_g: Serving size in grams.

    Returns:
        Nutrient records with lower_bound and upper_bound set (per 100g).
    """
    result = []
    for nut in label_nutrients:
        # Get per-serving interval
        lo_serving, hi_serving = label_value_to_interval(nut.amount, nut.name)

        # Convert to per 100g
        lo_100g = convert_to_per_100g(lo_serving, serving_size_g)
        hi_100g = convert_to_per_100g(hi_serving, serving_size_g)

        result.append(NutrientRecord(
            nutrient_id=nut.nutrient_id,
            nutrient_number=nut.nutrient_number,
            name=nut.name,
            amount=nut.amount,  # label value per serving (kept for reference)
            unit=nut.unit,
            rank=nut.rank,
            lower_bound=lo_100g,
            upper_bound=hi_100g,
            derivation_code="LABEL_INTERVAL",
            source_description=f"Label interval from {lo_serving:.2f}-{hi_serving:.2f} per serving",
        ))

    return result


def simulate_nutrition_facts(
    true_nutrients: list[NutrientRecord],
    serving_size_g: float,
) -> tuple[list[NutrientRecord], list[NutrientRecord]]:
    """Full labelized simulation pipeline.

    Args:
        true_nutrients: Exact nutrient values per 100g.
        serving_size_g: Serving size in grams.

    Returns:
        (label_nutrients, target_intervals)
        - label_nutrients: rounded per-serving label values
        - target_intervals: per-100g target intervals for inverse solver
    """
    label_nutrients = labelize_nutrients(true_nutrients, serving_size_g)
    target_intervals = build_label_intervals(label_nutrients, serving_size_g)
    return label_nutrients, target_intervals
