#!/usr/bin/env python3
"""retry_failures.py — Manually handle FNDDS benchmark failures.

Export failures: filter fortificants, use only real food ingredients.
Solve failures: adjust solver config for better convergence.

Usage::
    uv run python scripts/retry_failures.py
"""

from __future__ import annotations

import json, re, sys, time, yaml
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from nusol.data.fndds import FNDDSDataAdapter
from nusol.data.sr_legacy import SRLegacyDataAdapter
from nusol.api import solve

FNDDS_PATH = PROJECT_ROOT / ".." / "db" / "FoodData_Central_survey_food_json_2024-10-31" / "surveyDownload.json"
SR_PATH = PROJECT_ROOT / ".." / "db" / "FoodData_Central_sr_legacy_food_json_2018-04" / "FoodData_Central_sr_legacy_food_json_2018-04.json"
OUTPUT_DIR = PROJECT_ROOT / "output" / "fndds_benchmark"
RETRY_DIR = OUTPUT_DIR / "retry"
RETRY_DIR.mkdir(parents=True, exist_ok=True)

# Fortificant codes — no nutrient data available
FORT_CODES = {"999328", "999301", "999303", "999401", "999431", "999418", "999001", "999291"}

# FNDDS codes for ingredients that need manual SR Legacy lookup
CODE_TO_SR_LOOKUP = {
    # These codes are in FNDDS but might not resolve through standard mapper
    "2047": "Salt, table",
    "8120": "Cereals, oats, regular and quick, not fortified, dry",
    "4582": "Oil, canola",
    "19335": "Sugars, granulated",
    "20481": "Flour, wheat, all-purpose, unenriched, unbleached",
    "20422": "Cornmeal, degermed, unenriched, yellow",
    "20061": "Flour, rice, white, unenriched",
    "16122": "Soy protein isolate",
    "19165": "Cocoa, dry powder, unsweetened",
    "9298": "Raisins, dark, seedless",
    "16398": "Peanut butter, smooth style, without salt",
    "43483": "Millet, puffed",
    "1116": "Yogurt, plain, whole milk",
    "1117": "Yogurt, plain, low fat",
    "100295": "Yogurt, plain, nonfat",
    "61210220": "Orange juice, 100%, canned, bottled or in a carton",
    "9040": "Bananas, ripe and slightly ripe, raw",
    "100254": "Bananas, overripe, raw",
    "11529": "Tomatoes, red, ripe, raw, year round average",
    "100261": "Tomato, roma",
    "100147": "Tomatoes, grape, raw",
    "100255": "Onions, white, raw",
    "100253": "Onions, yellow, raw",
    "100252": "Onions, red, raw",
    "99998210": "Oil, industrial, as ingredient in food",
}

FDA_LABEL: dict[str, tuple[str, str]] = {
    "Energy": ("energy_kcal", "kcal"),
    "Protein": ("protein_g", "g"),
    "Total lipid (fat)": ("fat_g", "g"),
    "Carbohydrate, by difference": ("carbohydrate_g", "g"),
    "Fiber, total dietary": ("fiber_g", "g"),
    "Total Sugars": ("sugars_g", "g"),
    "Fatty acids, total saturated": ("saturated_fat_g", "g"),
    "Sodium, Na": ("sodium_mg", "mg"),
    "Calcium, Ca": ("calcium_mg", "mg"),
    "Iron, Fe": ("iron_mg", "mg"),
    "Potassium, K": ("potassium_mg", "mg"),
    "Vitamin D (D2 + D3)": ("vitamin_d_mcg", "mcg"),
    "Cholesterol": ("cholesterol_mg", "mg"),
}
FNDDS_ALIASES = {"Total Sugars, Total": "Total Sugars", "Vitamin D": "Vitamin D (D2 + D3)"}

KJ_KCAL = 4.184


def _resolve_name(n: str) -> str:
    return FNDDS_ALIASES.get(n, n)


def _correct_energy(amount, protein=0, carbs=0, fat=0):
    expected = 4*protein + 4*carbs + 9*fat
    if expected > 0 and amount / expected > 3.0:
        return amount / KJ_KCAL
    return amount


def build_manual_yaml(fdc_id: int, fndds, sr, output_path: Path) -> dict | None:
    """Manually build YAML for a recipe that failed auto-export."""
    recipe = fndds.get_recipe(fdc_id)
    if recipe is None:
        return None

    all_ings = recipe["ingredients"]
    total_wt = sum(ing.get("weight_g", 0) for ing in all_ings)

    # Filter: remove fortificants, keep real ingredients
    kept = []
    for ing in all_ings:
        code = str(ing.get("ingredient_code", ""))
        name = ing["description"]
        wt = ing.get("weight_g", 0)
        if wt <= 0:
            continue
        if code in FORT_CODES:
            continue  # skip fortificant
        kept.append({"name": name, "code": code, "wt": wt})

    if len(kept) < 2:
        return None  # can't solve with <2 ingredients

    # Recompute fractions
    kept_total = sum(i["wt"] for i in kept)
    for i in kept:
        i["true_frac"] = i["wt"] / kept_total
        i["is_2pct"] = i["true_frac"] <= 0.02

    # Order: main descending, then 2% group
    main = sorted([i for i in kept if not i["is_2pct"]], key=lambda x: -x["true_frac"])
    two = sorted([i for i in kept if i["is_2pct"]], key=lambda x: -x["true_frac"])
    ordered = main + two
    for i, ing in enumerate(ordered):
        ing["id"] = f"ing_{i}"

    # Lookup nutrients via SR Legacy search
    ing_data = {}
    ing_macros = {}
    for ing in ordered:
        # Try by code first, then by name
        profile = None
        code = ing.get("code", "")
        # Try code-based lookup via FNDDS mapper
        profile, method, conf = fndds.map_ingredient_to_profile(
            int(code) if code.isdigit() else 0, ing["name"], sr_legacy_db=sr
        )
        if profile is None or len(profile.nutrients) == 0:
            results = sr.search(ing["name"])
            if not results:
                return None  # still can't map
            profile, score = results[0]

        nut_map = {}
        macros = {"protein": 0.0, "carbs": 0.0, "fat": 0.0}
        for nr in profile.nutrients:
            rname = _resolve_name(nr.name)
            if rname == "Protein": macros["protein"] = nr.amount
            elif rname == "Carbohydrate, by difference": macros["carbs"] = nr.amount
            elif rname == "Total lipid (fat)": macros["fat"] = nr.amount
            nut_map[rname] = nr.amount
        ing_macros[ing["id"]] = macros

        data = {}
        for fda_name in FDA_LABEL:
            data[_resolve_name(fda_name)] = nut_map.get(_resolve_name(fda_name))
        ing_data[ing["id"]] = data

    # Final product nutrients
    final_nut_map = {}
    for nr in recipe["final_nutrients"].nutrients:
        final_nut_map[_resolve_name(nr.name)] = nr.amount

    # Select observable nutrients
    obs_nutrients = []
    for fda_name, (canon_id, unit) in FDA_LABEL.items():
        rname = _resolve_name(fda_name)
        label_val = final_nut_map.get(rname)
        if label_val is None or label_val <= 0:
            continue
        if any(ing_data[iid].get(rname) is None for iid in [i["id"] for i in ordered]):
            continue
        obs_nutrients.append((rname, canon_id, unit))

    if not obs_nutrients:
        return None

    # Build YAML
    yaml_nutrients = [{"id": cid, "unit": u} for (_, cid, u) in obs_nutrients]
    yaml_values = {}
    for ing in ordered:
        row = []
        for rname, cid, unit in obs_nutrients:
            val = ing_data[ing["id"]].get(rname) or 0.0
            if rname == "Energy":
                val = _correct_energy(val, **ing_macros[ing["id"]])
            row.append(round(val, 4))
        yaml_values[ing["id"]] = row

    yaml_obs = []
    for rname, cid, unit in obs_nutrients:
        label_val = final_nut_map[rname]
        yaml_obs.append({
            "nutrient": cid, "unit": unit,
            "interval": [round(label_val * 0.9, 3), round(label_val * 1.1, 3)],
            "source": "fndds_workflow_pm10pct",
        })

    doc = {
        "schema_version": "1.0-draft",
        "problem_id": f"retry_{fdc_id}",
        "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
        "ingredients": [
            {"id": ing["id"], "name": ing["name"],
             "declaration_position": i,
             "declaration_group": "two_percent_or_less" if ing["is_2pct"] else "main"}
            for i, ing in enumerate(ordered)
        ],
        "composition": {"source": "inline", "nutrients": yaml_nutrients, "values": yaml_values},
        "observations": yaml_obs,
        "model": {"type": "linear_mixing"},
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "constraints": [
            {"id": "mass_balance", "type": "mass_balance", "mode": "hard"},
            {"id": "declaration_order", "type": "ingredient_order", "mode": "hard",
             "config": {"groups": ["main"]}},
            {"id": "two_percent_rule", "type": "two_percent", "mode": "hard",
             "config": {"source": "declaration_group"}},
            {"id": "label_fit", "type": "nutrient_interval", "mode": "soft", "weight": 10.0},
        ],
        "solver": {
            "point": {"backend": "scipy_slsqp", "options": {"max_iterations": 1000, "tolerance": 1e-6}},
            "bounds": {"backend": "highs_lp"},
        },
        "output": {"path": f"output/retry_{fdc_id}.json"},
    }

    with open(output_path, "w") as f:
        yaml.dump(doc, f, sort_keys=False, default_flow_style=None, allow_unicode=True)

    # Truth
    truth = {
        "fdc_id": fdc_id, "description": recipe["description"],
        "ingredients": [{"id": ing["id"], "name": ing["name"], "true_fraction": ing["true_frac"]}
                        for ing in ordered],
    }
    truth_path = output_path.with_suffix(".truth.json")
    with open(truth_path, "w") as f:
        json.dump(truth, f, indent=2)

    return {"n_ing": len(ordered), "n_obs": len(obs_nutrients)}


def main():
    fndds = FNDDSDataAdapter(); fndds.load(str(FNDDS_PATH))
    sr = SRLegacyDataAdapter(); sr.load(str(SR_PATH))

    # ── EXPORT FAILURES ──
    print("=" * 60)
    print("FIXING EXPORT FAILURES")
    print("=" * 60)

    # Get IDs without YAML files
    all_yaml_ids = set(int(p.stem.replace("recipe_", ""))
                       for p in OUTPUT_DIR.glob("recipe_*.yaml"))
    nfs_re = re.compile(r'\bNFS\b', re.IGNORECASE)
    all_multi = [f['fdcId'] for f in
                 [fndds._data[fid] for fid in fndds._data
                  if len(fndds._data[fid].get('inputFoods', [])) >= 2
                  and not nfs_re.search(fndds._data[fid].get('description', ''))]]
    export_fail_ids = sorted(fid for fid in all_multi if fid not in all_yaml_ids)

    export_results = []
    for fid in export_fail_ids:
        recipe = fndds.get_recipe(fid)
        desc = recipe["description"] if recipe else "?"
        yaml_path = RETRY_DIR / f"manual_{fid}.yaml"
        result = build_manual_yaml(fid, fndds, sr, yaml_path)
        if result:
            try:
                r = solve(str(yaml_path))
                if r["success"]:
                    truth_path = yaml_path.with_suffix(".truth.json")
                    with open(truth_path) as f:
                        truth = json.load(f)
                    mae = sum(abs(i["true_fraction"] - r["fractions"].get(i["id"], 0))
                              for i in truth["ingredients"]) / len(truth["ingredients"])
                    print(f"  FDC {fid}: FIXED — MAE={mae*100:.1f}pp | {result['n_ing']}ingr × {result['n_obs']}obs — {desc[:50]}")
                    export_results.append({"fdc_id": fid, "status": "fixed", "mae_pp": round(mae*100, 2)})
                else:
                    print(f"  FDC {fid}: STILL FAILED — {r.get('error', '?')[:50]}")
                    export_results.append({"fdc_id": fid, "status": "still_failed", "error": r.get("error")})
            except Exception as e:
                print(f"  FDC {fid}: ERROR — {e}")
                export_results.append({"fdc_id": fid, "status": "error", "error": str(e)})
        else:
            print(f"  FDC {fid}: CANNOT FIX — {desc[:50]}")
            export_results.append({"fdc_id": fid, "status": "cannot_fix"})

    # ── SOLVE FAILURES ──
    print("\n" + "=" * 60)
    print("FIXING SOLVE FAILURES")
    print("=" * 60)

    with open(OUTPUT_DIR / "benchmark_full.json") as f:
        bench = json.load(f)
    solve_fail_ids = [r["fdc_id"] for r in bench["results"] if r["status"] == "solve_failed"]
    # Only do first 50 to keep time reasonable
    solve_fail_ids = solve_fail_ids[:50]
    print(f"Attempting {len(solve_fail_ids)} solve failures (out of 159 total)...")

    solve_results = []
    for fid in solve_fail_ids:
        # Find existing YAML
        yaml_path = OUTPUT_DIR / f"recipe_{fid}.yaml"
        if not yaml_path.exists():
            # Try export
            from scripts.export_fndds_recipes import export_recipe
            result = export_recipe(fid, fndds, sr, OUTPUT_DIR)
            if result is None:
                print(f"  FDC {fid}: CANNOT EXPORT")
                solve_results.append({"fdc_id": fid, "status": "cannot_export"})
                continue
            yaml_path = Path(result["yaml_path"])

        with open(yaml_path) as f:
            doc = yaml.safe_load(f)

        recipe = fndds.get_recipe(fid)
        desc = recipe["description"] if recipe else "?"

        # Strategy: try multiple solver configs
        configs = [
            # 1. Increased iterations
            {"point": {"backend": "scipy_slsqp", "options": {"max_iterations": 2000, "tolerance": 1e-6}}},
            # 2. Lower soft weight
            {"point": {"backend": "scipy_slsqp", "options": {"max_iterations": 1000, "tolerance": 1e-6}}},
        ]
        # Lower weight variant
        doc_low = yaml.safe_load(yaml_path.read_text())
        for c in doc_low.get("constraints", []):
            if c.get("type") == "nutrient_interval":
                c["weight"] = 1.0

        fixed = False
        for i, solver_cfg in enumerate(configs):
            doc_try = yaml.safe_load(yaml_path.read_text())
            doc_try["solver"] = solver_cfg
            tmp = RETRY_DIR / f"solve_retry_{fid}_v{i}.yaml"
            with open(tmp, "w") as f:
                yaml.dump(doc_try, f, sort_keys=False, allow_unicode=True)
            try:
                r = solve(str(tmp))
                if r["success"]:
                    truth_path = OUTPUT_DIR / f"recipe_{fid}_truth.json"
                    if truth_path.exists():
                        with open(truth_path) as f:
                            truth = json.load(f)
                        mae = sum(abs(i["true_fraction"] - r["fractions"].get(i["id"], 0))
                                  for i in truth["ingredients"]) / len(truth["ingredients"])
                        print(f"  FDC {fid}: FIXED (cfg{i}) — MAE={mae*100:.1f}pp — {desc[:50]}")
                        solve_results.append({"fdc_id": fid, "status": "fixed", "mae_pp": round(mae*100, 2), "config": i})
                    else:
                        print(f"  FDC {fid}: FIXED (cfg{i}) — no truth data — {desc[:50]}")
                        solve_results.append({"fdc_id": fid, "status": "fixed", "config": i})
                    fixed = True
                    break
            except Exception:
                pass
            finally:
                tmp.unlink(missing_ok=True)

        if not fixed:
            print(f"  FDC {fid}: STILL FAILED — {desc[:50]}")
            solve_results.append({"fdc_id": fid, "status": "still_failed"})

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    exp_fixed = sum(1 for r in export_results if r["status"] == "fixed")
    exp_still = sum(1 for r in export_results if r["status"] != "fixed")
    sol_fixed = sum(1 for r in solve_results if r["status"] == "fixed")
    sol_still = sum(1 for r in solve_results if r["status"] != "fixed")
    print(f"Export failures: {exp_fixed} fixed, {exp_still} still failed (of {len(export_fail_ids)})")
    print(f"Solve failures:  {sol_fixed} fixed, {sol_still} still failed (of {len(solve_fail_ids)} sampled)")

    if exp_fixed > 0:
        mae_list = [r["mae_pp"] for r in export_results if "mae_pp" in r]
        if mae_list:
            print(f"Export fix MAE: mean={sum(mae_list)/len(mae_list):.1f}pp, median={sorted(mae_list)[len(mae_list)//2]:.1f}pp")
    if sol_fixed > 0:
        mae_list = [r["mae_pp"] for r in solve_results if "mae_pp" in r]
        if mae_list:
            print(f"Solve fix MAE:  mean={sum(mae_list)/len(mae_list):.1f}pp, median={sorted(mae_list)[len(mae_list)//2]:.1f}pp")


if __name__ == "__main__":
    main()
