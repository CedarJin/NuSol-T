"""Tests for the public solve API."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def bread_yaml(tmp_path: Path) -> Path:
    doc = {
        "schema_version": "1.0-draft",
        "problem_id": "test_api",
        "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
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
            {"nutrient": "energy_kcal", "unit": "kcal", "interval": [370, 380]},
            {"nutrient": "protein_g", "unit": "g", "interval": [4.5, 6.0]},
        ],
        "model": {"type": "linear_mixing"},
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "constraints": [
            {"id": "mass_balance", "type": "mass_balance", "mode": "hard"},
            {"id": "label_fit", "type": "nutrient_interval", "mode": "soft", "weight": 10.0},
        ],
        "solver": {"point": {"backend": "scipy_slsqp"}},
        "output": {"path": "output/test.json"},
    }
    path = tmp_path / "api_test.yaml"
    path.write_text(yaml.dump(doc, sort_keys=False))
    return path


class TestSolveAPI:
    """Tests for nusol.solve()."""

    def test_solve_returns_fractions(self, bread_yaml: Path) -> None:
        import nusol

        result = nusol.solve(str(bread_yaml))
        assert result["success"] is True
        assert "flour" in result["fractions"]
        assert "sugar" in result["fractions"]
        assert abs(sum(result["fractions"].values()) - 1.0) < 1e-3

    def test_solve_returns_bounds(self, bread_yaml: Path) -> None:
        import nusol

        result = nusol.solve(str(bread_yaml))
        for ing in ["flour", "sugar"]:
            assert ing in result["bounds"]
            lo, hi = result["bounds"][ing]
            assert lo <= hi

    def test_solve_predictions_within_intervals(self, bread_yaml: Path) -> None:
        import nusol

        result = nusol.solve(str(bread_yaml))
        x = result["fractions"]

        # Compute predictions
        energy = 364.0 * x.get("flour", 0) + 387.0 * x.get("sugar", 0)
        assert 370 <= energy <= 380, f"Energy {energy} outside [370, 380]"

    def test_solve_returns_manifest(self, bread_yaml: Path) -> None:
        import nusol

        result = nusol.solve(str(bread_yaml))
        assert "manifest" in result
        assert result["manifest"]["problem_id"] == "test_api"
        assert "resolved_config" in result["manifest"]

    def test_solve_nonexistent_raises(self) -> None:
        import nusol

        with pytest.raises(Exception):
            nusol.solve("nonexistent.yaml")
