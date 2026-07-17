#!/usr/bin/env python3
"""run_afcd_benchmark.py — Run NuSol-T on Australia AFCD recipes.

Usage::
    uv run python scripts/run_afcd_benchmark.py
"""

from __future__ import annotations

import json, sys, time, yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from nusol.api import solve
from nusol.data.afcd import AFCDAdapter, AFCD_NUTRIENTS

DB = Path('/Users/jinyanshan/2026-ysjin-NuSol-T/db')
AFCD_DIR = DB / 'Australia Food Composition Database'
OUTPUT_DIR = PROJECT_ROOT / "output" / "afcd"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

KJ_KCAL = 4.184


def export_afcd_recipe(food_key: str, afcd: AFCDAdapter, output_dir: Path) -> dict | None:
    """Convert AFCD recipe to NuSol YAML."""
    recipe = afcd.get_recipe(food_key)
    if recipe is None:
        return None

    ingredients = recipe["ingredients"]
    if len(ingredients) < 2:
        return None

    total_wt = sum(i["weight_g"] for i in ingredients)
    yf = recipe.get("yield_factor", 1.0)

    # Filter: skip ingredients without nutrient data
    kept = []
    for ing in ingredients:
        nuts = afcd.get_ingredient_nutrients(ing["ingredient_code"])
        if not nuts:
            continue
        frac = float(ing["weight_g"]) / float(total_wt)
        is_2pct = frac <= 0.02
        kept.append({
            "id": f"ing_{len(kept)}",
            "name": ing["description"],
            "weight_g": float(ing["weight_g"]),
            "true_frac": frac,
            "is_2pct": is_2pct,
            "nutrients": nuts,
        })

    if len(kept) < 2:
        return None

    # Order: main descending, then ≤2%
    main = sorted([i for i in kept if not i["is_2pct"]], key=lambda x: -x["true_frac"])
    two = sorted([i for i in kept if i["is_2pct"]], key=lambda x: -x["true_frac"])
    ordered = main + two

    # Determine observable nutrients (present in all ingredients + final product)
    final_nuts = recipe["final_nutrients"]
    nut_list = [
        ("energy_kcal", "kcal"),
        ("protein_g", "g"), ("fat_g", "g"), ("carbohydrate_g", "g"),
        ("fiber_g", "g"), ("sugars_g", "g"), ("saturated_fat_g", "g"),
        ("sodium_mg", "mg"), ("calcium_mg", "mg"), ("iron_mg", "mg"),
        ("potassium_mg", "mg"), ("vitamin_d_mcg", "mcg"), ("cholesterol_mg", "mg"),
    ]

    obs_nutrients = []
    for canon_id, unit in nut_list:
        label_val = final_nuts.get(canon_id)
        if label_val is None or float(label_val) <= 0:
            continue
        if not all(canon_id in ing["nutrients"] for ing in ordered):
            continue
        obs_nutrients.append((canon_id, unit, float(label_val)))

    if not obs_nutrients:
        return None

    # Build YAML
    yaml_ingredients = [
        {"id": ing["id"], "name": ing["name"],
         "declaration_position": i,
         "declaration_group": "two_percent_or_less" if ing["is_2pct"] else "main"}
        for i, ing in enumerate(ordered)
    ]
    yaml_nutrients = [{"id": cid, "unit": u} for cid, u, _ in obs_nutrients]
    _yf = float(yf) if yf != 1.0 else 1.0
    yaml_values = {
        ing["id"]: [round(float(ing["nutrients"].get(cid, 0)) * _yf, 4)
                     for cid, _, _ in obs_nutrients]
        for ing in ordered
    }
    yaml_obs = [
        {"nutrient": cid, "unit": u,
         "interval": [round(float(lv) * 0.9, 3), round(float(lv) * 1.1, 3)],
         "source": "afcd_workflow_pm10pct"}
        for cid, u, lv in obs_nutrients
    ]

    doc = {
        "schema_version": "1.0-draft",
        "problem_id": f"afcd_{food_key}",
        "basis": {"ingredient_mass": "input_fraction", "nutrient_amount": "per_100g_finished_product"},
        "ingredients": yaml_ingredients,
        "composition": {"source": "inline", "nutrients": yaml_nutrients, "values": yaml_values},
        "observations": yaml_obs,
        "model": {"type": "linear_mixing", "config": {"yield_factor": round(yf, 4)} if yf != 1.0 else {}},
        "variables": {"ingredient_fractions": {"lower": 0.0, "upper": 1.0}},
        "constraints": [
            {"id": "mass_balance", "type": "mass_balance", "mode": "hard"},
            {"id": "declaration_order", "type": "ingredient_order", "mode": "hard",
             "config": {"groups": ["main"]}},
            {"id": "two_percent_rule", "type": "two_percent", "mode": "hard",
             "config": {"source": "declaration_group"}},
            {"id": "label_fit", "type": "nutrient_interval", "mode": "soft", "weight": 10.0},
        ],
        "solver": {"point": {"backend": "scipy_slsqp"}},
        "output": {"path": f"output/afcd_{food_key}.json"},
    }

    yaml_path = output_dir / f"recipe_{food_key}.yaml"
    with open(yaml_path, "w") as f:
        # Use json roundtrip to strip numpy scalars, then dump as YAML
        clean = json.loads(json.dumps(doc, default=float))
        yaml.safe_dump(clean, f, sort_keys=False, default_flow_style=None, allow_unicode=True)

    # Truth
    truth = {
        "food_key": food_key,
        "description": recipe["description"],
        "yield_factor": yf,
        "ingredients": [{"id": ing["id"], "name": ing["name"], "true_fraction": ing["true_frac"]}
                        for ing in ordered],
    }
    truth_path = output_dir / f"recipe_{food_key}_truth.json"
    with open(truth_path, "w") as f:
        json.dump(truth, f, indent=2)

    return {"yaml_path": str(yaml_path), "n_ing": len(ordered), "n_obs": len(obs_nutrients)}


def main():
    afcd = AFCDAdapter()
    afcd.load(str(AFCD_DIR))

    multi_ids = afcd.get_recipes_with_ingredients(min_ingredients=2)
    print(f"AFCD: {len(multi_ids)} multi-ingredient recipes\n")

    n_ok, n_export, n_solve = 0, 0, 0
    mae_list = []
    t0 = time.perf_counter()

    for i, fid in enumerate(multi_ids):
        r = export_afcd_recipe(fid, afcd, OUTPUT_DIR)
        if r is None:
            n_export += 1
            continue

        yaml_path = r["yaml_path"]
        with open(yaml_path) as f:
            doc = yaml.safe_load(f)
        doc["solver"]["point"] = {"backend": "scipy_slsqp", "options": {"max_iterations": 2000, "tolerance": 1e-6}}

        # Try solve; fallback to w=1.0
        result = None
        for w in [10.0, 1.0]:
            for c in doc.get("constraints", []):
                if c.get("type") == "nutrient_interval":
                    c["weight"] = w
            tmp = OUTPUT_DIR / f"_tmp_{fid}.yaml"
            with open(tmp, "w") as f:
                yaml.safe_dump(doc, f, sort_keys=False, allow_unicode=True)
            try:
                result = solve(str(tmp))
                if result["success"]:
                    break
            except Exception:
                pass
            finally:
                tmp.unlink(missing_ok=True)

        if result and result["success"]:
            n_ok += 1
            truth_path = OUTPUT_DIR / f"recipe_{fid}_truth.json"
            with open(truth_path) as f:
                truth = json.load(f)
            errors = [abs(i["true_fraction"] - result["fractions"].get(i["id"], 0))
                      for i in truth["ingredients"]]
            mae_list.append(sum(errors) / len(errors))
            recipe = afcd.get_recipe(fid)
            desc = recipe["description"][:50] if recipe else "?"
            if (i+1) % 50 == 0:
                print(f"  [{i+1}/{len(multi_ids)}] {n_ok} ok, {n_export} exp, {n_solve} sol")
        else:
            n_solve += 1

    elapsed = time.perf_counter() - t0
    mae_s = sorted(mae_list)
    summary = {
        "dataset": "AFCD Release 3",
        "usable": len(multi_ids),
        "export_failed": n_export,
        "solve_failed": n_solve,
        "success": n_ok,
        "success_rate": round(n_ok/len(multi_ids)*100, 2),
        "mae_mean_pp": round(sum(mae_list)/len(mae_list)*100, 2) if mae_list else None,
        "mae_median_pp": round(mae_s[len(mae_s)//2]*100, 2) if mae_list else None,
        "time_s": round(elapsed, 1),
    }
    with open(OUTPUT_DIR / "benchmark_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nAFCD: {n_ok}/{len(multi_ids)} ({n_ok/len(multi_ids)*100:.1f}%), "
          f"MAE median={summary['mae_median_pp']:.1f}pp, "
          f"mean={summary['mae_mean_pp']:.1f}pp, {elapsed:.0f}s")


if __name__ == "__main__":
    main()
