"""Tests for YAML config resolver — extends, defaults, canonical output."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nusol.config.errors import InheritanceError, SchemaValidationError
from nusol.config.resolver import ConfigResolver


@pytest.fixture
def extends_dir(tmp_path: Path) -> Path:
    """Create a set of YAML files with extends."""
    base = tmp_path / "extends"
    base.mkdir()

    # Parent template
    parent = {
        "schema_version": "1.0-draft",
        "problem_id": "parent",
        "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
        "ingredients": [
            {"id": "flour", "name": "Wheat flour", "declaration_position": 0},
        ],
        "composition": {"source": "inline", "nutrients": [{"id": "e", "unit": "kcal"}], "values": {"flour": [364.0]}},
        "observations": [{"nutrient": "e", "unit": "kcal", "interval": [400, 450]}],
        "model": {"type": "linear_mixing"},
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "constraints": [
            {"id": "total_mass", "type": "mass_balance", "mode": "hard"},
        ],
        "solver": {"point": {"backend": "scipy_slsqp"}},
        "output": {"path": "output/test.json"},
    }
    (base / "parent.yaml").write_text(yaml.dump(parent, sort_keys=False))

    # Child that extends parent
    child = {
        "schema_version": "1.0-draft",
        "problem_id": "child_bread",
        "extends": ["parent.yaml"],
        "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
        "ingredients": [
            {"id": "sugar", "name": "Sugar", "declaration_position": 1},
        ],
        "composition": {"source": "inline", "nutrients": [{"id": "e", "unit": "kcal"}], "values": {
            "flour": [364.0], "sugar": [387.0],
        }},
        "observations": [{"nutrient": "e", "unit": "kcal", "interval": [400, 450]}],
        "model": {"type": "linear_mixing"},
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "solver": {"point": {"backend": "scipy_slsqp"}},
        "output": {"path": "output/test.json"},
    }
    (base / "child.yaml").write_text(yaml.dump(child, sort_keys=False))

    # Multi-inheritance child
    parent2 = {
        "schema_version": "1.0-draft",
        "problem_id": "parent2",
        "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
        "ingredients": [
            {"id": "oil", "name": "Vegetable oil", "declaration_position": 2},
        ],
        "composition": {"source": "inline", "nutrients": [{"id": "e", "unit": "kcal"}], "values": {"oil": [884.0]}},
        "observations": [{"nutrient": "e", "unit": "kcal", "interval": [400, 450]}],
        "model": {"type": "linear_mixing"},
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "solver": {"point": {"backend": "scipy_slsqp"}},
        "output": {"path": "output/test.json"},
    }
    (base / "parent2.yaml").write_text(yaml.dump(parent2, sort_keys=False))

    multi_child = {
        "schema_version": "1.0-draft",
        "problem_id": "multi_child",
        "extends": ["parent.yaml", "parent2.yaml"],
        "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
        "ingredients": [
            {"id": "sugar", "name": "Sugar", "declaration_position": 1},
        ],
        "composition": {"source": "inline", "nutrients": [{"id": "e", "unit": "kcal"}], "values": {
            "flour": [364.0], "sugar": [387.0], "oil": [884.0],
        }},
        "observations": [{"nutrient": "e", "unit": "kcal", "interval": [400, 450]}],
        "model": {"type": "linear_mixing"},
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "solver": {"point": {"backend": "scipy_slsqp"}},
        "output": {"path": "output/test.json"},
    }
    (base / "multi_child.yaml").write_text(yaml.dump(multi_child, sort_keys=False))

    return base


class TestConfigResolver:
    """Tests for ConfigResolver."""

    def test_no_extends_passthrough(self, extends_dir: Path) -> None:
        """A file without extends is resolved without change."""
        resolver = ConfigResolver()
        doc = resolver.resolve(str(extends_dir / "parent.yaml"))
        assert doc.problem_id == "parent"
        assert len(doc.ingredients) == 1

    def test_single_extends_inherits_parent(self, extends_dir: Path) -> None:
        """Child inherits parent ingredients plus its own."""
        resolver = ConfigResolver()
        doc = resolver.resolve(str(extends_dir / "child.yaml"))
        assert doc.problem_id == "child_bread"
        ing_ids = [i.id for i in doc.ingredients]
        assert "flour" in ing_ids  # From parent
        assert "sugar" in ing_ids  # From child
        assert len(doc.ingredients) >= 2

    def test_multi_extends_merges_all_parents(self, extends_dir: Path) -> None:
        """Multi-inheritance: ingredients from both parents plus child."""
        resolver = ConfigResolver()
        doc = resolver.resolve(str(extends_dir / "multi_child.yaml"))
        ing_ids = [i.id for i in doc.ingredients]
        assert "flour" in ing_ids   # From parent
        assert "oil" in ing_ids     # From parent2
        assert "sugar" in ing_ids   # From child

    def test_single_extends_child_overrides_parent(self, extends_dir: Path) -> None:
        """Child overrides parent on conflicting fields."""
        resolver = ConfigResolver()
        doc = resolver.resolve(str(extends_dir / "child.yaml"))
        assert doc.problem_id == "child_bread"  # child overrides parent

    def test_extends_produces_canonical_yaml(self, extends_dir: Path) -> None:
        """Resolved YAML should be stable and not contain extends."""
        resolver = ConfigResolver()
        resolved_dict = resolver.resolve_to_dict(str(extends_dir / "child.yaml"))
        assert "extends" not in resolved_dict, "Resolved output should not contain extends key"

    def test_resolve_to_dict_no_extends(self, extends_dir: Path) -> None:
        """resolve_to_dict output matches expected structure."""
        resolver = ConfigResolver()
        resolved_dict = resolver.resolve_to_dict(str(extends_dir / "child.yaml"))
        assert "schema_version" in resolved_dict
        assert "ingredients" in resolved_dict
        assert isinstance(resolved_dict["ingredients"], list)

    def test_resolve_applies_defaults(self, extends_dir: Path) -> None:
        """Defaults are applied during resolution."""
        resolver = ConfigResolver()
        doc = resolver.resolve(str(extends_dir / "parent.yaml"))
        # basis defaults should be set
        assert doc.basis.ingredient_mass.value == "input_fraction"


class TestResolverErrors:
    """Tests for resolver error handling."""

    def test_circular_extends_raises_error(self, tmp_path: Path) -> None:
        """Circular extends should be detected."""
        a = {
            "schema_version": "1.0-draft",
            "problem_id": "a",
            "extends": ["b.yaml"],
            "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
            "ingredients": [{"id": "a", "name": "A", "declaration_position": 0}],
            "composition": {"source": "inline", "nutrients": [{"id": "e", "unit": "kcal"}], "values": {"a": [100.0]}},
            "observations": [{"nutrient": "e", "unit": "kcal", "interval": [0, 10]}],
            "model": {"type": "linear_mixing"},
            "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
            "solver": {"point": {"backend": "scipy_slsqp"}},
            "output": {"path": "out.json"},
        }
        b = {
            "schema_version": "1.0-draft",
            "problem_id": "b",
            "extends": ["a.yaml"],
            "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
            "ingredients": [{"id": "b", "name": "B", "declaration_position": 0}],
            "composition": {"source": "inline", "nutrients": [{"id": "e", "unit": "kcal"}], "values": {"b": [200.0]}},
            "observations": [{"nutrient": "e", "unit": "kcal", "interval": [0, 10]}],
            "model": {"type": "linear_mixing"},
            "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
            "solver": {"point": {"backend": "scipy_slsqp"}},
            "output": {"path": "out.json"},
        }

        (tmp_path / "a.yaml").write_text(yaml.dump(a, sort_keys=False))
        (tmp_path / "b.yaml").write_text(yaml.dump(b, sort_keys=False))

        resolver = ConfigResolver()
        with pytest.raises(InheritanceError, match="circular|Circular"):
            resolver.resolve(str(tmp_path / "a.yaml"))

    def test_missing_parent_raises_error(self, tmp_path: Path) -> None:
        """Missing parent config should raise an error."""
        child = {
            "schema_version": "1.0-draft",
            "problem_id": "orphan",
            "extends": ["nonexistent_parent.yaml"],
            "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
            "ingredients": [{"id": "a", "name": "A", "declaration_position": 0}],
            "composition": {"source": "inline", "nutrients": [{"id": "e", "unit": "kcal"}], "values": {"a": [100.0]}},
            "observations": [{"nutrient": "e", "unit": "kcal", "interval": [0, 10]}],
            "model": {"type": "linear_mixing"},
            "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
            "solver": {"point": {"backend": "scipy_slsqp"}},
            "output": {"path": "out.json"},
        }

        (tmp_path / "orphan.yaml").write_text(yaml.dump(child, sort_keys=False))

        resolver = ConfigResolver()
        with pytest.raises(InheritanceError, match="not found"):
            resolver.resolve(str(tmp_path / "orphan.yaml"))


class TestResolverDefaults:
    """Tests for default value application during resolution."""

    def test_basis_defaults_applied(self, tmp_path: Path) -> None:
        """Basis defaults should be applied when missing."""
        minimal = {
            "schema_version": "1.0-draft",
            "problem_id": "no_basis",
            "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
            "ingredients": [{"id": "a", "name": "A", "declaration_position": 0}],
            "composition": {"source": "inline", "nutrients": [{"id": "e", "unit": "kcal"}], "values": {"a": [100.0]}},
            "observations": [{"nutrient": "e", "unit": "kcal", "interval": [0, 10]}],
            "model": {"type": "linear_mixing"},
            "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
            "solver": {"point": {"backend": "scipy_slsqp"}},
            "output": {"path": "out.json"},
        }

        (tmp_path / "no_basis.yaml").write_text(yaml.dump(minimal, sort_keys=False))
        resolver = ConfigResolver()
        doc = resolver.resolve(str(tmp_path / "no_basis.yaml"))
        assert doc.basis.ingredient_mass.value == "input_fraction"
        assert doc.basis.nutrient_amount.value == "per_100g_finished_product"

    def test_variable_defaults_applied(self, tmp_path: Path) -> None:
        """Variable fraction defaults applied."""
        minimal = {
            "schema_version": "1.0-draft",
            "problem_id": "test_defaults",
            "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
            "ingredients": [{"id": "a", "name": "A", "declaration_position": 0}],
            "composition": {"source": "inline", "nutrients": [{"id": "e", "unit": "kcal"}], "values": {"a": [100.0]}},
            "observations": [{"nutrient": "e", "unit": "kcal", "interval": [0, 10]}],
            "model": {"type": "linear_mixing"},
            "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
            "solver": {"point": {"backend": "scipy_slsqp"}},
            "output": {"path": "out.json"},
        }

        (tmp_path / "defaults.yaml").write_text(yaml.dump(minimal, sort_keys=False))
        resolver = ConfigResolver()
        doc = resolver.resolve(str(tmp_path / "defaults.yaml"))
        assert doc.variables.ingredient_fractions.lower == 0.0
        assert doc.variables.ingredient_fractions.upper == 1.0
