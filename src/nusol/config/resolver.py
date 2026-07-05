"""YAML configuration resolver — extends, defaults, and canonical output.

Resolves a ``SolveDocument`` with extends into a complete, self-contained config.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

from nusol.config.errors import ConfigError, InheritanceError
from nusol.config.loader import ConfigLoader
from nusol.config.schema import SolveDocument

# Default field overrides applied during resolution (not schema defaults).
# These are merged into the raw dict BEFORE schema validation.
_DEFAULTS: dict[str, Any] = {
    "basis": {
        "ingredient_mass": "input_fraction",
        "nutrient_amount": "per_100g_finished_product",
    },
    "variables": {
        "ingredient_fractions": {
            "lower": 0.0,
            "upper": 1.0,
        },
    },
}


class ConfigResolver:
    """Resolve YAML configs with inheritance and defaults.

    Steps:
        1. Extends chain: recursively load parents and merge (child overrides parent).
        2. Apply hard-coded defaults for optional top-level sections.
        3. Canonicalize (sort keys for stable output).
    """

    def __init__(self, search_paths: list[str | Path] | None = None) -> None:
        self._loader = ConfigLoader(search_paths=search_paths)

    def resolve(self, path: str | Path) -> SolveDocument:
        """Load a YAML file and resolve its extends chain.

        Args:
            path: Path to the primary YAML file.

        Returns:
            A fully resolved SolveDocument with all defaults applied.

        Raises:
            InheritanceError: On cycle or missing parent.
            ConfigError: On other configuration errors.
        """
        resolved_raw = self._resolve_chain(path, visited=set())
        resolved_raw = self._apply_defaults(resolved_raw)
        resolved_raw = self._canonicalize(resolved_raw)
        return self._loader._validate(resolved_raw, str(path))

    def resolve_to_dict(self, path: str | Path) -> dict[str, Any]:
        """Resolve and return the resolved raw dict (for YAML output).

        Raises SchemaValidationError if the resolved document is invalid.
        """
        resolved_raw = self._resolve_chain(path, visited=set())
        resolved_raw = self._apply_defaults(resolved_raw)
        resolved_raw = self._canonicalize(resolved_raw)
        # Validate against SolveDocument schema to catch errors early
        self._loader._validate(resolved_raw, str(path))
        return resolved_raw

    def _resolve_chain(
        self, path: str | Path, visited: set[str]
    ) -> dict[str, Any]:
        """Recursively resolve extends chain."""
        abs_path = str(Path(path).resolve())
        if abs_path in visited:
            raise InheritanceError(
                f"Circular extends detected: {abs_path} already in chain"
            )
        visited.add(abs_path)

        raw = self._loader._load_yaml(Path(path))

        # Collect extends before merging (parents override nothing, child overrides them)
        extends_list: list[str] = raw.pop("extends", [])

        if extends_list:
            # Load and merge parents sequentially
            parent_dir = Path(path).resolve().parent
            for parent_ref in extends_list:
                parent_path = parent_dir / parent_ref
                if not parent_path.exists():
                    # Try resolving relative to search paths
                    for sp in self._loader.search_paths:
                        candidate = sp / parent_ref
                        if candidate.exists():
                            parent_path = candidate
                            break
                    else:
                        raise InheritanceError(
                            f"Parent config not found: {parent_ref} "
                            f"(searched {parent_dir} and {self._loader.search_paths})"
                        )
                parent_raw = self._resolve_chain(str(parent_path), visited)
                raw = self._deep_merge(parent_raw, raw)

        return raw

    def _deep_merge(self, base: dict, override: dict) -> dict:
        """Deep merge ``override`` into ``base``.

        - Dicts are merged recursively.
        - Lists are replaced (not merged), unless both are list-of-dicts with
          matching ``id`` keys.
        - Scalar values from ``override`` win.
        """
        result = copy.deepcopy(base)

        for key, value in override.items():
            if key not in result:
                result[key] = copy.deepcopy(value)
            elif isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            elif isinstance(result[key], list) and isinstance(value, list):
                # Try ID-based merge for lists of dicts with 'id' fields
                if value and isinstance(value[0], dict) and "id" in value[0]:
                    result[key] = self._merge_id_list(result[key], value)
                else:
                    result[key] = copy.deepcopy(value)
            else:
                result[key] = copy.deepcopy(value)

        return result

    def _merge_id_list(
        self, base: list[dict], override: list[dict]
    ) -> list[dict]:
        """Merge list-of-dicts by ``id`` field.

        Items in ``override`` with new ids are appended.
        Items with existing ids override the base item (deep merge).
        """
        base_by_id: dict[str, dict] = {}
        for item in base:
            if "id" in item:
                base_by_id[item["id"]] = item

        for item in override:
            item_id = item.get("id")
            if item_id in base_by_id:
                base_by_id[item_id] = self._deep_merge(
                    base_by_id[item_id], item
                )
            else:
                base_by_id[item_id] = copy.deepcopy(item)

        return list(base_by_id.values())

    def _apply_defaults(self, raw: dict) -> dict:
        """Apply hard-coded defaults for optional top-level sections."""
        for key, default_val in _DEFAULTS.items():
            if key not in raw:
                raw[key] = copy.deepcopy(default_val)
            elif isinstance(default_val, dict) and isinstance(raw[key], dict):
                for sub_key, sub_val in default_val.items():
                    if sub_key not in raw[key]:
                        raw[key][sub_key] = copy.deepcopy(sub_val)
        return raw

    def _canonicalize(self, raw: dict) -> dict:
        """Sort keys for stable, deterministic output."""
        if not isinstance(raw, dict):
            return raw
        return {k: self._canonicalize(v) if isinstance(v, dict) else v
                for k, v in sorted(raw.items())}


def resolve_yaml(path: str | Path) -> SolveDocument:
    """Convenience: load and resolve a YAML problem document with extends."""
    resolver = ConfigResolver()
    return resolver.resolve(path)


def resolve_yaml_to_dict(path: str | Path) -> dict[str, Any]:
    """Convenience: load, resolve, and return as a canonical dict for YAML output."""
    resolver = ConfigResolver()
    return resolver.resolve_to_dict(path)


def yaml_to_canonical_string(doc: dict[str, Any]) -> str:
    """Convert a resolved config dict to a canonical YAML string."""
    return yaml.dump(
        doc,
        Dumper=yaml.SafeDumper,
        default_flow_style=False,
        sort_keys=True,
        allow_unicode=True,
    )
