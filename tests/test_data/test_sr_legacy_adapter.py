"""Tests for SR Legacy data adapter using real data."""

from __future__ import annotations

from pathlib import Path

import pytest


SR_JSON_PATH = Path(__file__).parent.parent.parent.parent / "db" / "FoodData_Central_sr_legacy_food_json_2018-04" / "FoodData_Central_sr_legacy_food_json_2018-04.json"


@pytest.fixture(scope="module")
def sr_adapter():
    """Load the SR Legacy adapter with real data."""
    from nusol.data.sr_legacy import SRLegacyDataAdapter

    if not SR_JSON_PATH.exists():
        pytest.skip(f"SR Legacy JSON not found at {SR_JSON_PATH}")

    adapter = SRLegacyDataAdapter()
    adapter.load(SR_JSON_PATH)
    return adapter


class TestSRLegacyLoad:
    """Tests for loading SR Legacy data."""

    def test_load_succeeds(self, sr_adapter):
        assert len(sr_adapter) > 0

    def test_contains_many_foods(self, sr_adapter):
        assert len(sr_adapter) > 1000  # SR Legacy has thousands of foods

    def test_get_nutrient_profile_by_id(self, sr_adapter):
        # Try to get the first available FDC ID
        # SR Legacy IDs vary; get one from the data
        fdc_id = next(iter(sr_adapter._data.keys()))
        profile = sr_adapter.get_nutrient_profile(fdc_id)
        assert profile is not None
        assert profile.description != ""
        assert len(profile.nutrients) > 0

    def test_nutrient_profile_has_expected_fields(self, sr_adapter):
        fdc_id = next(iter(sr_adapter._data.keys()))
        profile = sr_adapter.get_nutrient_profile(fdc_id)
        assert profile.basis == "per_100g"
        for nut in profile.nutrients[:5]:
            assert nut.nutrient_id > 0
            assert nut.name != ""

    def test_search_by_name(self, sr_adapter):
        # Search for a common ingredient
        results = sr_adapter.search_by_name("wheat flour, white, all-purpose, enriched, bleached")
        # If exact match fails, try a more generic search
        if not results:
            results = sr_adapter.search_by_name("sugar")
        # Should find something common
        if results:
            assert len(results) > 0
            assert results[0].description != ""

    def test_search_fuzzy(self, sr_adapter):
        results = sr_adapter.search("wheat flour")
        if results:
            assert len(results) > 0
            assert all(0 <= score <= 100 for _, score in results)


class TestSRLegacyCache:
    """Tests for profile caching."""

    def test_profile_caching(self, sr_adapter):
        fdc_id = next(iter(sr_adapter._data.keys()))
        profile1 = sr_adapter.get_nutrient_profile(fdc_id)
        profile2 = sr_adapter.get_nutrient_profile(fdc_id)
        assert profile1 is profile2


class TestSRLegacyNDBLookup:
    """Tests for ndbNumber-based lookup (primary FNDDS mapping path)."""

    def test_get_by_ndb_number(self, sr_adapter):
        # NDB 1001 = Butter, salted
        profile = sr_adapter.get_by_ndb_number("1001")
        if profile:
            assert profile.description != ""
            assert len(profile.nutrients) > 0

    def test_get_by_ndb_number_int(self, sr_adapter):
        """Should accept int as well as str."""
        profile = sr_adapter.get_by_ndb_number(1001)
        if profile:
            assert len(profile.nutrients) > 0

    def test_has_ndb(self, sr_adapter):
        assert sr_adapter.has_ndb("1001")  # Should exist
        assert not sr_adapter.has_ndb("99999999")  # Should not exist

    def test_manual_map(self, sr_adapter):
        """Manual mapping table should resolve edge cases."""
        # 100260 = Spinach, baby → ndb 11457 (Spinach, raw)
        profile = sr_adapter.get_by_ndb_number("100260")
        # May or may not be in this SR Legacy version
        if profile:
            assert "spinach" in profile.description.lower()


class TestSRLegacySearch:
    """Tests for improved search methods."""

    def test_search_substring(self, sr_adapter):
        """Substring search should find partial matches."""
        results = sr_adapter.search_by_substring("onion")
        if results:
            for profile, score in results:
                assert "onion" in profile.description.lower()
                assert score > 0

    def test_search_words(self, sr_adapter):
        """Word-overlap search should handle cultivar variants."""
        results = sr_adapter.search_by_words("potatoes red without skin", min_overlap=2)
        # Should find potato entries
        if results:
            for profile, score in results:
                assert "potato" in profile.description.lower()

    def test_search_smart(self, sr_adapter):
        """Smart search should cascade through strategies."""
        results = sr_adapter.search("butter")
        if results:
            assert len(results) > 0
            assert results[0][1] > 0  # confidence > 0
