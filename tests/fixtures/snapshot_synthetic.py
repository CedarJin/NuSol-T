"""Generate expected solver outputs for synthetic fixtures (Phase 0 baseline)."""
import json
import sys
from pathlib import Path

import numpy as np

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from nusol.solver.qp_solver import QPSolver
from nusol.solver.bound_solver import BoundSolver


def load_fixture(path: Path) -> dict:
    with open(path) as f:
        data = json.load(f)
    return data


def fixture_to_context(fixture: dict) -> dict:
    return {
        "nutrient_matrix": np.array(fixture["nutrient_matrix"], dtype=float),
        "nutrient_names": fixture["nutrient_names"],
        "target_intervals": fixture["target_intervals"],
        "main_ingredient_indices": fixture.get("main_ingredient_indices",
                                                list(range(len(fixture["variables"])))),
    }


def run_and_save(fixture_path: Path, output_dir: Path) -> None:
    fixture = load_fixture(fixture_path)
    variables = fixture["variables"]
    context = fixture_to_context(fixture)

    meta = fixture["_meta"]
    name = meta["name"]
    print(f"  {name}...")

    expected = output_dir / f"{name}_expected.json"
    existing = {}
    if expected.exists():
        with open(expected) as f:
            existing = json.load(f)

    # Run QPSolver
    qp = QPSolver()
    qp_result = qp.solve(variables, constraints=[], context=context)
    print(f"    QP: success={qp_result.success}, "
          f"x={ {k: round(v, 4) for k, v in qp_result.x_point.items()} }")

    # Run BoundSolver
    bs = BoundSolver()
    bs_result = bs.solve(variables, constraints=[], context=context)
    print(f"    Bound: success={bs_result.success}")
    if bs_result.x_lower:
        widths = {k: round(bs_result.x_upper.get(k, 1) - v, 4)
                  for k, v in bs_result.x_lower.items()}
        print(f"    widths={widths}")

    snapshot = {
        "_meta": {
            "fixture": name,
            "fixture_type": meta["type"],
            "generated_by": "snapshot_synthetic.py",
        },
        "qp": {
            "success": qp_result.success,
            "message": qp_result.message,
            "x_point": {k: round(v, 6) for k, v in qp_result.x_point.items()},
            "objective_value": round(qp_result.objective_value, 6) if qp_result.objective_value else None,
            "active_constraints": qp_result.active_constraints,
            "solve_time_s": round(qp_result.solve_time_s, 4),
        },
        "bound": {
            "success": bs_result.success,
            "message": bs_result.message,
            "x_lower": {k: round(v, 6) for k, v in bs_result.x_lower.items()},
            "x_upper": {k: round(v, 6) for k, v in bs_result.x_upper.items()},
            "solve_time_s": round(bs_result.solve_time_s, 4),
        },
    }

    with open(expected, "w") as f:
        json.dump(snapshot, f, indent=2)
    print(f"    → saved {expected}")


def main():
    fixtures_dir = Path(__file__).parent / "synthetic"
    output_dir = fixtures_dir / "expected"
    output_dir.mkdir(parents=True, exist_ok=True)

    fixture_files = sorted(fixtures_dir.glob("*.json"))
    fixture_files = [f for f in fixture_files if not f.name.startswith("_")]

    print(f"Generating expected outputs for {len(fixture_files)} fixtures...")
    for fpath in fixture_files:
        run_and_save(fpath, output_dir)
    print("Done.")


if __name__ == "__main__":
    main()
