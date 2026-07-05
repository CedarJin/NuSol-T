# NuSol-T

**An Extensible Unified Framework for Food Nutrient Composition Analysis.**

Given ingredients, their nutrient compositions, a Nutrition Facts label, and optional prior knowledge, NuSol-T estimates ingredient mass fractions and their feasible ranges.

## Status

**Research prototype** — Phases 0-8 complete on the `refactor/yaml-solver-framework` branch.

```bash
nusol validate problem.yaml    # Check YAML document
nusol resolve problem.yaml     # Resolve extends defaults
nusol inspect problem.yaml     # Show problem structure
nusol solve problem.yaml       # Run full solve pipeline
```

## Quick Start

```bash
# Install
uv sync

# Run a minimal example
uv run nusol solve examples/bread_minimal.yaml
```

Output:
```
Solve SUCCESS ✓  (bread_minimal)
  fractions:
    flour                0.4854  [0.0000, 1.0000]
    sugar                0.4056  [0.0000, 1.0000]
    oil                  0.1090  [0.0000, 1.0000]
  solve_time: 0.0100s
```

## Python API

```python
import nusol
result = nusol.solve("problem.yaml")
print(result["fractions"])   # {'flour': 0.485, ...}
print(result["bounds"])      # {'flour': [0.0, 1.0], ...}
```

## Data Requirements

The USDA FoodData Central databases are stored at `../db/` (outside the project):

```
../db/
├── FoodData_Central_survey_food_json_2024-10-31/
├── FoodData_Central_branded_food_json_2026-04-30/
├── FoodData_Central_sr_legacy_food_json_2018-04/
└── FoodData_Central_foundation_food_json_2026-04-30/
```

See `docs/DATA.md` for details.

## Documentation

| Document | Purpose |
|----------|---------|
| `docs/NuSol-T.md` | Overall project vision |
| `docs/REFACTOR_PLAN.md` | YAML-driven architecture design |
| `docs/DEVELOPMENT_PLAN.md` | Phase-by-phase execution plan |
| `docs/CURRENT_STATUS.md` | Module-by-module implementation status |
| `docs/DATA.md` | Data dictionary and mapping strategy |
| `docs/DEVELOPMENT.md` | Original development guide (legacy) |
| `docs/FIX_PLAN.md` | Known issues index |

## Development

```bash
# Run tests
uv run pytest

# Lint and type check
uv run ruff check src/
uv run mypy src/

# FNDDS spike (requires USDA data)
uv run python scripts/spike_fndds_ir.py
```

## Architecture

```
YAML → Load + Validate → Resolve extends → Build IngredientProblem
  → Compile constraints → IR → Capability check → Backend solve → Result
```

See `docs/REFACTOR_PLAN.md` for the complete architecture.

## Known Limitations

- **Not a calibrated scientific tool** — feasible bounds are mathematical, not probabilistic
- **Cross-database mapping amplifies error** — SR Legacy composition ≠ FNDDS internal values
- **Missing nutrients ≠ zero** — unanalyzed nutrients are not automatically zero
- **Branded Food pipeline** — real package ingredient parsing still under development

## License

See LICENSE file.
