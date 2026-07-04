"""Shared fixtures for NuSol-T tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def nutrient_registry():
    """Return a fresh NutrientRegistry instance."""
    from nusol.core.nutrient_registry import NutrientRegistry

    return NutrientRegistry()


@pytest.fixture
def sample_nutrient_record():
    """Return a sample NutrientRecord."""
    from nusol.core.schema import NutrientRecord

    return NutrientRecord(
        nutrient_id=1008,
        nutrient_number="208",
        name="Energy",
        amount=250.0,
        unit="kcal",
        rank=300,
    )


@pytest.fixture
def sample_nutrient_profile():
    """Return a sample NutrientProfile with multiple nutrients."""
    from nusol.core.schema import NutrientRecord, NutrientProfile

    return NutrientProfile(
        fdc_id=999999,
        description="Test Food",
        nutrients=[
            NutrientRecord(nutrient_id=1008, nutrient_number="208", name="Energy", amount=250.0, unit="kcal", rank=300),
            NutrientRecord(nutrient_id=1003, nutrient_number="203", name="Protein", amount=10.0, unit="g", rank=600),
            NutrientRecord(nutrient_id=1004, nutrient_number="204", name="Total lipid (fat)", amount=15.0, unit="g", rank=800),
            NutrientRecord(nutrient_id=1005, nutrient_number="205", name="Carbohydrate, by difference", amount=20.0, unit="g", rank=1110),
        ],
        basis="per_100g",
    )


@pytest.fixture
def sample_ingredient_tree():
    """Return a sample parsed IngredientTree."""
    from nusol.core.schema import IngredientTree, IngredientNode

    return IngredientTree(
        raw_text="ENRICHED FLOUR (WHEAT FLOUR, NIACIN, REDUCED IRON), SUGAR, VEGETABLE OIL",
        root_ingredients=[
            IngredientNode(
                name="ENRICHED FLOUR",
                normalized_name="enriched flour",
                position=0,
                is_compound=True,
                children=[
                    IngredientNode(name="WHEAT FLOUR", normalized_name="wheat flour", position=0, is_sub_ingredient=True),
                    IngredientNode(name="NIACIN", normalized_name="niacin", position=1, is_sub_ingredient=True),
                    IngredientNode(name="REDUCED IRON", normalized_name="iron", position=2, is_sub_ingredient=True),
                ],
            ),
            IngredientNode(name="SUGAR", normalized_name="sugar", position=1),
            IngredientNode(name="VEGETABLE OIL", normalized_name="vegetable oil", position=2),
        ],
    )


@pytest.fixture
def sample_product_observation(sample_ingredient_tree, sample_nutrient_profile):
    """Return a sample ProductObservation."""
    from nusol.core.schema import ProductObservation

    return ProductObservation(
        fdc_id=999999,
        description="Test Product",
        source="FNDDS",
        label_nutrients=sample_nutrient_profile.nutrients,
        serving_size_g=100.0,
        ingredient_tree=sample_ingredient_tree,
        true_ingredient_fractions={
            "enriched flour": 0.60,
            "sugar": 0.25,
            "vegetable oil": 0.15,
        },
        true_nutrient_profile=sample_nutrient_profile,
    )


@pytest.fixture
def sample_trust_report():
    """Return a sample TrustReport."""
    from nusol.core.schema import (
        TrustReport,
        IngredientEstimate,
        IdentifiabilityReport,
    )

    return TrustReport(
        fdc_id=999999,
        description="Test Product",
        ingredient_estimates=[
            IngredientEstimate(
                ingredient_name="enriched flour",
                point_estimate=0.60,
                lower_bound=0.50,
                upper_bound=0.70,
                interval_80=(0.55, 0.65),
                interval_95=(0.50, 0.70),
                mapping_confidence=0.95,
            ),
            IngredientEstimate(
                ingredient_name="sugar",
                point_estimate=0.25,
                lower_bound=0.15,
                upper_bound=0.35,
                interval_80=(0.20, 0.30),
                interval_95=(0.15, 0.35),
                mapping_confidence=0.90,
            ),
        ],
        trust_grade="A",
        trust_score=85.0,
    )


@pytest.fixture
def temp_config_dir():
    """Create a temporary directory with a YAML config file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        config_file = config_dir / "test_config.yaml"
        config_data = {
            "run_id": "test_run",
            "data": {
                "product_observation_source": {"type": "FNDDS", "version": "2021-2023"},
            },
            "forward_model": {"basis": "per_100g"},
            "inverse_solver": {
                "variables": {"ingredient_fractions": True},
                "constraints": {
                    "mass_balance": {"enabled": True, "priority": "P0"},
                    "ingredient_order": {"enabled": True, "priority": "P1"},
                    "label_interval_fit": {"enabled": True, "priority": "P2"},
                },
                "solver": {"point_solver": "scipy_trust_constr"},
            },
            "reporting": {"output_dir": "./output"},
        }
        config_file.write_text(yaml.dump(config_data), encoding="utf-8")
        yield config_dir
