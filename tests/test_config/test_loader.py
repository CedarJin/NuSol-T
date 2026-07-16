"""Tests for YAML configuration loader and schema validation."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nusol.config.errors import ResourceError, SchemaValidationError
from nusol.config.loader import ConfigLoader
from nusol.config.schema import (
    BasisSpec,
    ConstraintSpec,
    IngredientFractionVariableSpec,
    IngredientSpec,
    InlineCompositionSpec,
    ModelSpec,
    NutrientColumnSpec,
    NutrientObservation,
    OutputSpec,
    PointSolverSpec,
    PriorSpec,
    SolveDocument,
    SolverSpec,
    VariableSpec,
)


@pytest.fixture
def minimal_yaml(tmp_path: Path) -> Path:
    """Create a minimal valid YAML problem document."""
    doc = {
        "schema_version": "1.0-draft",
        "problem_id": "test_minimal",
        "basis": {
            "ingredient_mass": "input_fraction",
            "nutrient_amount": "per_100g_finished_product",
        },
        "ingredients": [
            {"id": "flour", "name": "Wheat flour", "declaration_position": 0},
            {"id": "sugar", "name": "Sugar", "declaration_position": 1},
        ],
        "composition": {
            "source": "inline",
            "nutrients": [
                {"id": "energy_kcal", "unit": "kcal"},
                {"id": "protein_g", "unit": "g"},
            ],
            "values": {
                "flour": [364.0, 10.3],
                "sugar": [387.0, 0.0],
            },
        },
        "observations": [
            {"nutrient": "energy_kcal", "unit": "kcal", "interval": [400, 450]},
        ],
        "model": {"type": "linear_mixing"},
        "variables": {
            "ingredient_fractions": {"lower": 0.0, "upper": 1.0},
        },
        "solver": {
            "point": {"backend": "scipy_slsqp"},
        },
        "output": {"path": "output/test.json"},
    }
    path = tmp_path / "problem.yaml"
    path.write_text(yaml.dump(doc, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture
def valid_document() -> SolveDocument:
    """Create a minimal valid SolveDocument programmatically."""
    return SolveDocument(
        schema_version="1.0-draft",
        problem_id="test",
        basis=BasisSpec(),
        ingredients=[
            IngredientSpec(id="a", name="Ing A", declaration_position=0),
            IngredientSpec(id="b", name="Ing B", declaration_position=1),
        ],
        composition=InlineCompositionSpec(
            source="inline",
            nutrients=[NutrientColumnSpec(id="energy_kcal", unit="kcal")],
            values={"a": [100.0], "b": [200.0]},
        ),
        observations=[
            NutrientObservation(nutrient="energy_kcal", unit="kcal", interval=[120, 180]),
        ],
        model=ModelSpec(type="linear_mixing"),
        variables=VariableSpec(ingredient_fractions=IngredientFractionVariableSpec()),
        constraints=[
            ConstraintSpec(id="mass", type="mass_balance"),
        ],
        solver=SolverSpec(point=PointSolverSpec()),
        output=OutputSpec(path="output/test.json"),
    )


class TestConfigLoader:
    """Tests for ConfigLoader."""

    def test_load_valid_yaml(self, minimal_yaml: Path) -> None:
        loader = ConfigLoader()
        doc = loader.load_from_path(str(minimal_yaml))
        assert isinstance(doc, SolveDocument)
        assert doc.problem_id == "test_minimal"
        assert len(doc.ingredients) == 2
        assert len(doc.observations) == 1

    def test_load_yaml_str(self) -> None:
        yaml_str = """schema_version: 1.0-draft
problem_id: str_test
basis:
  ingredient_mass: input_fraction
  nutrient_amount: per_100g_finished_product
ingredients:
  - id: a
    name: A
    declaration_position: 0
composition:
  source: inline
  nutrients:
    - id: energy_kcal
      unit: kcal
  values:
    a: [100.0]
observations:
  - nutrient: energy_kcal
    unit: kcal
    interval: [50, 150]
model:
  type: linear_mixing
variables:
  ingredient_fractions:
    lower: 0.0
    upper: 1.0
solver:
  point:
    backend: scipy_slsqp
output:
  path: output/test.json"""
        loader = ConfigLoader()
        doc = loader.load_yaml_str(yaml_str)
        assert doc.problem_id == "str_test"
        assert len(doc.ingredients) == 1

    def test_load_nonexistent_raises_error(self) -> None:
        loader = ConfigLoader()
        with pytest.raises(ResourceError, match="not found"):
            loader.load_from_path("/nonexistent/path.yaml")

    def test_load_empty_yaml_raises_error(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")
        loader = ConfigLoader()
        with pytest.raises(ResourceError, match="Empty"):
            loader.load_from_path(str(path))

    def test_invalid_yaml_raises_schema_error(self, tmp_path: Path) -> None:
        doc = {
            "schema_version": "1.0-draft",
            "problem_id": "bad",
            # missing required fields
        }
        path = tmp_path / "bad.yaml"
        path.write_text(yaml.dump(doc), encoding="utf-8")
        loader = ConfigLoader()
        with pytest.raises(SchemaValidationError):
            loader.load_from_path(str(path))

    def test_unknown_field_rejected(self, tmp_path: Path) -> None:
        doc = {
            "schema_version": "1.0-draft",
            "problem_id": "extra",
            "basis": {
                "ingredient_mass": "input_fraction",
                "nutrient_amount": "per_100g_finished_product",
            },
            "ingredients": [
                {
                    "id": "a",
                    "name": "A",
                    "declaration_position": 0,
                    "unknown_field": "bad",
                }
            ],
            "composition": {
                "source": "inline",
                "nutrients": [{"id": "e", "unit": "kcal"}],
                "values": {"a": [100.0]},
            },
            "observations": [{"nutrient": "e", "unit": "kcal", "interval": [0, 10]}],
            "model": {"type": "linear_mixing"},
            "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
            "solver": {"point": {"backend": "scipy_slsqp"}},
            "output": {"path": "out.json"},
        }
        path = tmp_path / "extra.yaml"
        path.write_text(yaml.dump(doc), encoding="utf-8")
        loader = ConfigLoader()
        with pytest.raises(SchemaValidationError, match="validation error"):
            loader.load_from_path(str(path))

    def test_duplicate_ingredient_id_rejected(self, tmp_path: Path) -> None:
        doc = {
            "schema_version": "1.0-draft",
            "problem_id": "dup",
            "basis": {
                "ingredient_mass": "input_fraction",
                "nutrient_amount": "per_100g_finished_product",
            },
            "ingredients": [
                {"id": "a", "name": "A1", "declaration_position": 0},
                {"id": "a", "name": "A2", "declaration_position": 1},
            ],
            "composition": {
                "source": "inline",
                "nutrients": [{"id": "e", "unit": "kcal"}],
                "values": {"a": [100.0]},
            },
            "observations": [{"nutrient": "e", "unit": "kcal", "interval": [0, 10]}],
            "model": {"type": "linear_mixing"},
            "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
            "solver": {"point": {"backend": "scipy_slsqp"}},
            "output": {"path": "out.json"},
        }
        path = tmp_path / "dup.yaml"
        path.write_text(yaml.dump(doc), encoding="utf-8")
        loader = ConfigLoader()
        with pytest.raises(SchemaValidationError, match="Duplicate ingredient"):
            loader.load_from_path(str(path))


class TestSolveDocument:
    """Tests for SolveDocument schema validation."""

    def test_minimal_valid_document(self, valid_document: SolveDocument) -> None:
        assert valid_document.problem_id == "test"
        assert len(valid_document.ingredients) == 2

    def test_serialize_roundtrip(self, valid_document: SolveDocument, tmp_path: Path) -> None:
        """Serialize to dict and back, verify lossless."""
        data = valid_document.model_dump(mode="json")
        restored = SolveDocument.model_validate(data)
        assert restored.problem_id == valid_document.problem_id
        assert [i.id for i in restored.ingredients] == [i.id for i in valid_document.ingredients]

    def test_constraint_prior_ids_globally_unique(self) -> None:
        """Constraint and prior IDs must not overlap."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError, match="globally unique"):
            SolveDocument(
                schema_version="1.0-draft",
                problem_id="overlap",
                basis=BasisSpec(),
                ingredients=[IngredientSpec(id="a", name="A", declaration_position=0)],
                composition=InlineCompositionSpec(
                    source="inline",
                    nutrients=[NutrientColumnSpec(id="e", unit="kcal")],
                    values={"a": [100.0]},
                ),
                observations=[NutrientObservation(nutrient="e", unit="kcal", interval=[0, 10])],
                model=ModelSpec(type="linear_mixing"),
                variables=VariableSpec(ingredient_fractions=IngredientFractionVariableSpec()),
                constraints=[ConstraintSpec(id="shared", type="mass_balance")],
                priors=[PriorSpec(id="shared", type="some_prior", weight=0.5,
                                  evidence={"status": "experimental", "source": "test"})],
                solver=SolverSpec(point=PointSolverSpec()),
                output=OutputSpec(path="out.json"),
            )

    def test_prior_evidence_status_supports_calibration_lifecycle(self) -> None:
        """Prior evidence status distinguishes examples from calibrated priors."""
        for status in ["example", "experimental", "calibrated", "validated", "deprecated"]:
            prior = PriorSpec(
                id=f"{status}_prior",
                type="fraction_interval_prior",
                weight=0.5,
                evidence={"status": status, "source": "unit_test"},
            )
            assert prior.evidence.status == status

    def test_observation_exactly_one_mode(self) -> None:
        """Observation must have exactly one of interval/exact/less_than."""
        from pydantic import ValidationError

        # No mode → fail
        with pytest.raises(ValidationError, match="Exactly one"):
            NutrientObservation(nutrient="e", unit="kcal", basis="per_100g_finished_product")

        # Two modes → fail
        with pytest.raises(ValidationError, match="Exactly one"):
            NutrientObservation(nutrient="e", unit="kcal", interval=[0, 10], exact=5.0)
