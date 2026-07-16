"""Tests for fortification classification and FNDDS export diagnostics."""

from __future__ import annotations

import json
from pathlib import Path

from nusol.data.fortification import (
    build_fortification_ingredient,
    classify_export_failure,
    fortification_diagnostics,
    is_fortificant,
    suspected_nutrients_for_fortificant,
)


def test_fortificant_detection_by_code_and_name() -> None:
    assert is_fortificant(999328, "Vitamin D as ingredient")
    assert is_fortificant("123", "Reduced iron")
    assert is_fortificant("123", "Calcium carbonate")
    assert not is_fortificant(123, "Wheat flour")


def test_suspected_nutrients_for_fortificant_name() -> None:
    assert suspected_nutrients_for_fortificant("Vitamin D as ingredient") == (
        "vitamin_d_mcg",
    )
    assert "iron_mg" in suspected_nutrients_for_fortificant("Reduced iron")
    assert "calcium_mg" in suspected_nutrients_for_fortificant("Calcium carbonate")


def test_build_fortification_diagnostics() -> None:
    fortificant = build_fortification_ingredient(
        {
            "description": "Iron as ingredient",
            "ingredient_code": 999303,
            "weight_g": 0.01,
        },
        total_weight_g=100.0,
    )

    diagnostics = fortification_diagnostics(
        [fortificant],
        [{"nutrient": "iron_mg", "reason": "fortification_dominated"}],
    )

    assert diagnostics["has_fortification"] is True
    assert diagnostics["suspected_fortified_nutrients"] == ["iron_mg"]
    assert diagnostics["fortificant_ingredients"][0]["reason"] == "fortificant_code"


def test_classify_single_base_with_fortification() -> None:
    assert classify_export_failure(
        n_regular_ingredients=1,
        n_fortificants=2,
    ) == "single_base_with_fortification"


class _FakeFNDDS:
    def get_recipe(self, fdc_id: int):
        return {
            "fdc_id": fdc_id,
            "description": "Orange juice, 100%, with calcium and vitamin D",
            "ingredients": [
                {
                    "ingredient_code": 9206,
                    "description": "Orange juice",
                    "weight_g": 100.0,
                },
                {
                    "ingredient_code": 999301,
                    "description": "Calcium as ingredient",
                    "weight_g": 0.013,
                },
                {
                    "ingredient_code": 999328,
                    "description": "Vitamin D as ingredient",
                    "weight_g": 0.01,
                },
            ],
            "final_nutrients": None,
        }


class _FakeSR:
    pass


def test_export_writes_fortification_failure_artifact(tmp_path: Path) -> None:
    from scripts.export_fndds_recipes import export_recipe

    result = export_recipe(2709189, _FakeFNDDS(), _FakeSR(), tmp_path)

    assert result is None
    failure_path = tmp_path / "recipe_2709189_export_failure.json"
    payload = json.loads(failure_path.read_text())
    assert payload["failure_category"] == "single_base_with_fortification"
    assert payload["fortification"]["has_fortification"] is True
    nutrients = payload["fortification"]["suspected_fortified_nutrients"]
    assert "calcium_mg" in nutrients
    assert "vitamin_d_mcg" in nutrients
