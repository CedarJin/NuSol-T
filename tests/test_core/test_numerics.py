"""Tests for numerics utilities (FDA rounding, intervals)."""

from __future__ import annotations

import pytest


class TestFDARounding:
    """Tests for FDA rounding rule application."""

    def test_energy_below_5_rounds_to_0(self):
        from nusol.utils.numerics import apply_fda_rounding

        assert apply_fda_rounding(3.0, "Energy") == 0.0
        assert apply_fda_rounding(0.0, "Energy") == 0.0

    def test_energy_5_to_50(self):
        from nusol.utils.numerics import apply_fda_rounding

        assert apply_fda_rounding(23.0, "Energy") == 25.0  # nearest 5
        assert apply_fda_rounding(48.0, "Energy") == 50.0

    def test_energy_above_50(self):
        from nusol.utils.numerics import apply_fda_rounding

        assert apply_fda_rounding(123.0, "Energy") == 120.0  # nearest 10
        assert apply_fda_rounding(255.0, "Energy") == 260.0

    def test_fat_below_0_5_rounds_to_0(self):
        from nusol.utils.numerics import apply_fda_rounding

        assert apply_fda_rounding(0.3, "Total lipid (fat)") == 0.0

    def test_fat_0_5_to_5(self):
        from nusol.utils.numerics import apply_fda_rounding

        assert apply_fda_rounding(1.3, "Total lipid (fat)") == 1.5
        assert apply_fda_rounding(4.2, "Total lipid (fat)") == 4.0

    def test_fat_above_5(self):
        from nusol.utils.numerics import apply_fda_rounding

        assert apply_fda_rounding(12.3, "Total lipid (fat)") == 12.0
        assert apply_fda_rounding(12.6, "Total lipid (fat)") == 13.0

    def test_sodium_below_5(self):
        from nusol.utils.numerics import apply_fda_rounding

        assert apply_fda_rounding(3.0, "Sodium, Na") == 0.0

    def test_sodium_5_to_140(self):
        from nusol.utils.numerics import apply_fda_rounding

        assert apply_fda_rounding(120.0, "Sodium, Na") == 120.0  # nearest 5
        assert apply_fda_rounding(123.0, "Sodium, Na") == 125.0

    def test_sodium_above_140(self):
        from nusol.utils.numerics import apply_fda_rounding

        assert apply_fda_rounding(480.0, "Sodium, Na") == 480.0  # nearest 10
        assert apply_fda_rounding(485.0, "Sodium, Na") == 490.0  # nearest 10
        assert apply_fda_rounding(482.0, "Sodium, Na") == 480.0

    def test_unknown_nutrient_rounds_to_nearest_1(self):
        from nusol.utils.numerics import apply_fda_rounding

        assert apply_fda_rounding(5.3, "Unknown Nutrient") == 5.0
        assert apply_fda_rounding(5.6, "Unknown Nutrient") == 6.0


class TestLabelValueToInterval:
    """Tests for converting label values to true-value intervals."""

    def test_zero_label_value(self):
        from nusol.utils.numerics import label_value_to_interval

        lo, hi = label_value_to_interval(0.0, "Total lipid (fat)")
        assert lo == 0.0
        assert hi == 0.5  # < 0.5g rounds to 0

    def test_intermediate_fat_value(self):
        from nusol.utils.numerics import label_value_to_interval

        # 1.5g fat (0.5-1.0 was rounded to nearest 0.5)
        lo, hi = label_value_to_interval(1.5, "Total lipid (fat)")
        assert lo == pytest.approx(1.25)
        assert hi == pytest.approx(1.75)

    def test_large_energy_value(self):
        from nusol.utils.numerics import label_value_to_interval

        # 250 kcal (> 50, nearest 10)
        lo, hi = label_value_to_interval(250.0, "Energy")
        assert lo == pytest.approx(245.0)
        assert hi == pytest.approx(255.0)

    def test_sodium_value(self):
        from nusol.utils.numerics import label_value_to_interval

        # 120 mg (5-140, nearest 5)
        lo, hi = label_value_to_interval(120.0, "Sodium, Na")
        assert lo == pytest.approx(117.5)
        assert hi == pytest.approx(122.5)


class TestWithinInterval:
    """Tests for within_interval."""

    def test_within(self):
        from nusol.utils.numerics import within_interval

        assert within_interval(0.3, (0.0, 0.5))

    def test_at_lower_bound(self):
        from nusol.utils.numerics import within_interval

        assert within_interval(0.0, (0.0, 0.5))

    def test_at_upper_bound_exclusive(self):
        from nusol.utils.numerics import within_interval

        assert not within_interval(0.5, (0.0, 0.5))

    def test_outside(self):
        from nusol.utils.numerics import within_interval

        assert not within_interval(0.6, (0.0, 0.5))


class TestIntervalOverlap:
    """Tests for interval_overlap."""

    def test_overlapping(self):
        from nusol.utils.numerics import interval_overlap

        assert interval_overlap((0, 5), (3, 8))

    def test_adjacent(self):
        from nusol.utils.numerics import interval_overlap

        # [0, 3) and [3, 6) — don't overlap (upper is exclusive)
        assert not interval_overlap((0, 3), (3, 6))

    def test_contained(self):
        from nusol.utils.numerics import interval_overlap

        assert interval_overlap((1, 2), (0, 5))

    def test_disjoint(self):
        from nusol.utils.numerics import interval_overlap

        assert not interval_overlap((0, 1), (2, 3))


class TestSafeDiv:
    """Tests for safe_div."""

    def test_normal_division(self):
        from nusol.utils.numerics import safe_div

        assert safe_div(10.0, 2.0) == 5.0

    def test_division_by_zero_returns_default(self):
        from nusol.utils.numerics import safe_div

        assert safe_div(10.0, 0.0) == 0.0
        assert safe_div(10.0, 0.0, default=-1.0) == -1.0


class TestIsClose:
    """Tests for is_close."""

    def test_close_values(self):
        from nusol.utils.numerics import is_close

        assert is_close(1.0, 1.0000001)

    def test_not_close(self):
        from nusol.utils.numerics import is_close

        assert not is_close(1.0, 1.01)
