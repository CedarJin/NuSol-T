#!/usr/bin/env python3
"""run_fndds_benchmark.py — Batch solve all 197 usable FNDDS validation recipes.

Usage::
    uv run python scripts/run_fndds_benchmark.py
    uv run python scripts/run_fndds_benchmark.py --limit 10   # test with 10 recipes
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from nusol.data.fndds import FNDDSDataAdapter
from nusol.data.sr_legacy import SRLegacyDataAdapter
from nusol.api import solve
from scripts.export_fndds_recipes import export_recipe

FNDDS_PATH = (
    PROJECT_ROOT / ".." / "db"
    / "FoodData_Central_survey_food_json_2024-10-31" / "surveyDownload.json"
)
SR_PATH = (
    PROJECT_ROOT / ".." / "db"
    / "FoodData_Central_sr_legacy_food_json_2018-04"
    / "FoodData_Central_sr_legacy_food_json_2018-04.json"
)
VALIDATION_PATH = PROJECT_ROOT / "config" / "validation_recipes.json"
OUTPUT_DIR = PROJECT_ROOT / "output" / "fndds_benchmark"
SUMMARY_PATH = OUTPUT_DIR / "benchmark_summary.json"

NFS_RE = re.compile(r'\bNFS\b', re.IGNORECASE)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Limit number of recipes (0=all)")
    parser.add_argument("--skip-export", action="store_true", help="Skip export, solve existing YAMLs")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load databases
    print("Loading databases...")
    fndds = FNDDSDataAdapter(); fndds.load(str(FNDDS_PATH))
    sr = SRLegacyDataAdapter(); sr.load(str(SR_PATH))
    print(f"  FNDDS: {len(fndds)} foods, SR Legacy: {len(sr)} foods")

    # Load validation IDs
    with open(VALIDATION_PATH) as f:
        val_ids = json.load(f)["fdc_ids"]
    print(f"  Validation set: {len(val_ids)} recipe IDs")

    # Filter: multi-ingredient (2+), non-NFS
    usable = []
    skipped_nfs = []
    for fdc_id in val_ids:
        recipe = fndds.get_recipe(fdc_id)
        if recipe is None:
            continue
        n_ing = len(recipe.get("ingredients", []))
        if n_ing < 2:
            continue
        if NFS_RE.search(recipe.get("description", "")):
            skipped_nfs.append(fdc_id)
            continue
        usable.append(fdc_id)

    print(f"  NFS skipped: {len(skipped_nfs)}")
    print(f"  Usable: {len(usable)}")

    if args.limit:
        usable = usable[:args.limit]
        print(f"  Limited to: {len(usable)}")

    # Export + Solve
    results = []
    n_success, n_export_fail, n_solve_fail = 0, 0, 0
    mae_list = []

    t0 = time.perf_counter()
    for i, fdc_id in enumerate(usable):
        recipe = fndds.get_recipe(fdc_id)
        desc = recipe["description"] if recipe else "?"
        print(f"\n[{i+1}/{len(usable)}] FDC {fdc_id} — {desc[:60]}")

        # Export YAML
        if not args.skip_export:
            export_result = export_recipe(fdc_id, fndds, sr, OUTPUT_DIR)
            if export_result is None:
                print(f"  EXPORT FAILED")
                n_export_fail += 1
                results.append({"fdc_id": fdc_id, "description": desc, "status": "export_failed"})
                continue
            yaml_path = Path(export_result["yaml_path"])
            truth_path = Path(export_result["truth_path"])
            warnings = export_result.get("warnings", [])
            n_obs = export_result["n_observations"]
            n_ing = export_result["n_ingredients"]
            skipped = export_result.get("skipped_nutrients", [])
        else:
            yaml_path = OUTPUT_DIR / f"recipe_{fdc_id}.yaml"
            truth_path = OUTPUT_DIR / f"recipe_{fdc_id}_truth.json"
            if not yaml_path.exists():
                n_export_fail += 1
                continue
            n_ing = "?"
            n_obs = "?"
            warnings = []
            skipped = []

        # Solve
        try:
            result = solve(str(yaml_path))
        except Exception as e:
            print(f"  SOLVE ERROR: {e}")
            n_solve_fail += 1
            results.append({
                "fdc_id": fdc_id, "description": desc,
                "status": "solve_error", "error": str(e),
                "n_ingredients": n_ing, "n_observations": n_obs,
            })
            continue

        if not result["success"]:
            print(f"  SOLVE FAILED: {result.get('error', 'unknown')}")
            n_solve_fail += 1
            results.append({
                "fdc_id": fdc_id, "description": desc,
                "status": "solve_failed", "error": result.get("error"),
                "n_ingredients": n_ing, "n_observations": n_obs,
            })
            continue

        # Compute MAE vs ground truth
        fractions = result["fractions"]
        with open(truth_path) as f:
            truth = json.load(f)

        errors = []
        ing_details = []
        for ing in truth["ingredients"]:
            iid = ing["id"]
            t = ing["true_fraction"]
            s = fractions.get(iid, 0.0)
            e = abs(t - s)
            errors.append(e)
            ing_details.append({"id": iid, "name": ing["name"], "true": round(t, 6), "solved": round(s, 6), "error": round(e, 6)})

        mae = sum(errors) / len(errors) if errors else 0
        mae_list.append(mae)
        n_success += 1
        objective = result["diagnostics"]["point"].get("objective_value", None)

        print(f"  OK — MAE={mae:.4f} ({mae*100:.2f}pp) | obj={objective:.2e} | {n_ing}ingr × {n_obs}obs")

        results.append({
            "fdc_id": fdc_id,
            "description": desc,
            "status": "success",
            "mae": round(mae, 6),
            "mae_pp": round(mae * 100, 4),
            "objective_value": objective,
            "n_ingredients": n_ing,
            "n_observations": n_obs,
            "warnings": warnings,
            "skipped_nutrients": skipped,
            "ingredients": ing_details,
            "solve_time_s": result["diagnostics"]["total_time_s"],
        })

    t_total = time.perf_counter() - t0

    # Summary
    summary = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "total_in_validation_set": len(val_ids),
        "nfs_skipped": len(skipped_nfs),
        "attempted": len(usable),
        "export_failed": n_export_fail,
        "solve_failed": n_solve_fail,
        "success": n_success,
        "success_rate": round(n_success / len(usable), 4) if usable else 0,
        "mae_stats": {
            "mean": round(sum(mae_list) / len(mae_list), 6) if mae_list else None,
            "median": round(sorted(mae_list)[len(mae_list)//2], 6) if mae_list else None,
            "min": round(min(mae_list), 6) if mae_list else None,
            "max": round(max(mae_list), 6) if mae_list else None,
        } if mae_list else {},
        "total_time_s": round(t_total, 1),
        "results": results,
    }

    with open(SUMMARY_PATH, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Print final summary
    print(f"\n{'='*60}")
    print(f"BENCHMARK COMPLETE")
    print(f"  Attempted: {len(usable)}")
    print(f"  Export failed: {n_export_fail}")
    print(f"  Solve failed: {n_solve_fail}")
    print(f"  Success: {n_success} ({n_success/len(usable)*100:.1f}%)" if usable else "  Success: 0")
    if mae_list:
        print(f"  MAE mean:   {sum(mae_list)/len(mae_list):.4f} ({sum(mae_list)/len(mae_list)*100:.2f} pp)")
        print(f"  MAE median: {sorted(mae_list)[len(mae_list)//2]:.4f}")
        print(f"  MAE range:  [{min(mae_list):.4f}, {max(mae_list):.4f}]")
    print(f"  Total time: {t_total:.1f}s")
    print(f"  Summary → {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
