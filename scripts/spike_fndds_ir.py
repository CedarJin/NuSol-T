"""Phase 3.5: FNDDS spike — validate IR and solver on real USDA FNDDS recipes.

Usage: uv run python scripts/spike_fndds_ir.py
Output: docs/spike_fndds_ir.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import yaml

# Add project root
project_root = Path(__file__).resolve().parent.parent  # NuSol-T/
sys.path.insert(0, str(project_root))

# ── Configuration ──
FNDDS_PATH = (
    project_root / ".." / "db"
    / "FoodData_Central_survey_food_json_2024-10-31"
    / "surveyDownload.json"
)
VALIDATION_IDS_PATH = project_root / "config" / "validation_recipes.json"
OUTPUT_DIR = project_root / "output" / "spike_fndds_ir"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Load FNDDS data ──
from nusol.data.fndds import FNDDSDataAdapter

adapter = FNDDSDataAdapter()
adapter.load(str(FNDDS_PATH))
print(f"Loaded {len(adapter)} FNDDS foods")


def find_recipes(adapter, min_ingredients, max_ingredients, limit=5):
    """Find recipes with ingredient count in range."""
    results = []
    for fdc_id_str, food in adapter._data.items():
        n = len(food.get("inputFoods", []))
        if min_ingredients <= n <= max_ingredients:
            results.append(fdc_id_str)
    return results[:limit]


def _clean_nutrient_id(name: str) -> str:
    """Convert nutrient name to a clean snake_case ID."""
    return (name.lower()
            .replace(" ", "_")
            .replace(",", "")
            .replace("(", "")
            .replace(")", "")
            .replace("-", "_")
            .replace("/", "_")
            .replace("__", "_")
            .strip("_"))


def recipe_to_yaml(adapter, fdc_id, problem_id, output_path):
    """Convert an FNDDS recipe to a YAML problem document."""
    recipe = adapter.get_recipe(fdc_id)
    if recipe is None:
        raise ValueError(f"Recipe {fdc_id} not found")

    ingredients = recipe["ingredients"]
    final_nutrients = recipe["final_nutrients"]
    description = recipe["description"]

    # Build ingredient list
    ing_list = []
    for i, ing in enumerate(ingredients):
        ing_list.append({
            "id": f"ing_{i}",
            "name": ing["description"],
            "declaration_position": i,
            "declaration_group": "main",
        })

    # Build nutrient columns and name→ID map
    name_to_id = {}
    nut_list = []
    for nr in final_nutrients.nutrients:
        nid = _clean_nutrient_id(nr.name)
        name_to_id[nr.name] = nid
        nut_list.append({
            "id": nid,
            "unit": nr.unit,
            "usda_nutrient_ids": [nr.nutrient_id],
        })

    # Build composition values from ingredient nutrient profiles
    from nusol.data.sr_legacy import SRLegacyDataAdapter
    sr_path = (
        project_root / ".." / "db"
        / "FoodData_Central_sr_legacy_food_json_2018-04"
        / "FoodData_Central_sr_legacy_food_json_2018-04.json"
    )
    sr_adapter = None
    if sr_path.exists():
        sr_adapter = SRLegacyDataAdapter()
        sr_adapter.load(str(sr_path))

    matrix, profiles, nut_names, mapping_meta = adapter.get_ingredient_nutrient_matrix(
        fdc_id, sr_legacy_db=sr_adapter,
    )

    # Build composition values dict
    values = {}
    for i, ing in enumerate(ing_list):
        ing_name = ingredients[i]["description"]
        row = []
        for nr in final_nutrients.nutrients:
            val = matrix.get(ing_name, {}).get(nr.name, None)
            row.append(val)
        values[ing["id"]] = row

    # Focus on common label nutrients (subset for practical inverse problems)
    LABEL_NUTRIENT_NAMES = {
        "Energy", "Protein", "Total lipid (fat)", "Carbohydrate, by difference",
        "Fiber, total dietary", "Total Sugars", "Sugars, added",
        "Fatty acids, total saturated", "Fatty acids, total trans",
        "Cholesterol", "Sodium, Na", "Calcium, Ca", "Iron, Fe",
        "Potassium, K", "Vitamin D (D2 + D3)",
    }

    # Build observations — only for nutrients with complete composition data
    observations = []
    nutrient_has_all_data = {}
    for nr in final_nutrients.nutrients:
        nid = name_to_id[nr.name]
        # Check if ALL ingredients have data for this nutrient
        all_present = all(
            matrix.get(ingredients[i]["description"], {}).get(nr.name, None) is not None
            for i in range(len(ingredients))
        )
        nutrient_has_all_data[nid] = all_present

    for nr in final_nutrients.nutrients:
        nid = name_to_id[nr.name]
        val = nr.amount
        # Only observe label nutrients + those with complete data
        if val > 0 and nutrient_has_all_data.get(nid, False) and nr.name in LABEL_NUTRIENT_NAMES:
            observations.append({
                "nutrient": nid,
                "unit": nr.unit,
                "interval": [round(val * 0.9, 2), round(val * 1.1, 2)],
            })

    doc = {
        "schema_version": "1.0-draft",
        "problem_id": problem_id,
        "basis": {
            "ingredient_mass": "input_fraction",
            "nutrient_amount": "per_100g_finished_product",
        },
        "ingredients": ing_list,
        "composition": {
            "source": "inline",
            "nutrients": nut_list,
            "values": values,
        },
        "observations": observations,
        "model": {"type": "linear_mixing"},
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "constraints": [
            {"id": "mass_balance", "type": "mass_balance", "mode": "hard"},
            {"id": "label_fit", "type": "nutrient_interval", "mode": "soft", "weight": 10.0},
        ],
        "solver": {"point": {"backend": "scipy_slsqp"}},
        "output": {"path": f"output/{problem_id}.json"},
    }

    # Write YAML
    with open(output_path, "w") as f:
        yaml.dump(doc, f, sort_keys=False, default_flow_style=None, allow_unicode=True)

    return output_path


def analyze_results(fdc_id, recipe, result_yaml_path):
    """Run solve and analyze results."""
    from nusol.api import solve

    print(f"\n  Solving {result_yaml_path.name}...")
    try:
        result = solve(str(result_yaml_path))
        print(f"    Success: {result['success']}")
        if result["success"]:
            fracs = result["fractions"]
            total = sum(fracs.values())
            print(f"    Ingredients: {len(fracs)}, mass sum: {total:.4f}")
            max_frac = max(fracs.values())
            max_ing = max(fracs, key=fracs.get)
            print(f"    Top: {max_ing} = {max_frac:.4f}")

            # Compare with true fractions if available
            true_fracs = adapter.get_ingredient_fractions(fdc_id)
            if true_fracs and len(true_fracs) > 0:
                # Map our ingredient IDs back to descriptions
                ing_list = recipe["ingredients"]
                id_to_desc = {f"ing_{i}": ing["description"] for i, ing in enumerate(ing_list)}
                desc_to_id = {v: k for k, v in id_to_desc.items()}

                # Compute MAE (union)
                all_ings = set(true_fracs.keys()) | set(desc_to_id.keys())
                errors = []
                for ing in all_ings:
                    true_val = true_fracs.get(ing, 0)
                    mapped_key = desc_to_id.get(ing)
                    est_val = fracs.get(mapped_key, 0) if mapped_key else 0
                    errors.append(abs(true_val - est_val))
                mae = sum(errors) / len(errors) if errors else 0
                print(f"    MAE (vs true fractions): {mae:.4f}")

        else:
            print(f"    Error: {result.get('error', 'unknown')}")
    except Exception as e:
        print(f"    FAILED: {e}")
        import traceback
        traceback.print_exc()


def main():
    # Find recipes of varying complexity
    simple = find_recipes(adapter, 2, 3, limit=3)
    medium = find_recipes(adapter, 4, 6, limit=3)
    complex_recipes = find_recipes(adapter, 8, 15, limit=3)

    print(f"\nFound: {len(simple)} simple, {len(medium)} medium, {len(complex_recipes)} complex")

    # Pick the first of each
    selected = [
        ("simple", simple[0] if simple else None),
        ("medium", medium[0] if medium else None),
        ("complex", complex_recipes[0] if complex_recipes else None),
    ]

    results_md = ["# Phase 3.5: FNDDS Spike Results\n",
                  f"> Date: 2026-07-05",
                  f"> FNDDS file: {FNDDS_PATH.name}",
                  f"> Recipes: {len([s for _, s in selected if s])}",
                  "", "| Type | FDC ID | Description | Ingredients | Nutrients | Solve? | MAE |",
                  "|------|--------|-------------|-------------|-----------|--------|-----|"]

    for label, fdc_id in selected:
        if fdc_id is None:
            print(f"\nNo {label} recipe found")
            continue

        recipe = adapter.get_recipe(fdc_id)
        if recipe is None:
            continue

        problem_id = f"spike_{label}_{fdc_id}"
        yaml_path = OUTPUT_DIR / f"{problem_id}.yaml"

        print(f"\n{'='*60}")
        print(f"{label}: FDC {fdc_id} — {recipe['description']}")
        print(f"  Ingredients: {len(recipe['ingredients'])}")
        print(f"  Nutrients: {len(recipe['final_nutrients'].nutrients)}")

        # Convert to YAML
        recipe_to_yaml(adapter, fdc_id, problem_id, yaml_path)

        # Solve and analyze
        from nusol.api import solve
        try:
            result = solve(str(yaml_path))
            success = result["success"]
            mae_str = ""
            if success:
                true_fracs = adapter.get_ingredient_fractions(fdc_id)
                ing_list = recipe["ingredients"]
                id_to_desc = {f"ing_{i}": ing["description"] for i, ing in enumerate(ing_list)}
                desc_to_id = {v: k for k, v in id_to_desc.items()}
                fracs = result["fractions"]

                all_ings = set(true_fracs.keys()) | set(desc_to_id.keys())
                errors = []
                for ing_name in all_ings:
                    tv = true_fracs.get(ing_name, 0)
                    mk = desc_to_id.get(ing_name)
                    ev = fracs.get(mk, 0) if mk else 0
                    errors.append(abs(tv - ev))
                mae = sum(errors) / len(errors) if errors else 0
                mae_str = f"{mae:.4f}"
                print(f"  MAE: {mae_str}")
            else:
                print(f"  Solve FAILED")

            results_md.append(
                f"| {label} | {fdc_id} | {recipe['description'][:40]} | "
                f"{len(recipe['ingredients'])} | {len(recipe['final_nutrients'].nutrients)} | "
                f"{'✅' if success else '❌'} | {mae_str} |"
            )

        except Exception as e:
            print(f"  ERROR: {e}")
            results_md.append(
                f"| {label} | {fdc_id} | {recipe['description'][:40]} | "
                f"{len(recipe['ingredients'])} | {len(recipe['final_nutrients'].nutrients)} | "
                f"❌ | error |"
            )

    # Write results
    results_path = project_root / "docs" / "spike_fndds_ir.md"
    results_path.write_text("\n".join(results_md) + "\n")
    print(f"\nResults written to {results_path}")


if __name__ == "__main__":
    main()
