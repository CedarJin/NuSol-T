"""Core Pydantic schemas for NuSol-T."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ── Nutrient Records ────────────────────────────────────────────────────────

class NutrientRecord(BaseModel):
    """Unified nutrient record for a single nutrient value."""

    nutrient_id: int = Field(..., description="USDA nutrient ID (e.g. 1008 for Energy)")
    nutrient_number: str = Field(..., description="USDA nutrient number (e.g. '208')")
    name: str = Field(..., description="Standard nutrient name (e.g. 'Energy')")
    amount: float = Field(..., description="Numeric value")
    unit: str = Field(..., description="Unit of measurement (e.g. 'kcal', 'g', 'mg')")
    rank: Optional[int] = Field(default=None, description="USDA sort rank")

    # Uncertainty bounds (populated after label-interval conversion)
    lower_bound: Optional[float] = Field(default=None, description="Lower bound of possible true value")
    upper_bound: Optional[float] = Field(default=None, description="Upper bound of possible true value")

    # Provenance
    derivation_code: Optional[str] = Field(default=None, description="Derivation method code")
    source_description: Optional[str] = Field(default=None, description="Source description")
    data_points: Optional[int] = Field(default=None, description="Number of data points")


class NutrientProfile(BaseModel):
    """Nutrient profile for a food or ingredient."""

    fdc_id: Optional[int] = Field(default=None, description="FDC ID if available")
    description: str = Field(..., description="Food/ingredient description")
    nutrients: list[NutrientRecord] = Field(default_factory=list)
    basis: str = Field(default="per_100g", description="Nutrient basis (per_100g or per_serving)")

    def get_nutrient_by_name(self, name: str) -> Optional[NutrientRecord]:
        """Get a nutrient record by standard name."""
        for n in self.nutrients:
            if n.name == name:
                return n
        return None

    def get_nutrient_by_id(self, nutrient_id: int) -> Optional[NutrientRecord]:
        """Get a nutrient record by USDA nutrient ID."""
        for n in self.nutrients:
            if n.nutrient_id == nutrient_id:
                return n
        return None

    def nutrient_names(self) -> list[str]:
        """Return all nutrient names in this profile."""
        return [n.name for n in self.nutrients]

    def to_dict(self) -> dict[str, float]:
        """Convert to {nutrient_name: amount} dict."""
        return {n.name: n.amount for n in self.nutrients}

    def __len__(self) -> int:
        return len(self.nutrients)


# ── Ingredient Tree ─────────────────────────────────────────────────────────

class MappingCandidate(BaseModel):
    """A candidate match from ingredient text to nutrient database."""

    fdc_id: int = Field(..., description="FDC ID of the candidate")
    description: str = Field(..., description="Description in the database")
    source: str = Field(..., description="Source database: SR_LEGACY, FNDDS, FOUNDATION")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Match confidence 0-1")
    nutrient_profile: Optional[NutrientProfile] = Field(default=None)
    match_method: str = Field(default="exact", description="How the match was made")


class IngredientNode(BaseModel):
    """A single node in the ingredient parse tree."""

    name: str = Field(..., description="Raw ingredient text as it appears on the label")
    normalized_name: str = Field(default="", description="Normalized / cleaned ingredient name")
    position: int = Field(default=0, ge=0, description="Position in the ingredient list (0-based)")
    is_compound: bool = Field(default=False, description="Whether this is a compound ingredient")
    is_sub_ingredient: bool = Field(default=False, description="Whether this is a sub-ingredient inside parentheses")
    is_low_impact: bool = Field(default=False, description="Whether this is in the ≤2% group")
    is_alternative: bool = Field(default=False, description="Whether this is part of an AND/OR group")
    parenthetical_text: Optional[str] = Field(default=None, description="Original parenthetical text if any")
    children: list[IngredientNode] = Field(default_factory=list, description="Sub-ingredients")
    mapping_candidates: list[MappingCandidate] = Field(default_factory=list)

    def get_all_ingredients(self) -> list[IngredientNode]:
        """Return self and all descendants in a flat list."""
        result = [self]
        for child in self.children:
            result.extend(child.get_all_ingredients())
        return result

    def leaf_count(self) -> int:
        """Count of leaf nodes (ingredients without children)."""
        if not self.children:
            return 1
        return sum(c.leaf_count() for c in self.children)


class IngredientTree(BaseModel):
    """Parsed ingredient list tree for a product."""

    raw_text: str = Field(..., description="Original ingredient list text")
    root_ingredients: list[IngredientNode] = Field(default_factory=list)
    two_percent_group: list[IngredientNode] = Field(default_factory=list)

    def all_ingredients(self) -> list[IngredientNode]:
        """Return all ingredient nodes (flattened)."""
        result = []
        for ing in self.root_ingredients:
            result.extend(ing.get_all_ingredients())
        for ing in self.two_percent_group:
            result.extend(ing.get_all_ingredients())
        return result

    def main_ingredient_count(self) -> int:
        """Count of ingredients in the main list (excluding ≤2% group)."""
        return len(self.root_ingredients)

    def total_ingredient_count(self) -> int:
        """Total number of individual ingredient nodes."""
        return len(self.all_ingredients())


# ── Product Observation ─────────────────────────────────────────────────────

class ProductObservation(BaseModel):
    """A product observation — the input to the NuSol-T solver."""

    fdc_id: int = Field(..., description="FDC ID")
    description: str = Field(..., description="Product description")
    source: str = Field(..., description="Data source: FNDDS or BRANDED")

    # Label nutrients
    label_nutrients: list[NutrientRecord] = Field(default_factory=list)
    serving_size_g: float = Field(default=100.0, gt=0.0, description="Serving size in grams")

    # Ingredient
    ingredient_tree: Optional[IngredientTree] = Field(default=None)

    # Meta
    brand_owner: Optional[str] = Field(default=None)
    branded_category: Optional[str] = Field(default=None)
    gtin_upc: Optional[str] = Field(default=None)
    food_code: Optional[str] = Field(default=None)

    # Gold standard (only available during FNDDS validation)
    true_ingredient_fractions: Optional[dict[str, float]] = Field(default=None)
    true_nutrient_profile: Optional[NutrientProfile] = Field(default=None)

    def has_ground_truth(self) -> bool:
        """Whether this observation has ground truth for validation."""
        return self.true_ingredient_fractions is not None

    def nutrient_names(self) -> list[str]:
        """Return names of label nutrients."""
        return [n.name for n in self.label_nutrients]


# ── Trust Report ────────────────────────────────────────────────────────────

class IngredientEstimate(BaseModel):
    """Estimated ingredient fraction with uncertainty."""

    ingredient_name: str = Field(..., description="Ingredient name")
    normalized_name: Optional[str] = Field(default=None)
    point_estimate: float = Field(..., ge=0.0, le=1.0, description="Point estimate (mass fraction)")
    lower_bound: float = Field(default=0.0, ge=0.0, le=1.0, description="Feasible lower bound")
    upper_bound: float = Field(default=1.0, ge=0.0, le=1.0, description="Feasible upper bound")
    interval_80: tuple[float, float] = Field(default=(0.0, 1.0), description="80% credible interval")
    interval_95: tuple[float, float] = Field(default=(0.0, 1.0), description="95% credible interval")
    mapping_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    fdc_id: Optional[int] = Field(default=None)
    is_low_impact: bool = Field(default=False)

    @property
    def interval_width(self) -> float:
        """Width of the feasible interval."""
        return self.upper_bound - self.lower_bound


class NutrientEstimate(BaseModel):
    """Estimated / expanded nutrient value with uncertainty."""

    nutrient_name: str = Field(...)
    unit: str = Field(...)
    median: float = Field(...)
    p5: float = Field(...)
    p95: float = Field(...)
    label_value: Optional[float] = Field(default=None)
    source_coverage: float = Field(default=1.0, ge=0.0, le=1.0)


class IdentifiabilityReport(BaseModel):
    """Report on how identifiable ingredient fractions are."""

    n_ingredients: int = Field(default=0)
    n_label_nutrients: int = Field(default=0)
    degrees_of_freedom: int = Field(default=0)
    identifiable_ingredients: list[str] = Field(default_factory=list)
    poorly_identified_ingredients: list[str] = Field(default_factory=list)
    interval_width_median: float = Field(default=0.0)


class MappingProvenance(BaseModel):
    """Provenance record for an ingredient mapping."""

    ingredient_name: str = Field(...)
    mapped_to: str = Field(...)
    fdc_id: int = Field(...)
    source: str = Field(...)
    confidence: float = Field(default=1.0)
    alternative_candidates: list[str] = Field(default_factory=list)


class TrustReport(BaseModel):
    """Complete trust report for a single product."""

    fdc_id: int = Field(...)
    description: str = Field(...)

    # Estimates
    ingredient_estimates: list[IngredientEstimate] = Field(default_factory=list)
    expanded_nutrients: list[NutrientEstimate] = Field(default_factory=list)

    # Quality
    nutrient_residuals: dict[str, float] = Field(default_factory=dict)
    constraint_slacks: dict[str, float] = Field(default_factory=dict)
    constraint_conflicts: list[str] = Field(default_factory=list)

    # Uncertainty
    identifiability_report: IdentifiabilityReport = Field(default_factory=IdentifiabilityReport)

    # Provenance
    mapping_provenance: list[MappingProvenance] = Field(default_factory=list)
    data_source_version: dict[str, str] = Field(default_factory=dict)

    # Conclusion
    warnings: list[str] = Field(default_factory=list)
    trust_grade: str = Field(default="C")
    trust_score: float = Field(default=50.0, ge=0.0, le=100.0)

    # Solver metadata
    solver_name: Optional[str] = Field(default=None)
    solve_time_s: Optional[float] = Field(default=None)
    n_iterations: Optional[int] = Field(default=None)

    def add_warning(self, warning: str) -> None:
        """Append a warning message."""
        self.warnings.append(warning)

    def has_conflicts(self) -> bool:
        """Whether any constraints are in conflict."""
        return len(self.constraint_conflicts) > 0


# ── Solver Result ───────────────────────────────────────────────────────────

class SolverResult(BaseModel):
    """Raw result from a solver run."""

    success: bool = Field(default=False)
    message: str = Field(default="")

    # Point estimates
    x_point: dict[str, float] = Field(default_factory=dict)
    moisture_change: Optional[float] = Field(default=None)
    objective_value: Optional[float] = Field(default=None)

    # Interval estimates
    x_lower: dict[str, float] = Field(default_factory=dict)
    x_upper: dict[str, float] = Field(default_factory=dict)

    # Fit quality
    nutrient_predicted: dict[str, float] = Field(default_factory=dict)
    nutrient_residuals: dict[str, float] = Field(default_factory=dict)
    constraint_values: dict[str, float] = Field(default_factory=dict)
    constraint_slacks: dict[str, float] = Field(default_factory=dict)
    active_constraints: list[str] = Field(default_factory=list)

    # Meta
    solver_name: str = Field(default="")
    n_iterations: int = Field(default=0)
    n_func_evals: int = Field(default=0)
    solve_time_s: float = Field(default=0.0)

    @property
    def total_mass(self) -> float:
        """Sum of all ingredient fractions."""
        return sum(self.x_point.values()) if self.x_point else 0.0

    def get_sorted_ingredients(self) -> list[tuple[str, float]]:
        """Get ingredients sorted by estimated fraction (descending)."""
        return sorted(self.x_point.items(), key=lambda x: x[1], reverse=True)
