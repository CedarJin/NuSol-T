"""Tests for NutrientRegistry."""

from __future__ import annotations

import pytest


class TestNutrientRegistry:
    """Tests for NutrientRegistry."""

    def test_create_registry(self):
        from nusol.core.nutrient_registry import NutrientRegistry

        reg = NutrientRegistry()
        assert reg.nutrient_count > 0

    def test_get_by_id(self, nutrient_registry):
        entry = nutrient_registry.get_by_id(1008)
        assert entry is not None
        assert entry["name"] == "Energy"
        assert entry["unit"] == "kcal"

    def test_get_by_id_missing(self, nutrient_registry):
        assert nutrient_registry.get_by_id(999999) is None

    def test_get_by_name(self, nutrient_registry):
        entry = nutrient_registry.get_by_name("Energy")
        assert entry is not None
        assert entry["nutrient_id"] == 1008

    def test_get_by_name_case_insensitive(self, nutrient_registry):
        entry = nutrient_registry.get_by_name("energy")
        assert entry is not None
        assert entry["name"] == "Energy"

    def test_get_by_name_missing(self, nutrient_registry):
        assert nutrient_registry.get_by_name("NotANutrient") is None

    def test_get_by_number(self, nutrient_registry):
        entry = nutrient_registry.get_by_number("208")
        assert entry is not None
        assert entry["name"] == "Energy"

    def test_get_by_number_missing(self, nutrient_registry):
        assert nutrient_registry.get_by_number("999") is None

    def test_get_unit(self, nutrient_registry):
        assert nutrient_registry.get_unit("Energy") == "kcal"
        assert nutrient_registry.get_unit("Protein") == "g"
        assert nutrient_registry.get_unit("Sodium, Na") == "mg"

    def test_is_label_nutrient(self, nutrient_registry):
        assert nutrient_registry.is_label_nutrient("Energy")
        assert nutrient_registry.is_label_nutrient("Total lipid (fat)")
        assert nutrient_registry.is_label_nutrient("Protein")

    def test_is_not_label_nutrient(self, nutrient_registry):
        assert not nutrient_registry.is_label_nutrient("Water")
        assert not nutrient_registry.is_label_nutrient("Ash")
        assert not nutrient_registry.is_label_nutrient("Caffeine")

    def test_contains(self, nutrient_registry):
        assert "Energy" in nutrient_registry
        assert "energy" in nutrient_registry
        assert "NotANutrient" not in nutrient_registry

    def test_all_names(self, nutrient_registry):
        names = nutrient_registry.all_names
        assert isinstance(names, list)
        assert "Energy" in names
        assert "Protein" in names

    def test_label_nutrient_names(self, nutrient_registry):
        names = nutrient_registry.label_nutrient_names
        assert "Energy" in names
        assert "Protein" in names
        assert "Water" not in names

    def test_len(self, nutrient_registry):
        assert len(nutrient_registry) == nutrient_registry.nutrient_count
        assert len(nutrient_registry) > 30

    def test_singleton(self):
        from nusol.core.nutrient_registry import (
            get_nutrient_registry,
        )

        reg1 = get_nutrient_registry()
        reg2 = get_nutrient_registry()
        assert reg1 is reg2
