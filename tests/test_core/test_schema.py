"""Tests for core Pydantic schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError


class TestNutrientRecord:
    """Tests for NutrientRecord."""

    def test_create_valid_record(self):
        from nusol.core.schema import NutrientRecord

        r = NutrientRecord(
            nutrient_id=1008,
            nutrient_number="208",
            name="Energy",
            amount=250.0,
            unit="kcal",
        )
        assert r.nutrient_id == 1008
        assert r.amount == 250.0
        assert r.name == "Energy"

    def test_create_record_with_optional_fields(self):
        from nusol.core.schema import NutrientRecord

        r = NutrientRecord(
            nutrient_id=1008,
            nutrient_number="208",
            name="Energy",
            amount=250.0,
            unit="kcal",
            rank=300,
            lower_bound=245.0,
            upper_bound=255.0,
            derivation_code="LCCS",
            source_description="Manufacturer's analytical",
            data_points=5,
        )
        assert r.rank == 300
        assert r.lower_bound == 245.0
        assert r.upper_bound == 255.0
        assert r.derivation_code == "LCCS"

    def test_missing_required_fields_raises_error(self):
        from nusol.core.schema import NutrientRecord

        with pytest.raises(ValidationError):
            NutrientRecord(name="Energy")


class TestNutrientProfile:
    """Tests for NutrientProfile."""

    def test_create_profile(self, sample_nutrient_profile):
        assert len(sample_nutrient_profile) == 4
        assert sample_nutrient_profile.description == "Test Food"

    def test_get_nutrient_by_name(self, sample_nutrient_profile):
        nut = sample_nutrient_profile.get_nutrient_by_name("Energy")
        assert nut is not None
        assert nut.amount == 250.0

    def test_get_nutrient_by_name_missing(self, sample_nutrient_profile):
        nut = sample_nutrient_profile.get_nutrient_by_name("Fiber")
        assert nut is None

    def test_nutrient_names(self, sample_nutrient_profile):
        names = sample_nutrient_profile.nutrient_names()
        assert "Energy" in names
        assert "Protein" in names

    def test_to_dict(self, sample_nutrient_profile):
        d = sample_nutrient_profile.to_dict()
        assert d["Energy"] == 250.0
        assert d["Protein"] == 10.0

    def test_empty_profile(self):
        from nusol.core.schema import NutrientProfile

        p = NutrientProfile(description="Empty")
        assert len(p) == 0
        assert p.to_dict() == {}


class TestIngredientTree:
    """Tests for IngredientTree and IngredientNode."""

    def test_create_ingredient_node(self):
        from nusol.core.schema import IngredientNode

        node = IngredientNode(name="SUGAR", normalized_name="sugar", position=0)
        assert node.name == "SUGAR"
        assert node.position == 0
        assert not node.is_compound
        assert node.leaf_count() == 1

    def test_compound_ingredient_node(self):
        from nusol.core.schema import IngredientNode

        parent = IngredientNode(
            name="ENRICHED FLOUR",
            normalized_name="enriched flour",
            position=0,
            is_compound=True,
            children=[
                IngredientNode(name="WHEAT FLOUR", normalized_name="wheat flour", position=0, is_sub_ingredient=True),
                IngredientNode(name="IRON", normalized_name="iron", position=1, is_sub_ingredient=True),
            ],
        )
        assert parent.is_compound
        assert parent.leaf_count() == 2
        all_nodes = parent.get_all_ingredients()
        assert len(all_nodes) == 3  # parent + 2 children

    def test_ingredient_tree(self, sample_ingredient_tree):
        assert sample_ingredient_tree.main_ingredient_count() == 3
        # 3 root ingredients (1 compound + 2 simple), compound has 3 sub → 6 total
        assert sample_ingredient_tree.total_ingredient_count() == 6

    def test_ingredient_tree_with_two_percent_group(self):
        from nusol.core.schema import IngredientTree, IngredientNode

        tree = IngredientTree(
            raw_text="SUGAR, SALT, CONTAINS 2% OR LESS OF: SPICES",
            root_ingredients=[
                IngredientNode(name="SUGAR", normalized_name="sugar", position=0),
                IngredientNode(name="SALT", normalized_name="salt", position=1),
            ],
            two_percent_group=[
                IngredientNode(name="SPICES", normalized_name="spices", position=0, is_low_impact=True),
            ],
        )
        assert tree.total_ingredient_count() == 3
        assert tree.two_percent_group[0].is_low_impact


class TestProductObservation:
    """Tests for ProductObservation."""

    def test_create_observation(self, sample_product_observation):
        obs = sample_product_observation
        assert obs.fdc_id == 999999
        assert obs.source == "FNDDS"
        assert obs.serving_size_g == 100.0

    def test_has_ground_truth(self, sample_product_observation):
        assert sample_product_observation.has_ground_truth()

    def test_no_ground_truth(self):
        from nusol.core.schema import ProductObservation

        obs = ProductObservation(
            fdc_id=12345,
            description="No GT",
            source="BRANDED",
            serving_size_g=28.0,
        )
        assert not obs.has_ground_truth()

    def test_nutrient_names(self, sample_product_observation):
        names = sample_product_observation.nutrient_names()
        assert "Energy" in names


class TestTrustReport:
    """Tests for TrustReport and related models."""

    def test_create_report(self, sample_trust_report):
        assert sample_trust_report.trust_grade == "A"
        assert sample_trust_report.trust_score == 85.0
        assert len(sample_trust_report.ingredient_estimates) == 2

    def test_add_warning(self, sample_trust_report):
        sample_trust_report.add_warning("Test warning")
        assert len(sample_trust_report.warnings) == 1
        assert sample_trust_report.warnings[0] == "Test warning"

    def test_has_conflicts_empty(self, sample_trust_report):
        assert not sample_trust_report.has_conflicts()

    def test_has_conflicts(self, sample_trust_report):
        sample_trust_report.constraint_conflicts.append("mass balance violated")
        assert sample_trust_report.has_conflicts()

    def test_ingredient_estimate_interval_width(self):
        from nusol.core.schema import IngredientEstimate

        est = IngredientEstimate(
            ingredient_name="flour",
            point_estimate=0.5,
            lower_bound=0.4,
            upper_bound=0.6,
        )
        assert est.interval_width == pytest.approx(0.2)

    def test_identifiability_report(self):
        from nusol.core.schema import IdentifiabilityReport

        r = IdentifiabilityReport(
            n_ingredients=5,
            n_label_nutrients=7,
            degrees_of_freedom=2,
            identifiable_ingredients=["flour"],
            poorly_identified_ingredients=["spices", "natural flavor"],
        )
        assert r.n_ingredients == 5
        assert len(r.identifiable_ingredients) == 1
        assert len(r.poorly_identified_ingredients) == 2


class TestSolverResult:
    """Tests for SolverResult."""

    def test_create_empty_result(self):
        from nusol.core.schema import SolverResult

        r = SolverResult()
        assert not r.success
        assert r.total_mass == 0.0

    def test_create_result_with_values(self):
        from nusol.core.schema import SolverResult

        r = SolverResult(
            success=True,
            message="Converged",
            x_point={"flour": 0.5, "sugar": 0.3, "oil": 0.2},
            x_lower={"flour": 0.4, "sugar": 0.2, "oil": 0.1},
            x_upper={"flour": 0.6, "sugar": 0.4, "oil": 0.3},
            objective_value=0.05,
            solver_name="trust-constr",
            n_iterations=42,
        )
        assert r.success
        assert r.total_mass == 1.0
        assert len(r.x_point) == 3

    def test_get_sorted_ingredients(self):
        from nusol.core.schema import SolverResult

        r = SolverResult(
            success=True,
            x_point={"flour": 0.5, "sugar": 0.3, "oil": 0.2},
        )
        sorted_ing = r.get_sorted_ingredients()
        assert sorted_ing[0] == ("flour", 0.5)
        assert sorted_ing[-1] == ("oil", 0.2)

    def test_total_mass_empty(self):
        from nusol.core.schema import SolverResult

        r = SolverResult()
        assert r.total_mass == 0.0


class TestMappingCandidate:
    """Tests for MappingCandidate."""

    def test_create_mapping_candidate(self):
        from nusol.core.schema import MappingCandidate

        mc = MappingCandidate(
            fdc_id=789012,
            description="Wheat flour, white, all-purpose, enriched, bleached",
            source="SR_LEGACY",
            confidence=0.95,
            match_method="fuzzy",
        )
        assert mc.confidence == 0.95
        assert mc.source == "SR_LEGACY"

    def test_confidence_bounds(self):
        from nusol.core.schema import MappingCandidate

        with pytest.raises(ValidationError):
            MappingCandidate(fdc_id=1, description="x", source="SR_LEGACY", confidence=1.5)

        with pytest.raises(ValidationError):
            MappingCandidate(fdc_id=1, description="x", source="SR_LEGACY", confidence=-0.1)
