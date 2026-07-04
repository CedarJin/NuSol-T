"""Tests for unit conversion utilities."""

from __future__ import annotations

import pytest


class TestUnitConverter:
    """Tests for UnitConverter."""

    def test_is_energy(self):
        from nusol.core.units import UnitConverter

        assert UnitConverter.is_energy("kcal")
        assert UnitConverter.is_energy("kJ")
        assert not UnitConverter.is_energy("g")

    def test_is_mass(self):
        from nusol.core.units import UnitConverter

        assert UnitConverter.is_mass("g")
        assert UnitConverter.is_mass("mg")
        assert UnitConverter.is_mass("µg")
        assert not UnitConverter.is_mass("kcal")

    def test_convert_mass_g_to_mg(self):
        from nusol.core.units import UnitConverter

        assert UnitConverter.convert_mass(1.0, "g", "mg") == pytest.approx(1000.0)

    def test_convert_mass_mg_to_g(self):
        from nusol.core.units import UnitConverter

        assert UnitConverter.convert_mass(500.0, "mg", "g") == pytest.approx(0.5)

    def test_convert_mass_g_to_ug(self):
        from nusol.core.units import UnitConverter

        assert UnitConverter.convert_mass(1.0, "g", "µg") == pytest.approx(1_000_000.0)

    def test_convert_mass_same_unit(self):
        from nusol.core.units import UnitConverter

        assert UnitConverter.convert_mass(42.0, "g", "g") == 42.0

    def test_convert_energy_kcal_to_kj(self):
        from nusol.core.units import UnitConverter

        assert UnitConverter.convert_energy(100.0, "kcal", "kJ") == pytest.approx(418.4)

    def test_convert_energy_kj_to_kcal(self):
        from nusol.core.units import UnitConverter

        assert UnitConverter.convert_energy(418.4, "kJ", "kcal") == pytest.approx(100.0)

    def test_convert_energy_same_unit(self):
        from nusol.core.units import UnitConverter

        assert UnitConverter.convert_energy(50.0, "kcal", "kcal") == 50.0

    def test_convert_iu_vitamin_d(self):
        from nusol.core.units import UnitConverter

        # 400 IU Vitamin D = 10 µg
        result = UnitConverter.convert_iu(400.0, "Vitamin D", "µg")
        assert result == pytest.approx(10.0)

    def test_convert_iu_unknown_nutrient(self):
        from nusol.core.units import UnitConverter

        result = UnitConverter.convert_iu(100.0, "Unknown", "µg")
        assert result == 100.0  # unchanged


class TestConvertToPer100g:
    """Tests for per-serving / per-100g conversions."""

    def test_basic_conversion(self):
        from nusol.core.units import convert_to_per_100g

        # 10g fat per 28g serving → per 100g
        result = convert_to_per_100g(10.0, 28.0)
        assert result == pytest.approx(35.714, rel=0.01)

    def test_100g_serving_is_identity(self):
        from nusol.core.units import convert_to_per_100g

        result = convert_to_per_100g(5.0, 100.0)
        assert result == 5.0

    def test_zero_serving_size_raises_error(self):
        from nusol.core.units import convert_to_per_100g

        with pytest.raises(ValueError, match="positive"):
            convert_to_per_100g(10.0, 0.0)

    def test_negative_serving_size_raises_error(self):
        from nusol.core.units import convert_to_per_100g

        with pytest.raises(ValueError, match="positive"):
            convert_to_per_100g(10.0, -5.0)


class TestConvertToPerServing:
    """Tests for per-100g to per-serving conversion."""

    def test_basic_conversion(self):
        from nusol.core.units import convert_to_per_serving

        # 35.7g fat per 100g → 28g serving
        result = convert_to_per_serving(35.7, 28.0)
        assert result == pytest.approx(10.0, rel=0.01)

    def test_100g_serving_is_identity(self):
        from nusol.core.units import convert_to_per_serving

        result = convert_to_per_serving(5.0, 100.0)
        assert result == 5.0

    def test_zero_serving_size_raises_error(self):
        from nusol.core.units import convert_to_per_serving

        with pytest.raises(ValueError):
            convert_to_per_serving(10.0, 0.0)
