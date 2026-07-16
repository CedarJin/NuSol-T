"""Typed public result schema for ``nusol.solve()``."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class BoundsResult(BaseModel, extra="forbid"):
    """Ingredient fraction bounds with explicit semantic type."""

    type: Literal["hard_feasible_bounds", "slack_budget_bounds"]
    feasible_region: str
    values: dict[str, list[float]]


class SolveResult(BaseModel, extra="forbid"):
    """Public solve result returned as a JSON-compatible dict."""

    success: bool
    status: Literal["optimal", "error"]
    problem_id: str
    fractions: dict[str, float] = Field(default_factory=dict)
    bounds: BoundsResult | dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any]
    constraint_diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    observation_diagnostics: list[dict[str, Any]] = Field(default_factory=list)
    prior_contributions: list[dict[str, Any]] = Field(default_factory=list)
    manifest: dict[str, Any]
    error: str | None = None
