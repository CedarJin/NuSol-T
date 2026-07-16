"""Ingredient model with stable ID."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Ingredient(BaseModel):
    """An ingredient in a food product formulation.

    Uses a stable string ``id`` (not the description) as the primary key.
    This ID is used throughout the IR, matrix, and results.
    """

    id: str = Field(
        ...,
        description="Stable ingredient identifier (primary key throughout the system)",
    )
    name: str = Field(..., description="Human-readable ingredient name")
    declaration_position: int = Field(
        ..., ge=0,
        description="0-based position in the ingredient declaration list",
    )
    declaration_group: Literal["main", "two_percent_or_less"] = Field(
        default="main",
        description="Whether this is a main ingredient or in the ≤2% group",
    )
