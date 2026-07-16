#!/usr/bin/env python3
"""export_fndds_recipes.py — Convert FNDDS recipes to branded-food-conditions YAML.

Simulates what the Branded Food pipeline (Phase 5-6) sees:
  1. Ingredient NAMES from the label → look up SR Legacy by name (not FNDDS code)
  2. Nutrition Facts panel → observations from FNDDS final product nutrients
  3. FDA label constraints only (mass_balance, ingredient_order, nutrient_interval)

This validates the SOLVER under branded-food conditions.
Ground truth fractions saved separately for MAE computation.

Usage::
    uv run python scripts/export_fndds_recipes.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from nusol.data.fortification import (
    aggregate_contributions,
    build_fortification_ingredient,
    classify_export_failure,
    fortification_diagnostics,
    is_fortificant,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FNDDS_PATH = (
    PROJECT_ROOT / ".." / "db"
    / "FoodData_Central_survey_food_json_2024-10-31" / "surveyDownload.json"
)
SR_PATH = (
    PROJECT_ROOT / ".." / "db"
    / "FoodData_Central_sr_legacy_food_json_2018-04"
    / "FoodData_Central_sr_legacy_food_json_2018-04.json"
)
OUTPUT_DIR = PROJECT_ROOT / "output" / "fndds_benchmark"

# ── FDA Nutrition Facts Label (2016+) mandatory nutrients ─────────────────
# FNDDS nutrient name → (canonical_id, unit)
FDA_LABEL: dict[str, tuple[str, str]] = {
    "Energy":                           ("energy_kcal",     "kcal"),
    "Protein":                          ("protein_g",       "g"),
    "Total lipid (fat)":                ("fat_g",           "g"),
    "Carbohydrate, by difference":      ("carbohydrate_g",  "g"),
    "Fiber, total dietary":             ("fiber_g",         "g"),
    "Total Sugars":                     ("sugars_g",        "g"),
    "Fatty acids, total saturated":     ("saturated_fat_g", "g"),
    "Sodium, Na":                       ("sodium_mg",       "mg"),
    "Calcium, Ca":                      ("calcium_mg",      "mg"),
    "Iron, Fe":                         ("iron_mg",         "mg"),
    "Potassium, K":                     ("potassium_mg",    "mg"),
    "Vitamin D (D2 + D3)":              ("vitamin_d_mcg",   "mcg"),
    "Cholesterol":                      ("cholesterol_mg",  "mg"),
}

FNDDS_ALIASES = {"Total Sugars, Total": "Total Sugars", "Vitamin D": "Vitamin D (D2 + D3)"}

KJ_KCAL = 4.184


def _detect_yield_factor(
    true_fractions: dict[str, float],
    ing_nutrients: dict[str, dict[str, float]],
    label_energy: float,
) -> float:
    """Detect raw→cooked mismatch via energy ratio.

    When SR Legacy has raw ingredient profiles but the FNDDS final product
    is cooked, moisture loss concentrates nutrients.  This estimates a
    yield factor so that the linear model can account for cooking loss.

    Returns 1.0 if no correction is needed (>1.0 means concentration).
    """
    predicted = sum(
        true_fractions[iid] * ing_nutrients[iid]
        for iid in true_fractions
    )
    if predicted <= 0 or label_energy <= 0:
        return 1.0
    ratio = label_energy / predicted
    if ratio > 1.15:  # clearly concentrated (moisture loss)
        return ratio
    return 1.0


def _resolve_name(fndds_name: str) -> str:
    return FNDDS_ALIASES.get(fndds_name, fndds_name)


def _correct_energy(
    amount: float,
    protein_g: float = 0.0,
    carbs_g: float = 0.0,
    fat_g: float = 0.0,
) -> float:
    """Detect kJ→kcal using Atwater 4-4-9 formula.

    Expected kcal = 4*protein + 4*carbs + 9*fat.
    If reported ≈ 4.184× expected, it's kJ → divide by 4.184.
    """
    expected = 4.0 * protein_g + 4.0 * carbs_g + 9.0 * fat_g
    if expected <= 0:
        return amount
    ratio = amount / expected
    # kJ values are ~4.184× expected; real kcal are ~1.0×
    if ratio > 3.0:  # Clearly kJ — at least 3× expected kcal
        return amount / KJ_KCAL
    return amount


def _write_export_failure(
    fdc_id: int,
    recipe: dict[str, Any],
    output_dir: Path,
    failure_category: str,
    warnings: list[str],
    fortificants,
    skipped_nutrients: list[dict[str, Any]],
) -> Path:
    """Write a reproducible export failure artifact."""
    path = output_dir / f"recipe_{fdc_id}_export_failure.json"
    payload = {
        "fdc_id": fdc_id,
        "description": recipe["description"],
        "status": "export_failed",
        "failure_category": failure_category,
        "warnings": warnings,
        "fortification": fortification_diagnostics(
            fortificants,
            skipped_nutrients,
            failure_category=failure_category,
        ),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def export_recipe(fdc_id: int, fndds, sr, output_dir: Path) -> dict | None:
    recipe = fndds.get_recipe(fdc_id)
    if recipe is None:
        return None

    warnings: list[str] = []
    skipped_nutrients: list[dict[str, Any]] = []

    # ── Step 1: Ingredients (simulate reading the label) ─────────────────
    all_ings = recipe["ingredients"]
    total_wt = sum(ing.get("weight_g", 0) for ing in all_ings)

    kept = []
    fortificants = []
    for ing in all_ings:
        name = ing["description"]
        wt = ing.get("weight_g", 0)
        code = ing.get("ingredient_code", 0)
        if wt <= 0:
            warnings.append(f"Skip zero-weight: '{name}'")
            continue
        if is_fortificant(code, name):
            fortificant = build_fortification_ingredient(ing, total_wt)
            fortificants.append(fortificant)
            warnings.append(
                "Move fortificant out of ordinary solve ingredients: "
                f"'{name}'"
            )
            continue
        frac = wt / total_wt if total_wt > 0 else 0.0
        kept.append({
            "name": name,
            "code": code,
            "true_frac": frac,
            "is_2pct": frac <= 0.02,
        })

    if len(kept) < 2:
        failure_category = classify_export_failure(
            n_regular_ingredients=len(kept),
            n_fortificants=len(fortificants),
        )
        _write_export_failure(
            fdc_id,
            recipe,
            output_dir,
            failure_category,
            warnings,
            fortificants,
            skipped_nutrients,
        )
        return None

    # FDA order: main ingredients descending by weight, then ≤2% group
    main = sorted([i for i in kept if not i["is_2pct"]], key=lambda x: -x["true_frac"])
    two = sorted([i for i in kept if i["is_2pct"]], key=lambda x: -x["true_frac"])
    ordered = main + two
    for i, ing in enumerate(ordered):
        ing["id"] = f"ing_{i}"

    # ── Step 2: Map ingredient → nutrient profile via 4-level fallback ──
    # L1: FNDDS foodCode (self-lookup) → L2: Foundation Foods → L3: SR Legacy ndb → L4: fuzzy
    # This uses the ingredient_code from FNDDS for precise code-based mapping,
    # which is much more reliable than pure name search for "as ingredient" entries.

    ing_data: dict[str, dict[str, float | None]] = {}
    ing_macros: dict[str, dict[str, float]] = {}  # protein/carbs/fat for kJ detection
    match_info: dict[str, dict] = {}

    for ing in ordered:
        code = ing.get("code", 0)
        name = ing["name"]

        # Use FNDDS mapper: code-based L1→L2→L3, then name-based L4
        # Returns (profile, method, confidence) tuple
        profile, method, confidence = fndds.map_ingredient_to_profile(
            code, name, sr_legacy_db=sr
        )

        if profile is not None and len(profile.nutrients) > 0:
            score = confidence * 100
        else:
            # Last resort: try SR Legacy search directly
            sr_results = sr.search(name)
            if not sr_results:
                warnings.append(
                    f"No match for '{name}' (code={code}): "
                    f"mapper returned method='{method}'"
                )
                return None
            profile, score = sr_results[0]
            method = "sr_legacy_search"

        match_info[ing["id"]] = {
            "query": name,
            "matched": profile.description,
            "score": score,
            "method": method,
        }

        # Index by resolved FNDDS name
        nut_map: dict[str, float] = {}
        macros = {"protein": 0.0, "carbs": 0.0, "fat": 0.0}
        for nr in profile.nutrients:
            rname = _resolve_name(nr.name)
            if rname == "Protein":
                macros["protein"] = nr.amount
            elif rname == "Carbohydrate, by difference":
                macros["carbs"] = nr.amount
            elif rname == "Total lipid (fat)":
                macros["fat"] = nr.amount
            nut_map[rname] = nr.amount
        ing_macros[ing["id"]] = macros

        # Fill missing FDA nutrients as None
        data: dict[str, float | None] = {}
        for fda_name in FDA_LABEL:
            rname = _resolve_name(fda_name)
            data[rname] = nut_map.get(rname)
        ing_data[ing["id"]] = data

    # ── Step 3: Detect yield factor (raw→cooked moisture loss) ──────────
    # Build a temporary energy dict and true fraction dict for detection
    ing_energy: dict[str, float] = {}
    for ing in ordered:
        iid = ing["id"]
        raw_energy = ing_data[iid].get("Energy", 0) or 0.0
        mc = ing_macros[iid]
        ing_energy[iid] = _correct_energy(
            raw_energy,
            protein_g=mc["protein"],
            carbs_g=mc["carbs"],
            fat_g=mc["fat"],
        )

    label_energy = 0.0
    for nr in recipe["final_nutrients"].nutrients:
        if nr.name == "Energy":
            label_energy = nr.amount
            break

    true_fracs = {ing["id"]: ing["true_frac"] for ing in ordered}
    yield_factor = _detect_yield_factor(true_fracs, ing_energy, label_energy)
    if yield_factor > 1.0:
        warnings.append(
            f"Yield factor {yield_factor:.3f} detected: raw→cooked moisture loss"
        )

    # ── Step 4: Final product nutrients → observations ──────────────────
    final_nut_map: dict[str, float] = {}
    for nr in recipe["final_nutrients"].nutrients:
        final_nut_map[_resolve_name(nr.name)] = nr.amount

    # ── Step 4: Select observable nutrients ──────────────────────────────
    fortificant_contributions = aggregate_contributions(fortificants)
    obs_nutrients: list[tuple[str, str, str, float, float]] = []
    # [(fda_name, canonical_id, unit, adjusted_label_value, raw_label_value)]
    for fda_name, (canon_id, unit) in FDA_LABEL.items():
        rname = _resolve_name(fda_name)
        raw_label_val = final_nut_map.get(rname)
        if raw_label_val is None or raw_label_val <= 0:
            continue
        contribution = fortificant_contributions.get(canon_id, 0.0)
        label_val = max(0.0, raw_label_val - contribution)
        if contribution > 0:
            warnings.append(
                f"Adjust '{canon_id}' label by estimated fortificant contribution: "
                f"{raw_label_val:.3f} - {contribution:.3f} = {label_val:.3f}"
            )
        if raw_label_val > 0 and contribution >= raw_label_val * 0.9:
            skipped_nutrients.append({
                "nutrient": canon_id,
                "reason": "explained_by_fortification_contribution",
                "label_value": raw_label_val,
                "estimated_fortificant_contribution": contribution,
                "adjusted_label_value": label_val,
            })
            continue
        if label_val <= 0:
            continue

        # All ingredients must have data
        if any(ing_data[iid].get(rname) is None for iid in [i["id"] for i in ordered]):
            skipped_nutrients.append({
                "nutrient": canon_id,
                "reason": "incomplete_ingredient_profile",
            })
            continue

        # Fortification check: skip if label value can't be explained by
        # natural ingredients. If max_possible from any ingredient < 50% of
        # label value, the nutrient is likely from fortification.
        max_ing_val = max(
            (ing_data[iid].get(rname) or 0) for iid in [i["id"] for i in ordered]
        )
        # Even if one ingredient has it, the max contribution (100% of that
        # ingredient) must be enough to explain the label value.
        if max_ing_val < label_val * 0.5:
            warnings.append(
                f"Skip '{canon_id}': max ingredient value {max_ing_val:.1f} "
                f"< 50% of label {label_val:.1f} (likely fortified)"
            )
            skipped_nutrients.append({
                "nutrient": canon_id,
                "reason": "fortification_dominated",
                "label_value": raw_label_val,
                "adjusted_label_value": label_val,
                "estimated_fortificant_contribution": contribution,
                "max_base_ingredient_value": max_ing_val,
            })
            continue

        obs_nutrients.append((rname, canon_id, unit, label_val, raw_label_val))

    if not obs_nutrients:
        warnings.append("No observable nutrients — all skipped or incomplete")
        failure_category = classify_export_failure(
            n_regular_ingredients=len(kept),
            n_fortificants=len(fortificants),
            no_observable_nutrients=True,
        )
        _write_export_failure(
            fdc_id,
            recipe,
            output_dir,
            failure_category,
            warnings,
            fortificants,
            skipped_nutrients,
        )
        return None

    # ── Step 5: Build YAML ──────────────────────────────────────────────

    # Nutrients list
    yaml_nutrients = [{"id": cid, "unit": u} for (_, cid, u, _, _) in obs_nutrients]

    # Composition values (energy-corrected, yield-adjusted)
    yaml_values = {}
    for ing in ordered:
        iid = ing["id"]
        row = []
        for rname, cid, unit, label_val, raw_label_val in obs_nutrients:
            val = ing_data[iid].get(rname)
            if val is None:
                val = 0.0
            elif rname == "Energy":
                val = _correct_energy(
                    val,
                    protein_g=ing_macros[iid]["protein"],
                    carbs_g=ing_macros[iid]["carbs"],
                    fat_g=ing_macros[iid]["fat"],
                )
            # Apply yield factor for raw→cooked moisture loss
            if yield_factor > 1.0:
                val = val * yield_factor
            row.append(round(val, 4))
        yaml_values[iid] = row

    # Observations with ±10% intervals
    yaml_obs = []
    for rname, cid, unit, label_val, raw_label_val in obs_nutrients:
        source = "fndds_workflow_pm10pct"
        if label_val != raw_label_val:
            source = "fndds_workflow_pm10pct_fortification_adjusted"
        yaml_obs.append({
            "nutrient": cid,
            "unit": unit,
            "interval": [round(label_val * 0.9, 3), round(label_val * 1.1, 3)],
            "source": source,  # FNDDS final product ±10%, optionally adjusted
        })

    doc = {
        "schema_version": "1.0-draft",
        "problem_id": f"fndds_{fdc_id}",
        "basis": {
            "ingredient_mass": "input_fraction",
            "nutrient_amount": "per_100g_finished_product",
        },
        "ingredients": [
            {
                "id": ing["id"],
                "name": ing["name"],
                "declaration_position": i,
                "declaration_group": (
                    "two_percent_or_less" if ing["is_2pct"] else "main"
                ),
            }
            for i, ing in enumerate(ordered)
        ],
        "composition": {
            "source": "inline",
            "nutrients": yaml_nutrients,
            "values": yaml_values,
        },
        "observations": yaml_obs,
        "model": {
            "type": "linear_mixing",
            "config": {
                "yield_factor": round(yield_factor, 4),
            } if yield_factor > 1.0 else {},
        },
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "constraints": [
            {"id": "mass_balance", "type": "mass_balance", "mode": "hard"},
            {
                "id": "declaration_order",
                "type": "ingredient_order",
                "mode": "hard",
                "config": {"groups": ["main"]},
            },
            {
                "id": "two_percent_rule",
                "type": "two_percent",
                "mode": "hard",
                "config": {"source": "declaration_group"},
            },
            {
                "id": "label_fit",
                "type": "nutrient_interval",
                "mode": "soft",
                "weight": 10.0,
            },
        ],
        "solver": {"point": {"backend": "scipy_slsqp"}, "bounds": {"backend": "highs_lp"}},
        "output": {"path": f"output/fndds_{fdc_id}_result.json"},
    }

    yaml_path = output_dir / f"recipe_{fdc_id}.yaml"
    yaml_path.write_text(
        yaml.dump(doc, sort_keys=False, default_flow_style=None, allow_unicode=True),
        encoding="utf-8",
    )

    # Truth
    truth = {
        "fdc_id": fdc_id,
        "description": recipe["description"],
        "ingredients": [
            {
                "id": ing["id"],
                "name": ing["name"],
                "true_fraction": ing["true_frac"],
            }
            for ing in ordered
        ],
        "fortification": fortification_diagnostics(
            fortificants,
            skipped_nutrients,
        ),
        "warnings": warnings,
    }
    truth_path = output_dir / f"recipe_{fdc_id}_truth.json"
    truth_path.write_text(json.dumps(truth, indent=2, ensure_ascii=False), encoding="utf-8")

    return {
        "yaml_path": str(yaml_path), "truth_path": str(truth_path),
        "n_ingredients": len(ordered), "n_observations": len(obs_nutrients),
        "skipped_nutrients": [item["nutrient"] for item in skipped_nutrients],
        "skipped_nutrient_details": skipped_nutrients,
        "fortification": fortification_diagnostics(fortificants, skipped_nutrients),
        "warnings": warnings,
    }


def main():
    from nusol.data.fndds import FNDDSDataAdapter
    from nusol.data.sr_legacy import SRLegacyDataAdapter

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading databases...")
    fndds = FNDDSDataAdapter()
    fndds.load(str(FNDDS_PATH))
    sr = SRLegacyDataAdapter()
    sr.load(str(SR_PATH))
    print(f"  FNDDS: {len(fndds)} foods, SR Legacy: {len(sr)} foods\n")

    test_ids = [2705394, 2705384, 2705412]

    for fdc_id in test_ids:
        recipe = fndds.get_recipe(fdc_id)
        print(f"FDC {fdc_id} — {recipe['description']}")
        result = export_recipe(fdc_id, fndds, sr, OUTPUT_DIR)
        if result:
            print(
                f"  Ingredients: {result['n_ingredients']}, "
                f"Observations: {result['n_observations']}"
            )
            if result["skipped_nutrients"]:
                print(f"  Skipped: {result['skipped_nutrients']}")
            for w in result["warnings"]:
                print(f"  ⚠ {w}")
            print(f"  → {Path(result['yaml_path']).name}")
        else:
            print("  FAILED")
        print()


if __name__ == "__main__":
    main()
