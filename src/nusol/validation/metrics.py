"""Validation metrics for forward and inverse evaluation."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ForwardMetrics:
    """Metrics for forward nutrition calculation validation."""

    n_samples: int = 0
    nutrient_mae: dict[str, float] = field(default_factory=dict)
    nutrient_relative_error: dict[str, float] = field(default_factory=dict)
    nutrient_median_error: dict[str, float] = field(default_factory=dict)
    overall_mae: float = 0.0
    overall_relative_error: float = 0.0

    def summary(self) -> str:
        lines = [
            f"Forward Metrics (n={self.n_samples}):",
            f"  Overall MAE: {self.overall_mae:.4f}",
            f"  Overall Relative Error: {self.overall_relative_error:.4f}",
        ]
        for name in sorted(self.nutrient_mae):
            lines.append(f"  {name}: MAE={self.nutrient_mae[name]:.4f}, "
                        f"RelErr={self.nutrient_relative_error.get(name, 0):.4f}")
        return "\n".join(lines)


@dataclass
class InverseMetrics:
    """Metrics for inverse ingredient reconstruction."""

    n_samples: int = 0
    ingredient_mae: float = 0.0
    top_ingredient_mae: float = 0.0
    rank_correlation: float = 0.0
    interval_coverage_80: float = 0.0
    interval_coverage_95: float = 0.0
    average_interval_width: float = 0.0
    solve_rate: float = 0.0
    zero_slack_rate: float = 0.0
    constraint_conflict_frequency: dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"Inverse Metrics (n={self.n_samples}):",
            f"  Ingredient MAE: {self.ingredient_mae:.4f}",
            f"  Top Ingredient MAE: {self.top_ingredient_mae:.4f}",
            f"  Rank Correlation: {self.rank_correlation:.4f}",
            f"  80% Coverage: {self.interval_coverage_80:.4f}",
            f"  95% Coverage: {self.interval_coverage_95:.4f}",
            f"  Avg Interval Width: {self.average_interval_width:.4f}",
            f"  Solve Rate: {self.solve_rate:.4f}",
            f"  Zero-Slack Rate: {self.zero_slack_rate:.4f}",
        ]
        return "\n".join(lines)


def compute_forward_metrics(
    true_values: dict[str, list[float]],
    predicted_values: dict[str, list[float]],
) -> ForwardMetrics:
    """Compute forward calculation metrics.

    Args:
        true_values: {nutrient_name: [values across samples]}
        predicted_values: {nutrient_name: [values across samples]}

    Returns:
        ForwardMetrics dataclass.
    """
    metrics = ForwardMetrics()

    all_abs_errors = []
    all_rel_errors = []

    for name in true_values:
        t = np.array(true_values[name])
        p = np.array(predicted_values.get(name, [0] * len(t)))

        if len(t) > 0:
            ae = np.abs(t - p)
            metrics.nutrient_mae[name] = float(np.mean(ae))

            # Relative error (avoid division by zero)
            mask = t != 0
            if mask.any():
                re = np.abs((t[mask] - p[mask]) / t[mask])
                metrics.nutrient_relative_error[name] = float(np.mean(re))
                all_rel_errors.extend(re.tolist())
            else:
                metrics.nutrient_relative_error[name] = 0.0

            metrics.nutrient_median_error[name] = float(np.median(ae))
            all_abs_errors.extend(ae.tolist())

    metrics.n_samples = len(next(iter(true_values.values()), []))
    metrics.overall_mae = float(np.mean(all_abs_errors)) if all_abs_errors else 0.0
    metrics.overall_relative_error = float(np.mean(all_rel_errors)) if all_rel_errors else 0.0

    return metrics


def compute_inverse_metrics(
    true_fractions: list[dict[str, float]],
    estimated_fractions: list[dict[str, float]],
    estimated_lower: list[dict[str, float]] | None = None,
    estimated_upper: list[dict[str, float]] | None = None,
    solve_success: list[bool] | None = None,
    active_constraints: list[list[str]] | None = None,
) -> InverseMetrics:
    """Compute inverse reconstruction metrics.

    Args:
        true_fractions: List of {ingredient: true_fraction} dicts.
        estimated_fractions: List of {ingredient: estimated_fraction} dicts.
        estimated_lower: List of {ingredient: lower_bound} dicts (from BoundSolver).
        estimated_upper: List of {ingredient: upper_bound} dicts.
        solve_success: Whether each solve succeeded.
        active_constraints: Active (violated) constraint names per sample.

    Returns:
        InverseMetrics dataclass.
    """
    metrics = InverseMetrics()
    metrics.n_samples = len(true_fractions)

    if metrics.n_samples == 0:
        return metrics

    # Solve rate
    if solve_success:
        metrics.solve_rate = sum(1 for s in solve_success if s) / len(solve_success)
    else:
        metrics.solve_rate = 1.0

    all_abs_errors = []
    top_abs_errors = []
    rank_correlations = []
    coverages_80 = []
    coverages_95 = []
    interval_widths = []

    for idx, true_frac in enumerate(true_fractions):
        est_frac = estimated_fractions[idx] if idx < len(estimated_fractions) else {}

        # Compute MAE for common ingredients
        common = set(true_frac) & set(est_frac)
        if common:
            errors = [abs(true_frac[k] - est_frac.get(k, 0)) for k in common]
            all_abs_errors.extend(errors)

            # Top ingredient error
            top_true = max(true_frac, key=true_frac.get)
            if top_true in est_frac:
                top_abs_errors.append(abs(true_frac[top_true] - est_frac[top_true]))

            # Rank correlation (Spearman)
            true_sorted = sorted(true_frac, key=true_frac.get, reverse=True)
            est_sorted = sorted(est_frac, key=est_frac.get, reverse=True)

            true_ranks = {name: i for i, name in enumerate(true_sorted)}
            est_ranks = {name: i for i, name in enumerate(est_sorted)}

            common_ranked = [k for k in common if k in true_ranks and k in est_ranks]
            if len(common_ranked) >= 2:
                d2 = sum((true_ranks[k] - est_ranks[k])**2 for k in common_ranked)
                n = len(common_ranked)
                rho = 1.0 - 6.0 * d2 / (n * (n**2 - 1)) if n > 1 else 0.0
                rank_correlations.append(rho)

        # Coverage
        if estimated_lower and estimated_upper:
            lo = estimated_lower[idx] if idx < len(estimated_lower) else {}
            hi = estimated_upper[idx] if idx < len(estimated_upper) else {}
            for k in common:
                if k in lo and k in hi:
                    w = hi[k] - lo[k]
                    interval_widths.append(w)
                    if lo[k] <= true_frac[k] <= hi[k]:
                        coverages_80.append(1.0)
                        coverages_95.append(1.0)
                    else:
                        coverages_80.append(0.0)
                        coverages_95.append(0.0)

    metrics.ingredient_mae = float(np.mean(all_abs_errors)) if all_abs_errors else 0.0
    metrics.top_ingredient_mae = float(np.mean(top_abs_errors)) if top_abs_errors else 0.0
    metrics.rank_correlation = float(np.mean(rank_correlations)) if rank_correlations else 0.0
    metrics.interval_coverage_80 = float(np.mean(coverages_80)) if coverages_80 else 0.0
    metrics.interval_coverage_95 = float(np.mean(coverages_95)) if coverages_95 else 0.0
    metrics.average_interval_width = float(np.mean(interval_widths)) if interval_widths else 0.0

    # Constraint conflicts
    if active_constraints:
        from collections import Counter

        all_conflicts = []
        for ac in active_constraints:
            all_conflicts.extend(ac)
        counter = Counter(all_conflicts)
        total = len(active_constraints)
        metrics.constraint_conflict_frequency = {
            k: v / total for k, v in counter.items()
        }
        metrics.zero_slack_rate = 1.0 - (sum(counter.values()) / total) if total > 0 else 1.0

    return metrics
