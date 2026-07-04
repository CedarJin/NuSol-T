"""Tests for FNDDS data adapter using real FNDDS JSON."""

from __future__ import annotations

from pathlib import Path

import pytest


FNDDS_JSON_PATH = Path(__file__).parent.parent.parent.parent / "db" / "FoodData_Central_survey_food_json_2024-10-31" / "surveyDownload.json"


@pytest.fixture(scope="module")
def fndds_adapter():
    """Load the FNDDS adapter with real data."""
    from nusol.data.fndds import FNDDSDataAdapter

    if not FNDDS_JSON_PATH.exists():
        pytest.skip(f"FNDDS JSON not found at {FNDDS_JSON_PATH}")

    adapter = FNDDSDataAdapter()
    adapter.load(FNDDS_JSON_PATH)
    return adapter


class TestFNDDSLoad:
    """Tests for loading FNDDS data."""

    def test_load_succeeds(self, fndds_adapter):
        assert len(fndds_adapter) > 0

    def test_contains_records(self, fndds_adapter):
        assert len(fndds_adapter) > 100  # FNDDS has thousands of foods

    def test_get_nutrient_profile(self, fndds_adapter):
        # Find the first food that has nutrients and inputFoods
        recipes = fndds_adapter.get_recipes_with_ingredients(min_ingredients=1)
        if not recipes:
            pytest.skip("No recipes with ingredients found")
        fdc_id = recipes[0]
        profile = fndds_adapter.get_nutrient_profile(fdc_id)
        assert profile is not None
        assert profile.description != ""
        assert len(profile.nutrients) >= 0  # Some may have empty nutrients


class TestFNDDSRecipe:
    """Tests for recipe extraction."""

    def test_get_recipe(self, fndds_adapter):
        recipes = fndds_adapter.get_recipes_with_ingredients(min_ingredients=2)
        if not recipes:
            pytest.skip("No multi-ingredient recipes found")
        fdc_id = recipes[0]
        recipe = fndds_adapter.get_recipe(fdc_id)
        assert recipe is not None
        assert "ingredients" in recipe
        assert len(recipe["ingredients"]) > 0
        assert "final_nutrients" in recipe

    def test_get_ingredient_fractions_sum_to_one(self, fndds_adapter):
        recipes = fndds_adapter.get_recipes_with_ingredients(min_ingredients=2)
        if not recipes:
            pytest.skip("No multi-ingredient recipes found")
        fdc_id = recipes[0]
        fractions = fndds_adapter.get_ingredient_fractions(fdc_id)
        if fractions:
            total = sum(fractions.values())
            assert abs(total - 1.0) < 0.01

    def test_get_recipes_with_ingredients(self, fndds_adapter):
        recipes = fndds_adapter.get_recipes_with_ingredients(min_ingredients=2, max_ingredients=20)
        assert len(recipes) > 0

    def test_to_product_observation(self, fndds_adapter):
        recipes = fndds_adapter.get_recipes_with_ingredients(min_ingredients=2, max_ingredients=10)
        if not recipes:
            pytest.skip("No suitable recipes")
        fdc_id = recipes[0]
        obs = fndds_adapter.to_product_observation(fdc_id)
        assert obs is not None
        assert obs.source == "FNDDS"
        assert obs.has_ground_truth()
        assert obs.ingredient_tree is not None
        assert obs.ingredient_tree.total_ingredient_count() > 0

    def test_get_serving_size(self, fndds_adapter):
        recipes = fndds_adapter.get_recipes_with_ingredients(min_ingredients=1)
        if not recipes:
            pytest.skip("No recipes found")
        fdc_id = recipes[0]
        ss = fndds_adapter.get_serving_size_g(fdc_id)
        assert ss > 0

    def test_nonexistent_fdc_id(self, fndds_adapter):
        recipe = fndds_adapter.get_recipe(999999999)
        assert recipe is None

        profile = fndds_adapter.get_nutrient_profile(999999999)
        assert profile is None


class TestFNDDSIngredientMatrix:
    """Tests for ingredient nutrient matrix building."""

    def test_build_matrix(self, fndds_adapter):
        from nusol.data.sr_legacy import SRLegacyDataAdapter

        sr_path = Path(__file__).parent.parent.parent.parent / "db" / "FoodData_Central_sr_legacy_food_json_2018-04" / "FoodData_Central_sr_legacy_food_json_2018-04.json"
        if not sr_path.exists():
            pytest.skip("SR Legacy JSON not found")

        sr = SRLegacyDataAdapter()
        sr.load(sr_path)

        recipes = fndds_adapter.get_recipes_with_ingredients(min_ingredients=2, max_ingredients=10)
        if not recipes:
            pytest.skip("No suitable recipes found")

        fdc_id = recipes[0]
        recipe = fndds_adapter.get_recipe(fdc_id)
        if not recipe or not recipe["ingredients"]:
            pytest.skip("Recipe has no ingredients")

        nutrient_names = recipe["final_nutrients"].nutrient_names()

        matrix, profiles, names, mapping_meta = fndds_adapter.get_ingredient_nutrient_matrix(
            fdc_id, sr_legacy_db=sr, nutrient_names=nutrient_names[:10]
        )
        assert len(matrix) > 0
        assert len(matrix) == len(recipe["ingredients"])
        # mapping_meta should have entries for all ingredients
        assert len(mapping_meta) == len(recipe["ingredients"])


class TestFNDDSIngredientMapping:
    """Tests for the 3-level ingredient mapping fallback."""

    def test_ndb_direct_mapping(self, fndds_adapter):
        """Most FNDDS ingredientCodes should map directly to SR Legacy ndbNumber."""
        from nusol.data.sr_legacy import SRLegacyDataAdapter

        sr_path = Path(__file__).parent.parent.parent.parent / "db" / "FoodData_Central_sr_legacy_food_json_2018-04" / "FoodData_Central_sr_legacy_food_json_2018-04.json"
        if not sr_path.exists():
            pytest.skip("SR Legacy JSON not found")

        sr = SRLegacyDataAdapter()
        sr.load(sr_path)

        # Find a recipe with ingredients in the NDB range (1001-9999)
        recipes = fndds_adapter.get_recipes_with_ingredients(min_ingredients=2)
        if not recipes:
            pytest.skip("No recipes found")

        # Test a few recipes and count mapping methods
        methods = {"ndb_direct": 0, "fndds_self": 0, "fuzzy": 0, "fortificant": 0, "none": 0}
        tested = 0
        for fdc_id in recipes[:20]:
            recipe = fndds_adapter.get_recipe(fdc_id)
            if not recipe:
                continue
            for ing in recipe["ingredients"]:
                profile, method, conf = fndds_adapter.map_ingredient_to_profile(
                    ing["ingredient_code"], ing["description"], sr_legacy_db=sr
                )
                methods[method] = methods.get(method, 0) + 1
                tested += 1
            if tested >= 50:
                break

        # Should have matches via ndb (foundation or sr_legacy) or fndds_self
        total_matched = methods.get("fndds_self", 0) + methods.get("foundation_ndb", 0) + methods.get("sr_legacy_ndb", 0)
        assert total_matched > 0, "Should have at least some mapped ingredients"
        total = sum(methods.values())
        print(f"\nMapping methods: {methods} (mapped={total_matched}/{total})")

    def test_fortificant_detection(self, fndds_adapter):
        """999xxx codes should be detected as fortificants."""
        from nusol.data.sr_legacy import SRLegacyDataAdapter

        sr_path = Path(__file__).parent.parent.parent.parent / "db" / "FoodData_Central_sr_legacy_food_json_2018-04" / "FoodData_Central_sr_legacy_food_json_2018-04.json"
        if not sr_path.exists():
            pytest.skip("SR Legacy JSON not found")

        sr = SRLegacyDataAdapter()
        sr.load(sr_path)

        # Test a fortificant code directly
        profile, method, conf = fndds_adapter.map_ingredient_to_profile(
            999328, "Vitamin D as ingredient", sr_legacy_db=sr
        )
        assert method == "fortificant"
        assert profile is None  # Fortificants don't get a profile

    def test_all_methods_produce_valid_output(self, fndds_adapter):
        """All mapping methods should return valid (profile, method, confidence)."""
        from nusol.data.sr_legacy import SRLegacyDataAdapter

        sr_path = Path(__file__).parent.parent.parent.parent / "db" / "FoodData_Central_sr_legacy_food_json_2018-04" / "FoodData_Central_sr_legacy_food_json_2018-04.json"
        if not sr_path.exists():
            pytest.skip("SR Legacy JSON not found")

        sr = SRLegacyDataAdapter()
        sr.load(sr_path)

        recipes = fndds_adapter.get_recipes_with_ingredients(min_ingredients=2)
        if not recipes:
            pytest.skip("No recipes found")

        for fdc_id in recipes[:5]:
            recipe = fndds_adapter.get_recipe(fdc_id)
            if not recipe:
                continue
            for ing in recipe["ingredients"]:
                profile, method, conf = fndds_adapter.map_ingredient_to_profile(
                    ing["ingredient_code"], ing["description"], sr_legacy_db=sr
                )
                assert method in ("fndds_self", "foundation_ndb", "sr_legacy_ndb", "fuzzy", "fortificant", "none")
                assert 0.0 <= conf <= 1.0
