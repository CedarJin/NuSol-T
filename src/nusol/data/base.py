"""Abstract base class for data adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from nusol.core.schema import NutrientProfile, ProductObservation


class DataAdapterBase(ABC):
    """Abstract base class for all data source adapters."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    @abstractmethod
    def load(self, path: str | Path) -> None:
        """Load raw data from a file path."""
        ...

    @abstractmethod
    def get_nutrient_profile(self, fdc_id: int) -> NutrientProfile | None:
        """Get the nutrient profile for a food by FDC ID."""
        ...

    @abstractmethod
    def to_product_observation(self, fdc_id: int) -> ProductObservation | None:
        """Convert a data record to a ProductObservation."""
        ...
