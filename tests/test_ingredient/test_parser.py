"""Tests for IngredientParser."""

from __future__ import annotations

import pytest


class TestIngredientParser:
    """Tests for ingredient list parsing."""

    def test_simple_comma_separated(self):
        from nusol.ingredient.parser import IngredientParser

        parser = IngredientParser()
        tree = parser.parse_simple("FLOUR, SUGAR, OIL, SALT")

        assert tree.main_ingredient_count() == 4
        assert tree.total_ingredient_count() == 4
        assert tree.root_ingredients[0].name == "FLOUR"
        assert tree.root_ingredients[0].position == 0

    def test_parenthetical_sub_ingredients(self):
        from nusol.ingredient.parser import IngredientParser

        parser = IngredientParser()
        tree = parser.parse("ENRICHED FLOUR (WHEAT FLOUR, NIACIN, IRON), SUGAR, OIL.")

        assert len(tree.root_ingredients) == 3
        flour = tree.root_ingredients[0]
        assert flour.is_compound
        assert flour.name == "ENRICHED FLOUR"
        assert len(flour.children) == 3
        assert flour.children[0].name == "WHEAT FLOUR"
        assert flour.children[0].is_sub_ingredient
        assert flour.leaf_count() == 3

    def test_two_percent_group(self):
        from nusol.ingredient.parser import IngredientParser

        parser = IngredientParser()
        tree = parser.parse("SUGAR, SALT, CONTAINS 2% OR LESS OF: SPICES, NATURAL FLAVOR")

        assert tree.main_ingredient_count() == 2
        assert len(tree.two_percent_group) == 2
        assert tree.two_percent_group[0].is_low_impact
        assert tree.two_percent_group[0].name == "SPICES"

    def test_two_percent_alt_pattern(self):
        from nusol.ingredient.parser import IngredientParser

        parser = IngredientParser()
        tree = parser.parse("FLOUR, SUGAR, CONTAINS LESS THAN 2% OF: SALT, YEAST")

        assert len(tree.two_percent_group) == 2

    def test_removes_asterisk_markers(self):
        from nusol.ingredient.parser import IngredientParser

        parser = IngredientParser()
        tree = parser.parse_simple("FLOUR*, SUGAR**, OIL***")

        names = [n.name for n in tree.root_ingredients]
        assert "FLOUR" in names[0]

    def test_period_termination(self):
        from nusol.ingredient.parser import IngredientParser

        parser = IngredientParser()
        tree = parser.parse("FLOUR, SUGAR, SALT.")

        assert tree.main_ingredient_count() == 3
        assert tree.root_ingredients[-1].name == "SALT"

    def test_empty_input(self):
        from nusol.ingredient.parser import IngredientParser

        parser = IngredientParser()
        tree = parser.parse("")
        assert tree.main_ingredient_count() == 0
        assert tree.total_ingredient_count() == 0

    def test_and_or_handling(self):
        from nusol.ingredient.parser import IngredientParser

        parser = IngredientParser()
        tree = parser.parse("SOYBEAN AND/OR CANOLA OIL, SALT")

        assert tree.main_ingredient_count() == 2

    def test_compound_with_sub_and_two_pct(self):
        from nusol.ingredient.parser import IngredientParser

        parser = IngredientParser()
        tree = parser.parse(
            "ENRICHED FLOUR (WHEAT, NIACIN), SUGAR, "
            "CONTAINS 2% OR LESS OF: COCOA (PROCESSED WITH ALKALI), SALT"
        )

        assert len(tree.root_ingredients) == 2
        assert tree.root_ingredients[0].is_compound
        assert len(tree.two_percent_group) == 2
        # Check cocoa sub-ingredient
        cocoa = tree.two_percent_group[0]
        assert cocoa.is_compound
        assert len(cocoa.children) == 1
