"""Tests for YAML configuration loader."""

from __future__ import annotations

import pytest


class TestConfigLoader:
    """Tests for ConfigLoader."""

    def test_load_valid_config(self, temp_config_dir):
        from nusol.config.loader import ConfigLoader

        loader = ConfigLoader(temp_config_dir)
        data = loader.load("test_config.yaml")
        assert data["run_id"] == "test_run"
        assert "data" in data

    def test_applies_defaults(self, temp_config_dir):
        from nusol.config.loader import ConfigLoader

        loader = ConfigLoader(temp_config_dir)
        data = loader.load("test_config.yaml")

        # Should have defaults applied
        fm = data["forward_model"]
        assert fm["retention"]["enabled"] is False
        assert fm["moisture"]["enabled"] is False

        inv = data["inverse_solver"]
        assert inv["solver"]["multi_start"] == 50
        assert inv["solver"]["tolerance"] == 1e-8

        rep = data["reporting"]
        assert "json" in rep["formats"]

    def test_load_nonexistent_config_raises_error(self, temp_config_dir):
        from nusol.config.loader import ConfigLoader

        loader = ConfigLoader(temp_config_dir)
        with pytest.raises(FileNotFoundError):
            loader.load("nonexistent.yaml")

    def test_validate_valid_config(self, temp_config_dir):
        from nusol.config.loader import ConfigLoader

        loader = ConfigLoader(temp_config_dir)
        data = loader.load("test_config.yaml")
        errors = loader.validate(data)
        assert len(errors) == 0

    def test_validate_missing_inverse_solver(self, temp_config_dir):
        from nusol.config.loader import ConfigLoader

        loader = ConfigLoader(temp_config_dir)
        data = {
            "run_id": "test",
            "data": {"source": "FNDDS"},
            "forward_model": {},
        }
        errors = loader.validate(data)
        assert any("inverse_solver" in e.lower() for e in errors)

    def test_load_from_path(self, temp_config_dir):
        from nusol.config.loader import ConfigLoader

        config_path = temp_config_dir / "test_config.yaml"
        loader = ConfigLoader()
        data = loader.load_from_path(str(config_path))
        assert data["run_id"] == "test_run"


class TestLoadConfig:
    """Tests for the load_config convenience function."""

    def test_load_from_path(self, temp_config_dir):
        from nusol.config.loader import load_config

        config_path = temp_config_dir / "test_config.yaml"
        data = load_config(str(config_path))
        assert data["run_id"] == "test_run"


class TestConfigDefaults:
    """Tests for default value application."""

    def test_minimal_config_gets_defaults(self):
        from nusol.config.loader import ConfigLoader

        loader = ConfigLoader()
        data = loader._apply_defaults({})
        assert data["run_id"] == "unnamed_run"
        assert "forward_model" in data
        assert "inverse_solver" in data
        assert "reporting" in data

    def test_user_values_override_defaults(self):
        from nusol.config.loader import ConfigLoader

        loader = ConfigLoader()
        data = loader._apply_defaults({
            "run_id": "custom",
            "forward_model": {"basis": "per_serving"},
        })
        assert data["run_id"] == "custom"
        assert data["forward_model"]["basis"] == "per_serving"
        # Defaults should still fill missing keys
        assert data["forward_model"]["retention"]["enabled"] is False
