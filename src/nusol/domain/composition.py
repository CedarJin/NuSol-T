"""Composition matrix — ingredient × nutrient values with missingness support."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from nusol.config.errors import ResourceError
from nusol.domain.nutrient import CANONICAL_NUTRIENT_MAP, Missingness, NutrientValue


class CompositionMatrix:
    """Typed composition matrix: ingredient_id × nutrient_id.

    Stores:
      - matrix: np.ndarray of shape (n_ingredients, n_nutrients)
      - missingness: ndarray of same shape tracking the status of each value
      - ingredient_ids: tuple[str, ...]
      - nutrient_ids: tuple[str, ...]
    """

    def __init__(
        self,
        values: list[list[float | None]],
        ingredient_ids: list[str],
        nutrient_ids: list[str],
        units: list[str],
        statuses: list[list[Missingness]] | None = None,
    ):
        if len(values) != len(ingredient_ids):
            raise ValueError(
                f"Number of value rows ({len(values)}) != "
                f"number of ingredients ({len(ingredient_ids)})"
            )
        if not values:
            raise ValueError("Empty composition matrix")
        n_nutrients = len(nutrient_ids)
        for i, row in enumerate(values):
            if len(row) != n_nutrients:
                raise ValueError(
                    f"Row {i} has {len(row)} values, expected {n_nutrients}"
                )

        self._ingredient_ids = tuple(ingredient_ids)
        self._nutrient_ids = tuple(nutrient_ids)
        self._units = tuple(units)

        # Build numeric matrix: None → NaN
        matrix = np.full((len(ingredient_ids), n_nutrients), np.nan, dtype=float)
        for i, row in enumerate(values):
            for j, val in enumerate(row):
                if val is not None:
                    matrix[i, j] = val

        self._matrix = matrix

        # Missingness matrix
        if statuses:
            self._statuses = tuple(tuple(s) for s in statuses)
        else:
            self._statuses = tuple(
                tuple("measured" if not np.isnan(matrix[i, j]) else "missing"
                       for j in range(n_nutrients))
                for i in range(len(ingredient_ids))
            )

    @property
    def matrix(self) -> np.ndarray:
        """Numpy array (n_ingredients, n_nutrients). NaN for missing."""
        return self._matrix.copy()

    @property
    def ingredient_ids(self) -> tuple[str, ...]:
        return self._ingredient_ids

    @property
    def nutrient_ids(self) -> tuple[str, ...]:
        return self._nutrient_ids

    @property
    def shape(self) -> tuple[int, int]:
        return self._matrix.shape

    def get_value(self, ingredient_id: str, nutrient_id: str) -> NutrientValue:
        """Get a single cell as a NutrientValue."""
        i = self._ingredient_ids.index(ingredient_id)
        j = self._nutrient_ids.index(nutrient_id)
        val = None if np.isnan(self._matrix[i, j]) else float(self._matrix[i, j])
        return NutrientValue(
            value=val,
            unit=self._units[j],
            status=self._statuses[i][j],
        )

    def get_ingredient_vector(
        self, ingredient_id: str
    ) -> dict[str, NutrientValue]:
        """Get all nutrients for an ingredient."""
        i = self._ingredient_ids.index(ingredient_id)
        result = {}
        for j, nid in enumerate(self._nutrient_ids):
            result[nid] = self.get_value(ingredient_id, nid)
        return result

    def has_nutrient(self, nutrient_id: str) -> bool:
        """Check if a nutrient is in the matrix."""
        return nutrient_id in self._nutrient_ids

    def any_missing_for_nutrient(self, nutrient_id: str) -> bool:
        """Check if ANY ingredient has missing data for a given nutrient."""
        j = self._nutrient_ids.index(nutrient_id)
        return any(self._statuses[i][j] == "missing" for i in range(len(self._ingredient_ids)))

    def missing_for_nutrient(self, nutrient_id: str) -> list[str]:
        """Return ingredient IDs with missing data for a given nutrient."""
        j = self._nutrient_ids.index(nutrient_id)
        return [
            self._ingredient_ids[i]
            for i in range(len(self._ingredient_ids))
            if self._statuses[i][j] == "missing"
        ]

    @classmethod
    def from_inline_dict(
        cls,
        values: dict[str, list[float | None]],
        ingredient_ids: list[str],
        nutrient_ids: list[str],
        units: list[str],
    ) -> CompositionMatrix:
        """Build from dict: {ingredient_id: [value, ...]}."""
        rows = []
        for ing_id in ingredient_ids:
            if ing_id not in values:
                raise ValueError(f"Missing ingredient '{ing_id}' in composition values")
            rows.append(values[ing_id])
        return cls(rows, ingredient_ids, nutrient_ids, units)

    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        key_column: str = "ingredient_id",
        missing_value_policy: str = "error",
    ) -> CompositionMatrix:
        """Build from a CSV file path."""
        path = Path(path)
        if not path.exists():
            raise ResourceError(f"Composition CSV not found: {path}")

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None:
                raise ResourceError(f"Empty CSV: {path}")
            if key_column not in reader.fieldnames:
                raise ResourceError(
                    f"Key column '{key_column}' not found in CSV columns: {reader.fieldnames}"
                )

            nutrient_ids = [c for c in reader.fieldnames if c != key_column]
            ingredient_ids: list[str] = []
            rows: list[list[float | None]] = []

            for row in reader:
                ing_id = row[key_column].strip()
                if not ing_id:
                    continue
                ingredient_ids.append(ing_id)
                values = []
                for nid in nutrient_ids:
                    raw = row.get(nid, "").strip()
                    if raw in ("", "NA", "NaN"):
                        if missing_value_policy == "error":
                            raise ResourceError(
                                f"Missing value for {ing_id}/{nid} "
                                f"(policy=error, use DROP_NUTRIENT or DROP_INGREDIENT)"
                            )
                        values.append(None)
                    else:
                        try:
                            values.append(float(raw))
                        except ValueError:
                            raise ResourceError(
                                f"Non-numeric value '{raw}' for {ing_id}/{nid}"
                            )
                rows.append(values)

        # Infer units from canonical map
        units = []
        for nid in nutrient_ids:
            if nid in CANONICAL_NUTRIENT_MAP:
                units.append(CANONICAL_NUTRIENT_MAP[nid][1])
            else:
                units.append("")

        return cls(rows, ingredient_ids, nutrient_ids, units)

    def to_dict(self) -> dict[str, Any]:
        """Export to dict for serialization."""
        return {
            "ingredient_ids": list(self._ingredient_ids),
            "nutrient_ids": list(self._nutrient_ids),
            "units": list(self._units),
            "matrix": self._matrix.tolist(),
            "statuses": [list(s) for s in self._statuses],
        }

    def __repr__(self) -> str:
        return (
            f"CompositionMatrix({self.shape[0]} ingr × {self.shape[1]} nu, "
            f"missing={sum(1 for s in self._statuses for v in s if v == 'missing')})"
        )
