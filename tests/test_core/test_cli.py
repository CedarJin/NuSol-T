"""Tests for Typer CLI."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner():
    """Return a CliRunner for testing."""
    return CliRunner()


class TestCLI:
    """Tests for the NuSol-T CLI."""

    def test_version(self, runner):
        from nusol.cli import app

        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "NuSol-T" in result.stdout

    def test_validate_config_valid(self, runner, temp_config_dir):
        from nusol.cli import app

        config_path = temp_config_dir / "test_config.yaml"
        result = runner.invoke(app, ["validate-config", str(config_path)])
        assert result.exit_code == 0
        assert "PASSED" in result.stdout

    def test_validate_config_nonexistent(self, runner):
        from nusol.cli import app

        result = runner.invoke(app, ["validate-config", "nonexistent.yaml"])
        # Should fail — FileNotFoundError
        assert result.exit_code != 0

    def test_run_forward_help(self, runner):
        from nusol.cli import app

        result = runner.invoke(app, ["run-forward", "--help"])
        assert result.exit_code == 0
        assert "config" in result.stdout

    def test_run_inverse_help(self, runner):
        from nusol.cli import app

        result = runner.invoke(app, ["run-inverse", "--help"])
        assert result.exit_code == 0

    def test_app_help(self, runner):
        from nusol.cli import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "NuSol-T" in result.stdout
