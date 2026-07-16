from __future__ import annotations

from pathlib import Path

import pytest
import yaml


@pytest.fixture
def prior_yaml(tmp_path: Path) -> Path:
    doc = {
        "schema_version": "1.0-draft",
        "problem_id": "prior_test",
        "basis": {
            "ingredient_mass": "input_fraction",
            "nutrient_amount": "per_100g_finished_product",
        },
        "ingredients": [
            {"id": "flour", "name": "Wheat flour", "declaration_position": 0},
            {"id": "sugar", "name": "Sugar", "declaration_position": 1},
            {"id": "oil", "name": "Oil", "declaration_position": 2},
        ],
        "composition": {
            "source": "inline",
            "nutrients": [{"id": "energy_kcal", "unit": "kcal"}],
            "values": {
                "flour": [364.0],
                "sugar": [387.0],
                "oil": [884.0],
            },
        },
        "observations": [
            {"nutrient": "energy_kcal", "unit": "kcal", "interval": [400, 450]},
        ],
        "model": {"type": "linear_mixing"},
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "constraints": [
            {"id": "mass_balance", "type": "mass_balance", "mode": "hard"},
            {
                "id": "label_fit",
                "type": "nutrient_interval",
                "mode": "soft",
                "weight": 1.0,
            },
        ],
        "solver": {"point": {"backend": "scipy_slsqp"}},
        "output": {"path": "output/prior_test.json"},
    }
    path = tmp_path / "prior_test.yaml"
    path.write_text(yaml.safe_dump(doc, sort_keys=False))
    return path


def _evidence() -> dict[str, str]:
    return {
        "status": "experimental",
        "source": "unit_test",
        "version": "2026-07-15",
    }


def test_fraction_interval_prior_contributes_to_result(prior_yaml: Path) -> None:
    import nusol

    doc = yaml.safe_load(prior_yaml.read_text())
    doc["priors"] = [
        {
            "id": "sugar_limit",
            "type": "fraction_interval_prior",
            "weight": 2.0,
            "evidence": _evidence(),
            "config": {"ingredient": "sugar", "interval": [0.0, 0.05]},
        }
    ]
    prior_yaml.write_text(yaml.safe_dump(doc, sort_keys=False))

    result = nusol.solve(prior_yaml)

    assert result["success"] is True
    assert result["manifest"]["priors"][0]["id"] == "sugar_limit"
    assert result["prior_contributions"]
    assert all(item["source_id"] == "sugar_limit" for item in result["prior_contributions"])


def test_recipe_center_prior_quadratic_objective_is_supported(
    prior_yaml: Path,
) -> None:
    import nusol

    doc = yaml.safe_load(prior_yaml.read_text())
    doc["priors"] = [
        {
            "id": "center",
            "type": "recipe_center_prior",
            "weight": 0.5,
            "evidence": _evidence(),
            "config": {"center": {"flour": 0.7, "sugar": 0.2, "oil": 0.1}},
        }
    ]
    prior_yaml.write_text(yaml.safe_dump(doc, sort_keys=False))

    result = nusol.solve(prior_yaml)

    assert result["success"] is True
    assert any(item["type"] == "quadratic_penalty" for item in result["prior_contributions"])


def test_unknown_prior_type_fails_explicitly(prior_yaml: Path) -> None:
    import nusol

    doc = yaml.safe_load(prior_yaml.read_text())
    doc["priors"] = [
        {
            "id": "unknown",
            "type": "not_registered",
            "weight": 1.0,
            "evidence": _evidence(),
            "config": {},
        }
    ]
    prior_yaml.write_text(yaml.safe_dump(doc, sort_keys=False))

    with pytest.raises(Exception, match="unknown type"):
        nusol.solve(prior_yaml)


def test_objective_matches_diagnostic_contributions(prior_yaml: Path) -> None:
    import nusol

    doc = yaml.safe_load(prior_yaml.read_text())
    doc["priors"] = [
        {
            "id": "anti_extreme",
            "type": "anti_extreme_prior",
            "weight": 0.25,
            "evidence": _evidence(),
            "config": {"ingredients": ["flour", "sugar", "oil"]},
        }
    ]
    prior_yaml.write_text(yaml.safe_dump(doc, sort_keys=False))

    result = nusol.solve(prior_yaml)

    contribution_sum = sum(
        item["weighted_penalty"] for item in result["constraint_diagnostics"]
    )
    objective = result["diagnostics"]["point"]["objective_value"]
    assert contribution_sum == pytest.approx(objective, abs=1e-5)
