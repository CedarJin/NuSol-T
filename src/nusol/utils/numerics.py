"""Numerics utilities — rounding, interval logic, tolerance-aware comparison."""

from __future__ import annotations

import math

# ── FDA Rounding Rules (21 CFR 101.9) ───────────────────────────────────────

# Mapping from nutrient name patterns to rounding rules
FDA_ROUNDING_TABLE: dict[str, list[tuple[float, float, float]]] = {
    # Energy (kcal): per serving
    "Energy": [
        # (min_val, max_val, increment) — exclusive upper bound
        # < 5 cal → express as 0
        (0, 5, 0),  # special: round to 0
        (5, 50, 5),  # 5–50 → nearest 5
        (50, float("inf"), 10),  # > 50 → nearest 10
    ],
    # Fat / carbs / protein / fiber / sugars (g)
    "Total lipid (fat)": [
        (0, 0.5, 0),
        (0.5, 5, 0.5),
        (5, float("inf"), 1),
    ],
    "Fatty acids, total saturated": [
        (0, 0.5, 0),
        (0.5, 5, 0.5),
        (5, float("inf"), 1),
    ],
    "Fatty acids, total trans": [
        (0, 0.5, 0),
        (0.5, 5, 0.5),
        (5, float("inf"), 1),
    ],
    "Carbohydrate, by difference": [
        (0, 0.5, 0),
        (0.5, 1, 0.5),  # actually < 1g → "less than 1g"
        (1, float("inf"), 1),
    ],
    "Fiber, total dietary": [
        (0, 0.5, 0),
        (0.5, 1, 0.5),
        (1, float("inf"), 1),
    ],
    "Total Sugars": [
        (0, 0.5, 0),
        (0.5, 1, 0.5),
        (1, float("inf"), 1),
    ],
    "Sugars, added": [
        (0, 0.5, 0),
        (0.5, 1, 0.5),
        (1, float("inf"), 1),
    ],
    "Protein": [
        (0, 0.5, 0),
        (0.5, 1, 0.5),
        (1, float("inf"), 1),
    ],
    # Sodium (mg)
    "Sodium, Na": [
        (0, 5, 0),
        (5, 140, 5),
        (140, float("inf"), 10),
    ],
    # Cholesterol (mg)
    "Cholesterol": [
        (0, 2, 0),
        (2, 5, 5),  # actually 2-5mg → nearest 5mg
        (5, float("inf"), 5),
    ],
    # Minerals in mg (Calcium, Iron, Potassium)
    "Calcium, Ca": [
        (0, 2, 0),
        (2, 10, 2),
        (10, 50, 5),
        (50, float("inf"), 10),
    ],
    "Iron, Fe": [
        (0, 2, 0),
        (2, 10, 2),
        (10, 50, 5),
        (50, float("inf"), 10),
    ],
    "Potassium, K": [
        (0, 2, 0),
        (2, 10, 2),
        (10, 50, 5),
        (50, float("inf"), 10),
    ],
    # Vitamins
    "Vitamin D (D2 + D3)": [
        (0, 0.5, 0),
        (0.5, 1, 0.5),
        (1, float("inf"), 1),
    ],
}

# Default rounding for unknown nutrients: nearest 1
_DEFAULT_ROUNDING: list[tuple[float, float, float]] = [
    (0, 1, 0),
    (1, float("inf"), 1),
]


def _round_to_increment(value: float, increment: float) -> float:
    """Round a value to the nearest increment using arithmetic rounding (half up).

    Python's built-in round() uses banker's rounding (half to even), but FDA
    rounding rules require standard arithmetic rounding (half up).
    """
    if increment == 0:
        return 0.0
    # Use arithmetic rounding: floor(value/increment + 0.5)
    return math.floor(value / increment + 0.5) * increment


def apply_fda_rounding(value: float, nutrient_name: str) -> float:
    """Apply FDA rounding rules to a per-serving nutrient value.

    Args:
        value: Nutrient amount per serving.
        nutrient_name: Standard nutrient name.

    Returns:
        Rounded label value.
    """
    rules = FDA_ROUNDING_TABLE.get(nutrient_name, _DEFAULT_ROUNDING)

    for min_val, max_val, increment in rules:
        if min_val <= value < max_val:
            if increment == 0:
                return 0.0
            return _round_to_increment(value, increment)

    # Fallback
    return _round_to_increment(value, 1)


def label_value_to_interval(
    label_value: float,
    nutrient_name: str,
) -> tuple[float, float]:
    """Convert a Nutrition Facts label value to a possible true-value interval.

    Reverses FDA rounding rules to produce the interval of values that would
    round to the given label value.

    Args:
        label_value: Rounded value appearing on the Nutrition Facts label.
        nutrient_name: Standard nutrient name (for rounding rules).

    Returns:
        (lower_bound, upper_bound) tuple. Bounds are inclusive-exclusive.
    """
    rules = FDA_ROUNDING_TABLE.get(nutrient_name, _DEFAULT_ROUNDING)

    if label_value == 0:
        # Find the "express as 0" threshold
        for min_val, max_val, increment in rules:
            if increment == 0:
                return (0.0, max_val)
        return (0.0, 1.0)

    # First, find the correct rule by value range
    matched_rule = None
    for min_val, max_val, increment in rules:
        if min_val <= label_value < max_val:
            matched_rule = (min_val, max_val, increment)
            break

    if matched_rule is None:
        # Fallback: use last rule
        matched_rule = rules[-1]

    min_val, max_val, increment = matched_rule

    if increment == 0:
        return (0.0, max_val)

    half_inc = increment / 2.0
    lower = max(label_value - half_inc, min_val)
    upper = min(label_value + half_inc, max_val)
    return (lower, upper)


def within_interval(predicted: float, interval: tuple[float, float]) -> bool:
    """Check if a predicted value falls within an interval.

    Args:
        predicted: Predicted value.
        interval: (lower, upper) tuple, inclusive-exclusive.

    Returns:
        True if predicted is within the interval.
    """
    lo, hi = interval
    return lo <= predicted < hi


def interval_overlap(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """Check if two intervals overlap.

    Args:
        a: First interval as (lower, upper).
        b: Second interval as (lower, upper).

    Returns:
        True if the intervals overlap.
    """
    return a[0] < b[1] and b[0] < a[1]


def safe_div(a: float, b: float, default: float = 0.0) -> float:
    """Safely divide, returning default if denominator is 0."""
    if abs(b) < 1e-15:
        return default
    return a / b


def is_close(a: float, b: float, rtol: float = 1e-5, atol: float = 1e-8) -> bool:
    """Check if two floats are close using relative and absolute tolerance."""
    return math.isclose(a, b, rel_tol=rtol, abs_tol=atol)
