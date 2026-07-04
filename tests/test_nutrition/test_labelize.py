"""Tests for labelized simulation."""

from __future__ import annotations

import pytest


class TestLabelizeNutrients:
    """Tests for labelize_nutrients."""

    def test_basic_labelize(self):
        from nusol.nutrition.labelize import labelize_nutrients
        from nusol.core.schema import NutrientRecord

        true_nutrients = [
            NutrientRecord(nutrient_id=1008, nutrient_number="208", name="Energy", amount=250.0, unit="kcal"),
            NutrientRecord(nutrient_id=1003, nutrient_number="203", name="Protein", amount=10.5, unit="g"),
        ]
        serving_size_g = 55.0

        labeled = labelize_nutrients(true_nutrients, serving_size_g)
        assert len(labeled) == 2

        # Energy: 250 * 55/100 = 137.5 per serving → rounded to nearest 10 (>50) = 140
        assert labeled[0].name == "Energy"
        assert labeled[0].amount == 140.0  # round(137.5/10)*10 = round(13.75)*10

    def test_labelize_preserves_metadata(self):
        from nusol.nutrition.labelize import labelize_nutrients
        from nusol.core.schema import NutrientRecord

        true = [
            NutrientRecord(nutrient_id=1004, nutrient_number="204", name="Total lipid (fat)", amount=15.0, unit="g", rank=800),
        ]
        labeled = labelize_nutrients(true, serving_size_g=28.0)
        assert labeled[0].nutrient_id == 1004
        assert labeled[0].rank == 800


class TestBuildLabelIntervals:
    """Tests for build_label_intervals."""

    def test_build_intervals(self):
        from nusol.nutrition.labelize import build_label_intervals
        from nusol.core.schema import NutrientRecord

        # Simulated label values: 140 kcal per 55g serving
        label_nutrients = [
            NutrientRecord(nutrient_id=1008, nutrient_number="208", name="Energy", amount=140.0, unit="kcal"),
        ]
        serving_size_g = 55.0

        intervals = build_label_intervals(label_nutrients, serving_size_g)
        assert len(intervals) == 1
        # 140 kcal label → interval [135, 145) per serving (since nearest 10)
        # Per 100g: lower=135*100/55=245.45, upper=145*100/55=263.64
        assert intervals[0].lower_bound == pytest.approx(245.45, rel=0.05)
        assert intervals[0].upper_bound == pytest.approx(263.64, rel=0.05)

    def test_zero_label_value(self):
        from nusol.nutrition.labelize import build_label_intervals
        from nusol.core.schema import NutrientRecord

        label_nutrients = [
            NutrientRecord(nutrient_id=1004, nutrient_number="204", name="Total lipid (fat)", amount=0.0, unit="g"),
        ]
        intervals = build_label_intervals(label_nutrients, serving_size_g=30.0)
        assert intervals[0].lower_bound == 0.0
        assert intervals[0].upper_bound > 0


class TestSimulateNutritionFacts:
    """Tests for the full simulate_nutrition_facts pipeline."""

    def test_simulate(self):
        from nusol.nutrition.labelize import simulate_nutrition_facts
        from nusol.core.schema import NutrientRecord

        true_nutrients = [
            NutrientRecord(nutrient_id=1008, nutrient_number="208", name="Energy", amount=250.0, unit="kcal"),
            NutrientRecord(nutrient_id=1004, nutrient_number="204", name="Total lipid (fat)", amount=12.0, unit="g"),
            NutrientRecord(nutrient_id=1003, nutrient_number="203", name="Protein", amount=8.0, unit="g"),
        ]
        serving_size_g = 55.0

        label_nutrients, intervals = simulate_nutrition_facts(true_nutrients, serving_size_g)
        assert len(label_nutrients) == 3
        assert len(intervals) == 3
        # Check intervals have bounds set
        for interval in intervals:
            assert interval.lower_bound is not None
            assert interval.upper_bound is not None
            assert interval.lower_bound <= interval.upper_bound
