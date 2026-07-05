"""Tests for Typer CLI."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def minimal_yaml(tmp_path: Path) -> Path:
    """Create a minimal valid YAML problem document."""
    doc = {
        "schema_version": "1.0-draft",
        "problem_id": "test_cli_minimal",
        "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
        "ingredients": [
            {"id": "flour", "name": "Wheat flour", "declaration_position": 0},
            {"id": "sugar", "name": "Sugar", "declaration_position": 1},
        ],
        "composition": {
            "source": "inline",
            "nutrients": [{"id": "energy_kcal", "unit": "kcal"}],
            "values": {"flour": [364.0], "sugar": [387.0]},
        },
        "observations": [{"nutrient": "energy_kcal", "unit": "kcal", "interval": [400, 450]}],
        "model": {"type": "linear_mixing"},
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "solver": {"point": {"backend": "scipy_slsqp"}},
        "output": {"path": "output/test.json"},
    }
    path = tmp_path / "problem.yaml"
    path.write_text(yaml.dump(doc, sort_keys=False), encoding="utf-8")
    return path


@pytest.fixture
def invalid_yaml(tmp_path: Path) -> Path:
    """Create an invalid YAML file (unknown field)."""
    doc = {
        "schema_version": "1.0-draft",
        "problem_id": "bad",
        "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
        "ingredients": [{"id": "a", "name": "A", "declaration_position": 0, "unknown": "bad"}],
        "composition": {"source": "inline", "nutrients": [{"id": "e", "unit": "kcal"}], "values": {"a": [100.0]}},
        "observations": [{"nutrient": "e", "unit": "kcal", "interval": [0, 10]}],
        "model": {"type": "linear_mixing"},
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "solver": {"point": {"backend": "scipy_slsqp"}},
        "output": {"path": "out.json"},
    }
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.dump(doc), encoding="utf-8")
    return path


class TestCLI:
    """Tests for the NuSol-T CLI."""

    def test_version(self, runner: CliRunner) -> None:
        from nusol.cli import app

        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "NuSol-T" in result.stdout

    def test_validate_valid(self, runner: CliRunner, minimal_yaml: Path) -> None:
        from nusol.cli import app

        result = runner.invoke(app, ["validate", str(minimal_yaml)])
        assert result.exit_code == 0, result.output
        assert "PASSED" in result.stdout

    def test_validate_invalid(self, runner: CliRunner, invalid_yaml: Path) -> None:
        from nusol.cli import app

        result = runner.invoke(app, ["validate", str(invalid_yaml)])
        assert result.exit_code == 1, f"Expected exit code 1, got {result.return_code}"
        assert "FAILED" in result.stdout or "error" in result.stdout.lower()

    def test_validate_nonexistent(self, runner: CliRunner) -> None:
        from nusol.cli import app

        result = runner.invoke(app, ["validate", "nonexistent.yaml"])
        assert result.exit_code == 1

    def test_resolve(self, runner: CliRunner, minimal_yaml: Path) -> None:
        from nusol.cli import app

        result = runner.invoke(app, ["resolve", str(minimal_yaml)])
        assert result.exit_code == 0, result.output
        # Resolved output should not contain 'extends'
        assert "extends" not in result.stdout

    def test_resolve_invalid(self, runner: CliRunner, invalid_yaml: Path) -> None:
        from nusol.cli import app

        result = runner.invoke(app, ["resolve", str(invalid_yaml)])
        assert result.exit_code == 1

    def test_inspect(self, runner: CliRunner, minimal_yaml: Path) -> None:
        from nusol.cli import app

        result = runner.invoke(app, ["inspect", str(minimal_yaml)])
        assert result.exit_code == 0, result.output
        assert "test_cli_minimal" in result.stdout
        assert "flour" in result.stdout
        assert "energy_kcal" in result.stdout
        assert "scipy_slsqp" in result.stdout

    def test_solve_e2e(self, runner: CliRunner, minimal_yaml: Path) -> None:
        from nusol.cli import app

        result = runner.invoke(app, ["solve", str(minimal_yaml)])
        assert result.exit_code == 0, result.output
        assert "SUCCESS" in result.stdout
        assert "fractions" in result.stdout
        assert "solve_time" in result.stdout

    def test_solve_dry_run(self, runner: CliRunner, minimal_yaml: Path) -> None:
        from nusol.cli import app

        result = runner.invoke(app, ["solve", str(minimal_yaml), "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "DRY-RUN" in result.stdout

    def test_solve_with_output(self, runner: CliRunner, minimal_yaml: Path, tmp_path) -> None:
        from nusol.cli import app

        out_path = tmp_path / "result.json"
        result = runner.invoke(app, ["solve", str(minimal_yaml), "--output", str(out_path)])
        assert result.exit_code == 0, result.output
        assert out_path.exists()
        assert "fractions" in out_path.read_text()

    def test_app_help(self, runner: CliRunner) -> None:
        from nusol.cli import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "NuSol-T" in result.stdout
        assert "validate" in result.stdout
        assert "resolve" in result.stdout
        assert "inspect" in result.stdout
        assert "solve" in result.stdout
