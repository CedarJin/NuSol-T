"""Pydantic v2 strict schemas for NuSol-T YAML 1.0 documents.

All models use ``extra="forbid"`` to reject unknown fields at load time.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, model_validator

# ── Version & Basis ───────────────────────────────────────────────────────────

class SchemaVersion(StrEnum):
    V1_0_DRAFT = "1.0-draft"
    V1_0 = "1.0"


class MassBasis(StrEnum):
    INPUT_FRACTION = "input_fraction"


class NutrientBasis(StrEnum):
    PER_100G = "per_100g_finished_product"


class BasisSpec(BaseModel, extra="forbid"):
    ingredient_mass: MassBasis = MassBasis.INPUT_FRACTION
    nutrient_amount: NutrientBasis = NutrientBasis.PER_100G


# ── Evidence (for priors / soft constraints) ─────────────────────────────────

class EvidenceSpec(BaseModel, extra="forbid"):
    status: Literal["example", "experimental", "calibrated", "validated", "deprecated"]
    source: str
    version: str | None = None


# ── Ingredients ───────────────────────────────────────────────────────────────

class DeclarationGroup(StrEnum):
    MAIN = "main"
    TWO_PERCENT = "two_percent_or_less"


class IngredientSpec(BaseModel, extra="forbid"):
    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$",
                    description="Stable ingredient identifier used throughout the document")
    name: str = Field(..., min_length=1,
                      description="Human-readable ingredient name")
    declaration_position: int = Field(
        ...,
        ge=0,
        description="0-based position in the ingredient declaration list",
    )
    declaration_group: DeclarationGroup = DeclarationGroup.MAIN


# ── Composition ───────────────────────────────────────────────────────────────

class NutrientColumnSpec(BaseModel, extra="forbid"):
    id: str = Field(..., description="Canonical nutrient identifier (e.g. 'energy_kcal')")
    unit: str = Field(..., description="Unit of measurement (e.g. 'kcal', 'g', 'mg', 'µg')")
    usda_nutrient_ids: list[int] = Field(
        default_factory=list,
        description="USDA nutrient IDs for adapter-based lookup",
    )
    usda_nutrient_names: list[str] = Field(
        default_factory=list,
        description="Controlled alias names for nutrient matching (not fuzzy)",
    )


class MissingValuePolicy(StrEnum):
    ERROR = "error"
    DROP_NUTRIENT = "drop_nutrient"
    DROP_INGREDIENT = "drop_ingredient"


class InlineCompositionSpec(BaseModel, extra="forbid"):
    source: Literal["inline"]
    nutrients: list[NutrientColumnSpec]
    values: dict[str, list[float | None]]


class CsvCompositionSpec(BaseModel, extra="forbid"):
    source: Literal["csv"]
    path: str
    sha256: str
    key_column: str = "ingredient_id"
    missing_value_policy: MissingValuePolicy = MissingValuePolicy.ERROR
    allow_extra_nutrients: bool = False
    nutrients: list[NutrientColumnSpec]


CompositionSpec = Annotated[
    InlineCompositionSpec | CsvCompositionSpec,
    Field(discriminator="source"),
]


# ── Observations ──────────────────────────────────────────────────────────────

class NutrientObservation(BaseModel, extra="forbid"):
    nutrient: str = Field(..., description="Canonical nutrient identifier")
    unit: str
    basis: NutrientBasis = NutrientBasis.PER_100G
    interval: tuple[float, float] | None = Field(
        None, description="Inclusive interval [lo, hi] for the true value",
    )
    exact: float | None = Field(
        None, description="Known exact value (e.g. from FNDDS ground truth)",
    )
    less_than: float | None = Field(
        None, description="Upper bound for 'less than X' declarations",
    )
    source: str | None = Field(
        None, description="Provenance of the observation interval (e.g. fndds_workflow_pm10pct)",
    )

    @model_validator(mode="after")
    def exactly_one_mode(self) -> NutrientObservation:
        modes = [self.interval, self.exact, self.less_than]
        if sum(1 for m in modes if m is not None) != 1:
            raise ValueError(
                "Exactly one of interval / exact / less_than is required "
                f"for observation '{self.nutrient}'"
            )
        if self.interval is not None:
            lo, hi = self.interval
            if lo > hi:
                raise ValueError(
                    f"interval lower ({lo}) > upper ({hi}) for '{self.nutrient}'"
                )
        if self.exact is not None and self.exact < 0:
            raise ValueError(f"exact value must be non-negative, got {self.exact}")
        if self.less_than is not None and self.less_than <= 0:
            raise ValueError(f"less_than must be positive, got {self.less_than}")
        return self


# ── Model ─────────────────────────────────────────────────────────────────────

class ModelType(StrEnum):
    LINEAR_MIXING = "linear_mixing"


class ModelSpec(BaseModel, extra="forbid"):
    type: Literal["linear_mixing"]
    config: dict[str, Any] = Field(default_factory=dict)


# ── Variables ─────────────────────────────────────────────────────────────────

class IngredientFractionVariableSpec(BaseModel, extra="forbid"):
    lower: float = Field(0.0, ge=0.0, le=1.0)
    upper: float = Field(1.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_bounds(self) -> IngredientFractionVariableSpec:
        if self.lower > self.upper:
            raise ValueError("ingredient fraction lower must not exceed upper")
        return self


class VariableSpec(BaseModel, extra="forbid"):
    ingredient_fractions: IngredientFractionVariableSpec


# ── Constraints ───────────────────────────────────────────────────────────────

class ConstraintMode(StrEnum):
    HARD = "hard"
    SOFT = "soft"


class LossFunction(StrEnum):
    SQUARED_HINGE = "squared_hinge"
    LEAST_SQUARES = "least_squares"


class ConstraintSpec(BaseModel, extra="forbid"):
    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    type: str = Field(..., description="Constraint type name, validated by constraint_registry")
    mode: ConstraintMode = ConstraintMode.HARD
    enabled: bool = True
    weight: float = Field(1.0, gt=0)
    config: dict[str, Any] = Field(default_factory=dict)
    evidence: EvidenceSpec | None = None


# ── Priors ────────────────────────────────────────────────────────────────────

class PriorSpec(BaseModel, extra="forbid"):
    """YAML-declared prior preference.

    This defines the mechanism for injecting prior knowledge into the objective.
    It does not imply that numeric prior parameters are scientifically calibrated;
    provenance and calibration status must be carried by ``evidence`` and the
    external calibration workflow.
    """

    id: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    type: str
    enabled: bool = True
    weight: float = Field(..., gt=0,
                          description="Prior weight — must be explicitly set (no default)")
    config: dict[str, Any] = Field(default_factory=dict)
    evidence: EvidenceSpec


# ── Solver ────────────────────────────────────────────────────────────────────

class BackendName(StrEnum):
    SCIPY_SLSQP = "scipy_slsqp"
    HIGHS_LP = "highs_lp"


class PointSolverSpec(BaseModel, extra="forbid"):
    backend: BackendName = BackendName.SCIPY_SLSQP
    options: dict = Field(default_factory=lambda: {
        "max_iterations": 500,
        "tolerance": 1e-8,
    })


class BoundsSolverSpec(BaseModel, extra="forbid"):
    backend: BackendName = BackendName.HIGHS_LP
    feasible_region: Literal["hard_constraints_only", "explicit_slack_budget"] = \
        "hard_constraints_only"
    slack_budgets: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_slack_budget(self) -> BoundsSolverSpec:
        if self.feasible_region == "explicit_slack_budget" and not self.slack_budgets:
            raise ValueError(
                "explicit_slack_budget mode requires non-empty slack_budgets"
            )
        if self.feasible_region == "hard_constraints_only" and self.slack_budgets:
            raise ValueError(
                "hard_constraints_only mode does not accept slack_budgets; "
                "use explicit_slack_budget to enable budgets"
            )
        negative = {key: value for key, value in self.slack_budgets.items() if value < 0}
        if negative:
            raise ValueError(f"slack_budgets must be non-negative: {negative}")
        return self


class SolverSpec(BaseModel, extra="forbid"):
    point: PointSolverSpec | None = None
    bounds: BoundsSolverSpec | None = None

    @model_validator(mode="after")
    def at_least_one_solver(self) -> SolverSpec:
        if self.point is None and self.bounds is None:
            raise ValueError("At least one of point / bounds solver must be configured")
        return self


# ── Output ────────────────────────────────────────────────────────────────────

class OutputSpec(BaseModel, extra="forbid"):
    path: str = Field(..., description="Output path for result JSON")
    include: list[Literal[
        "point_estimate",
        "feasible_bounds",
        "constraint_diagnostics",
        "nutrient_predicted",
        "nutrient_residuals",
    ]] = Field(default_factory=lambda: [
        "point_estimate",
        "feasible_bounds",
        "constraint_diagnostics",
    ])


# ── Top-level Document ────────────────────────────────────────────────────────

class SolveDocument(BaseModel, extra="forbid"):
    """Top-level model for a NuSol-T YAML 1.0 problem definition."""

    schema_version: Literal["1.0-draft", "1.0"]
    problem_id: str
    extends: list[str] = Field(default_factory=list)
    basis: BasisSpec
    ingredients: list[IngredientSpec]
    composition: CompositionSpec
    observations: list[NutrientObservation]
    model: ModelSpec
    variables: VariableSpec
    constraints: list[ConstraintSpec] = Field(default_factory=list)
    priors: list[PriorSpec] = Field(default_factory=list)
    solver: SolverSpec
    output: OutputSpec

    @model_validator(mode="after")
    def unique_ids(self) -> SolveDocument:
        ing_ids = [i.id for i in self.ingredients]
        if len(ing_ids) != len(set(ing_ids)):
            seen = [i for i in ing_ids if ing_ids.count(i) > 1]
            raise ValueError(f"Duplicate ingredient ids: {set(seen)}")

        c_ids = [c.id for c in self.constraints]
        if len(c_ids) != len(set(c_ids)):
            seen = [i for i in c_ids if c_ids.count(i) > 1]
            raise ValueError(f"Duplicate constraint ids: {set(seen)}")

        p_ids = [p.id for p in self.priors]
        if len(p_ids) != len(set(p_ids)):
            seen = [i for i in p_ids if p_ids.count(i) > 1]
            raise ValueError(f"Duplicate prior ids: {set(seen)}")

        if set(c_ids) & set(p_ids):
            overlap = set(c_ids) & set(p_ids)
            raise ValueError(
                f"Constraint and prior ids must be globally unique; "
                f"overlap: {overlap}"
            )
        return self
