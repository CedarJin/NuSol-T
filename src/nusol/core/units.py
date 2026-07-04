"""Unit conversion utilities for nutrient values."""

from __future__ import annotations


class UnitConverter:
    """Convert between nutrient units and between per-serving / per-100g bases."""

    # Conversion factors to standard unit (g for macros, mg for micros, kcal for energy)
    _MASS_TO_G: dict[str, float] = {
        "g": 1.0,
        "mg": 0.001,
        "µg": 0.000001,
        "mcg": 0.000001,
    }

    _ENERGY_TO_KCAL: dict[str, float] = {
        "kcal": 1.0,
        "kJ": 1.0 / 4.184,
    }

    _IU_CONVERSIONS: dict[str, float] = {
        # Vitamin D: 1 IU = 0.025 µg
        "Vitamin D": 0.025,  # IU → µg
        "Vitamin E (alpha-tocopherol)": 0.67,  # IU → mg
        "Vitamin A, RAE": 0.3,  # IU → µg RAE (approximate)
    }

    @classmethod
    def is_energy(cls, unit: str) -> bool:
        """Check if the unit is an energy unit."""
        return unit in cls._ENERGY_TO_KCAL

    @classmethod
    def is_mass(cls, unit: str) -> bool:
        """Check if the unit is a mass unit."""
        return unit in cls._MASS_TO_G

    @classmethod
    def convert_mass(cls, value: float, from_unit: str, to_unit: str) -> float:
        """Convert between mass units (g, mg, µg)."""
        if from_unit == to_unit:
            return value
        g_value = value * cls._MASS_TO_G.get(from_unit, 1.0)
        return g_value / cls._MASS_TO_G.get(to_unit, 1.0)

    @classmethod
    def convert_energy(cls, value: float, from_unit: str, to_unit: str) -> float:
        """Convert between energy units (kcal, kJ)."""
        if from_unit == to_unit:
            return value
        kcal_value = value * cls._ENERGY_TO_KCAL.get(from_unit, 1.0)
        if to_unit == "kcal":
            return kcal_value
        if to_unit == "kJ":
            return kcal_value * 4.184
        return kcal_value

    @classmethod
    def convert_iu(cls, value: float, nutrient_name: str, to_unit: str) -> float:
        """Convert from IU to mass unit for a specific vitamin."""
        factor = cls._IU_CONVERSIONS.get(nutrient_name)
        if factor is None:
            return value  # Can't convert, return as-is
        if to_unit in ("µg", "mcg"):
            return value * factor
        if to_unit == "mg":
            return value * factor * 0.001
        return value


def convert_to_per_100g(
    amount_per_serving: float,
    serving_size_g: float,
) -> float:
    """Convert a nutrient amount from per-serving to per-100g basis.

    Args:
        amount_per_serving: Nutrient amount per serving.
        serving_size_g: Serving size in grams.

    Returns:
        Nutrient amount per 100g.

    Raises:
        ValueError: If serving_size_g <= 0.
    """
    if serving_size_g <= 0:
        raise ValueError(f"Serving size must be positive, got {serving_size_g}")
    return amount_per_serving * 100.0 / serving_size_g


def convert_to_per_serving(
    amount_per_100g: float,
    serving_size_g: float,
) -> float:
    """Convert a nutrient amount from per-100g to per-serving basis.

    Args:
        amount_per_100g: Nutrient amount per 100g.
        serving_size_g: Serving size in grams.

    Returns:
        Nutrient amount per serving.
    """
    if serving_size_g <= 0:
        raise ValueError(f"Serving size must be positive, got {serving_size_g}")
    return amount_per_100g * serving_size_g / 100.0
