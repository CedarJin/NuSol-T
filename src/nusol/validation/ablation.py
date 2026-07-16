"""Ablation study — systematically disable constraints to measure their impact.

LEGACY MODULE — Uses pre-refactor architecture.
Current public solve path is ``nusol.solve(yaml_path)``.
Ablation is planned for Phase 4+ under the new framework.
"""

from __future__ import annotations

import copy
from typing import Any

import numpy as np

from nusol.validation.metrics import ForwardMetrics, InverseMetrics


# Ablation levels: G0 (minimal) → G7 (full model)
# Each level strictly includes the previous + one new constraint type.
ABLATION_LEVELS: dict[str, list[str]] = {
    "G0": ["mass_balance"],
    "G1": ["mass_balance", "ingredient_order"],
    "G2": ["mass_balance", "ingredient_order", "label_interval_fit"],
    "G3": ["mass_balance", "ingredient_order", "label_interval_fit", "energy_closure"],
    "G4": ["mass_balance", "ingredient_order", "label_interval_fit", "energy_closure", "two_percent_rule"],
    "G5": ["mass_balance", "ingredient_order", "label_interval_fit", "energy_closure", "two_percent_rule",
           "water_solid_balance"],
    "G6": ["mass_balance", "ingredient_order", "label_interval_fit", "energy_closure", "two_percent_rule",
           "water_solid_balance", "sodium_balance", "added_sugar_balance", "fatty_acid_closure"],
    "G7": ["mass_balance", "ingredient_order", "label_interval_fit", "energy_closure", "two_percent_rule",
           "water_solid_balance", "sodium_balance", "added_sugar_balance", "fatty_acid_closure",
           "category_prior"],
}


def generate_ablation_configs(base_config: dict[str, Any]) -> dict[str, dict]:
    """Generate configuration variants for each ablation level G0-G7.

    Each level enables a different subset of constraints.

    Args:
        base_config: Base YAML config dict.

    Returns:
        {level_name: config_dict} mapping.
    """
    configs = {}
    for level, enabled in ABLATION_LEVELS.items():
        cfg = copy.deepcopy(base_config)
        constraints_cfg = cfg.setdefault("inverse_solver", {}).setdefault("constraints", {})

        # Disable all constraints first
        for c_name in constraints_cfg:
            constraints_cfg[c_name]["enabled"] = False

        # Enable only those in this level
        for c_name in enabled:
            if c_name not in constraints_cfg:
                constraints_cfg[c_name] = {}
            constraints_cfg[c_name]["enabled"] = True

        configs[level] = cfg

    return configs


def run_ablation(
    run_fn,
    base_config: dict[str, Any],
    data_source,
    levels: list[str] | None = None,
) -> dict[str, InverseMetrics]:
    """Run an ablation study across constraint levels.

    Args:
        run_fn: Function( config, data_source ) → InverseMetrics.
        base_config: Base configuration dict.
        data_source: Data source to pass to run_fn.
        levels: Which ablation levels to test (default: all G0-G7).

    Returns:
        {level_name: InverseMetrics} mapping.
    """
    if levels is None:
        levels = list(ABLATION_LEVELS.keys())

    configs = generate_ablation_configs(base_config)
    results = {}

    for level in levels:
        cfg = configs.get(level, base_config)
        try:
            metrics = run_fn(cfg, data_source)
            results[level] = metrics
        except Exception as e:
            print(f"  Ablation {level} FAILED: {e}")
            results[level] = InverseMetrics(n_samples=0)

    return results


def ablation_summary(results: dict[str, InverseMetrics]) -> str:
    """Generate a human-readable summary of ablation results."""
    lines = ["=" * 60, "ABLATION STUDY RESULTS", "=" * 60]

    for level in sorted(results.keys()):
        metrics = results[level]
        lines.append(
            f"{level:4s} | MAE={metrics.ingredient_mae:.4f} | "
            f"TopMAE={metrics.top_ingredient_mae:.4f} | "
            f"RankCorr={metrics.rank_correlation:.3f} | "
            f"Cover80={metrics.interval_coverage_80:.3f} | "
            f"Solve={metrics.solve_rate:.3f}"
        )

    lines.append("=" * 60)
    return "\n".join(lines)
