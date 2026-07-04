"""YAML configuration loader with schema validation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class ConfigLoader:
    """Load and validate YAML configuration files for NuSol-T pipelines."""

    def __init__(self, config_dir: str | Path = "config") -> None:
        self.config_dir = Path(config_dir)

    def load(self, config_name: str) -> dict[str, Any]:
        """Load a YAML config file by name.

        Args:
            config_name: Config file name (e.g. 'fndds_forward.yaml') or
                         path relative to config_dir.

        Returns:
            Parsed configuration dict.

        Raises:
            FileNotFoundError: If the config file doesn't exist.
            yaml.YAMLError: If the YAML is malformed.
        """
        config_path = self.config_dir / config_name
        if not config_path.suffix:
            config_path = config_path.with_suffix(".yaml")
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ValueError(f"Config file is empty: {config_path}")

        return self._apply_defaults(data)

    def load_from_path(self, path: str | Path) -> dict[str, Any]:
        """Load a YAML config from an absolute path."""
        config_path = Path(path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            raise ValueError(f"Config file is empty: {config_path}")

        return self._apply_defaults(data)

    @staticmethod
    def _apply_defaults(data: dict) -> dict:
        """Apply sensible defaults to the loaded config."""
        # Ensure required top-level keys exist
        data.setdefault("run_id", "unnamed_run")

        # Forward model defaults
        fm = data.setdefault("forward_model", {})
        fm.setdefault("basis", "per_100g")
        fm.setdefault("edible_weight_adjustment", True)

        retention = fm.setdefault("retention", {})
        retention.setdefault("enabled", False)
        retention.setdefault("mode", "none")

        moisture = fm.setdefault("moisture", {})
        moisture.setdefault("enabled", False)
        moisture.setdefault("estimate", False)
        moisture.setdefault("default_bounds", [-0.30, 0.30])

        fm.setdefault("normalization", "finished_weight")

        # Inverse solver defaults
        inv = data.setdefault("inverse_solver", {})
        variables = inv.setdefault("variables", {})
        variables.setdefault("ingredient_fractions", True)
        variables.setdefault("moisture_change", False)

        solver = inv.setdefault("solver", {})
        solver.setdefault("point_solver", "scipy_trust_constr")
        solver.setdefault("multi_start", 50)
        solver.setdefault("max_iter", 1000)
        solver.setdefault("tolerance", 1e-8)

        bound = solver.setdefault("bound_solver", {})
        bound.setdefault("enabled", True)

        ensemble = solver.setdefault("ensemble", {})
        ensemble.setdefault("enabled", False)
        ensemble.setdefault("n_bootstrap", 100)
        ensemble.setdefault("n_multi_start", 50)

        # Reporting defaults
        rep = data.setdefault("reporting", {})
        rep.setdefault("output_dir", "./output")
        rep.setdefault("formats", ["json"])
        rep.setdefault("include_provenance", True)
        rep.setdefault("include_uncertainty", True)
        rep.setdefault("include_warnings", True)
        rep.setdefault("include_trust_grade", True)

        return data

    def validate(self, data: dict) -> list[str]:
        """Validate a loaded config dict. Returns list of error messages."""
        errors = []

        if "data" not in data:
            errors.append("Missing 'data' section in config")

        if "forward_model" not in data:
            errors.append("Missing 'forward_model' section in config")

        inv = data.get("inverse_solver", {})
        if "constraints" not in inv:
            errors.append("Missing 'constraints' section under 'inverse_solver'")

        return errors


def load_config(config_path: str | Path = "config") -> dict[str, Any]:
    """Convenience function to load a config.

    Args:
        config_path: Path to YAML config file.

    Returns:
        Config dict with defaults applied.
    """
    config_path = Path(config_path)

    if config_path.is_file():
        loader = ConfigLoader(config_path.parent)
        return loader.load_from_path(config_path)

    # Treat as config name under config/ directory
    loader = ConfigLoader()
    return loader.load(str(config_path))
