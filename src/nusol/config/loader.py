"""YAML loader and validator for NuSol-T problem documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from nusol.config.errors import ConfigError, SchemaValidationError, ResourceError
from nusol.config.schema import SolveDocument


class ConfigLoader:
    """Load, validate, and resolve NuSol-T YAML problem documents.

    Usage::

        loader = ConfigLoader()
        doc = loader.load_from_path("problem.yaml")   # returns SolveDocument
    """

    def __init__(self, search_paths: list[str | Path] | None = None) -> None:
        self.search_paths = [Path(p) for p in (search_paths or ["config", "."])]

    def load_from_path(self, path: str | Path) -> SolveDocument:
        """Load and validate a YAML problem document from a file path.

        Args:
            path: Absolute or relative path to a YAML file.

        Returns:
            Parsed and validated SolveDocument.

        Raises:
            ResourceError: If the file does not exist.
            SchemaValidationError: If the YAML fails schema validation.
            ConfigError: For other configuration errors.
        """
        config_path = Path(path)
        if not config_path.exists():
            raise ResourceError(f"Config file not found: {config_path}")

        raw = self._load_yaml(config_path)
        return self._validate(raw, str(config_path))

    def load_yaml_str(self, yaml_str: str, source: str = "<string>") -> SolveDocument:
        """Load and validate a YAML document from a string.

        Args:
            yaml_str: YAML content as a string.
            source: Source name for error messages.

        Returns:
            Parsed and validated SolveDocument.
        """
        raw = yaml.safe_load(yaml_str)
        if raw is None:
            raise ConfigError(f"Empty YAML document from {source}")
        return self._validate(raw, source)

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        """Load raw YAML dict from file."""
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if data is None:
            raise ResourceError(f"Empty config file: {path}")
        if not isinstance(data, dict):
            raise ConfigError(
                f"Config file must be a top-level mapping, got {type(data).__name__}: {path}"
            )
        return data

    def _validate(self, raw: dict[str, Any], source: str) -> SolveDocument:
        """Validate raw dict against SolveDocument schema."""
        try:
            return SolveDocument.model_validate(raw)
        except ValidationError as e:
            raise SchemaValidationError(
                f"Schema validation failed for {source}:\n{e}"
            ) from e


def load_yaml_document(path: str | Path) -> SolveDocument:
    """Convenience function to load and validate a YAML problem document."""
    loader = ConfigLoader()
    return loader.load_from_path(path)
