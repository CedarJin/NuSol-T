"""Tests for the public solve API."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml


@pytest.fixture
def bread_yaml(tmp_path: Path) -> Path:
    doc = {
        "schema_version": "1.0-draft",
        "problem_id": "test_api",
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
            {"nutrient": "energy_kcal", "unit": "kcal", "interval": [370, 380]},
            {"nutrient": "protein_g", "unit": "g", "interval": [4.5, 6.0]},
        ],
        "model": {"type": "linear_mixing"},
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "constraints": [
            {"id": "mass_balance", "type": "mass_balance", "mode": "hard"},
            {"id": "label_fit", "type": "nutrient_interval", "mode": "soft", "weight": 10.0},
        ],
        "solver": {
            "point": {"backend": "scipy_slsqp"},
            "bounds": {"backend": "highs_lp"},
        },
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
        assert result["bounds"]["type"] == "hard_feasible_bounds"
        for ing in ["flour", "sugar"]:
            assert ing in result["bounds"]["values"]
            lo, hi = result["bounds"]["values"][ing]
            assert lo <= hi

    def test_solve_predictions_within_intervals(self, bread_yaml: Path) -> None:
        import nusol

        result = nusol.solve(str(bread_yaml))
        x = result["fractions"]

        # Compute predictions
        energy = 364.0 * x.get("flour", 0) + 387.0 * x.get("sugar", 0)
        assert 370 <= energy <= 380, f"Energy {energy} outside [370, 380]"
        energy_diag = next(
            item for item in result["observation_diagnostics"]
            if item["nutrient"] == "energy_kcal"
        )
        assert energy_diag["predicted"] == pytest.approx(energy, abs=1e-6)
        assert energy_diag["lower"] == 370
        assert energy_diag["upper"] == 380

    def test_solve_returns_manifest(self, bread_yaml: Path) -> None:
        import nusol

        result = nusol.solve(str(bread_yaml))
        assert "manifest" in result
        assert result["manifest"]["problem_id"] == "test_api"
        assert "resolved_config" in result["manifest"]

    def test_point_only_does_not_run_bounds(self, bread_yaml: Path) -> None:
        import nusol

        doc = yaml.safe_load(bread_yaml.read_text())
        doc["solver"] = {"point": {"backend": "scipy_slsqp"}}
        bread_yaml.write_text(yaml.safe_dump(doc, sort_keys=False))

        result = nusol.solve(bread_yaml)

        assert result["success"] is True
        assert result["bounds"] == {}
        assert result["diagnostics"]["bounds"]["success"] is False

    def test_bounds_only_is_successful_and_honors_variable_bounds(
        self, bread_yaml: Path,
    ) -> None:
        import nusol

        doc = yaml.safe_load(bread_yaml.read_text())
        doc["solver"] = {"bounds": {"backend": "highs_lp"}}
        doc["variables"]["ingredient_fractions"] = {"lower": 0.3, "upper": 0.7}
        bread_yaml.write_text(yaml.safe_dump(doc, sort_keys=False))

        result = nusol.solve(bread_yaml)

        assert result["success"] is True
        assert result["fractions"] == {}
        assert result["bounds"]["values"]["flour"] == pytest.approx([0.3, 0.7])
        assert result["bounds"]["values"]["sugar"] == pytest.approx([0.3, 0.7])

    def test_explicit_slack_budget_limits_bounds(self, bread_yaml: Path) -> None:
        import nusol

        doc = yaml.safe_load(bread_yaml.read_text())
        doc["observations"] = [
            {"nutrient": "energy_kcal", "unit": "kcal", "exact": 375.0},
        ]
        doc["solver"] = {
            "bounds": {
                "backend": "highs_lp",
                "feasible_region": "explicit_slack_budget",
                "slack_budgets": {"label_fit": 0.0},
            },
        }
        bread_yaml.write_text(yaml.safe_dump(doc, sort_keys=False))

        result = nusol.solve(bread_yaml)

        expected_flour = (387.0 - 375.0) / (387.0 - 364.0)
        assert result["success"] is True
        assert result["bounds"]["type"] == "slack_budget_bounds"
        assert result["bounds"]["values"]["flour"] == pytest.approx(
            [expected_flour, expected_flour], abs=1e-7,
        )
        assert result["manifest"]["solver"]["bounds_feasible_region"] == \
            "explicit_slack_budget"

    def test_relative_csv_is_verified_aligned_and_recorded(
        self, bread_yaml: Path,
    ) -> None:
        import nusol

        csv_path = bread_yaml.parent / "composition.csv"
        csv_path.write_text(
            "ingredient_id,energy_kcal,protein_g\n"
            "sugar,387,0\n"
            "flour,364,10.3\n",
        )
        checksum = hashlib.sha256(csv_path.read_bytes()).hexdigest()
        doc = yaml.safe_load(bread_yaml.read_text())
        nutrients = doc["composition"]["nutrients"]
        doc["composition"] = {
            "source": "csv",
            "path": "composition.csv",
            "sha256": checksum,
            "nutrients": nutrients,
        }
        bread_yaml.write_text(yaml.safe_dump(doc, sort_keys=False))

        result = nusol.solve(bread_yaml)

        assert result["success"] is True
        resource = result["manifest"]["resources"][0]
        assert resource["path"] == str(csv_path.resolve())
        assert resource["sha256"] == checksum

    def test_solve_nonexistent_raises(self) -> None:
        import nusol

        with pytest.raises(Exception):
            nusol.solve("nonexistent.yaml")
