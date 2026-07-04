"""Tests for Foundation Foods data adapter."""

from __future__ import annotations

from pathlib import Path

import pytest


FF_JSON_PATH = Path(__file__).parent.parent.parent.parent / "db" / "FoodData_Central_foundation_food_json_2026-04-30" / "FoodData_Central_foundation_food_json_2026-04-30.json"


@pytest.fixture(scope="module")
def ff_adapter():
    """Load the Foundation Foods adapter with real data."""
    from nusol.data.foundation import FoundationFoodsAdapter

    if not FF_JSON_PATH.exists():
        pytest.skip(f"Foundation Foods JSON not found at {FF_JSON_PATH}")

    adapter = FoundationFoodsAdapter()
    adapter.load(FF_JSON_PATH)
    return adapter


class TestFoundationLoad:
    """Tests for loading Foundation Foods data."""

    def test_load_succeeds(self, ff_adapter):
        assert len(ff_adapter) > 0

    def test_all_have_ndb(self, ff_adapter):
        """Every Foundation food should have an ndbNumber."""
        for fdc_id in list(ff_adapter._data.keys())[:50]:
            food = ff_adapter._data[fdc_id]
            assert food.get("ndbNumber") is not None

    def test_get_by_ndb_number(self, ff_adapter):
        """Should be able to look up by ndbNumber."""
        # Find a known ndbNumber
        sample = next(iter(ff_adapter._ndb_index.keys()))
        profile = ff_adapter.get_by_ndb_number(sample)
        assert profile is not None
        assert len(profile.nutrients) > 0

    def test_get_nutrient_profile(self, ff_adapter):
        fdc_id = next(iter(ff_adapter._data.keys()))
        profile = ff_adapter.get_nutrient_profile(fdc_id)
        assert profile is not None
        assert profile.description != ""

    def test_has_ndb(self, ff_adapter):
        sample = next(iter(ff_adapter._ndb_index.keys()))
        assert ff_adapter.has_ndb(sample)
        assert not ff_adapter.has_ndb("99999999")
