"""Tests for validation metrics."""

from __future__ import annotations

import numpy as np
import pytest


class TestForwardMetrics:
    """Tests for forward calculation metrics."""

    def test_perfect_prediction(self):
        from nusol.validation.metrics import compute_forward_metrics

        true = {"Energy": [250.0, 300.0], "Protein": [10.0, 15.0]}
        pred = {"Energy": [250.0, 300.0], "Protein": [10.0, 15.0]}

        metrics = compute_forward_metrics(true, pred)
        assert metrics.n_samples == 2
        assert metrics.overall_mae == 0.0
        assert metrics.overall_relative_error == 0.0

    def test_with_errors(self):
        from nusol.validation.metrics import compute_forward_metrics

        true = {"Energy": [100.0], "Protein": [10.0]}
        pred = {"Energy": [110.0], "Protein": [9.0]}

        metrics = compute_forward_metrics(true, pred)
        assert metrics.n_samples == 1
        assert metrics.overall_mae == pytest.approx(5.5)  # (10 + 1)/2


class TestInverseMetrics:
    """Tests for inverse reconstruction metrics."""

    def test_perfect_reconstruction(self):
        from nusol.validation.metrics import compute_inverse_metrics

        true_fracs = [{"flour": 0.5, "sugar": 0.3, "oil": 0.2}]
        est_fracs = [{"flour": 0.5, "sugar": 0.3, "oil": 0.2}]

        metrics = compute_inverse_metrics(true_fracs, est_fracs)
        assert metrics.n_samples == 1
        assert metrics.ingredient_mae == 0.0
        assert metrics.rank_correlation == 1.0

    def test_with_errors(self):
        from nusol.validation.metrics import compute_inverse_metrics

        true_fracs = [{"a": 0.6, "b": 0.4}]
        est_fracs = [{"a": 0.5, "b": 0.5}]

        metrics = compute_inverse_metrics(true_fracs, est_fracs)
        assert metrics.ingredient_mae == pytest.approx(0.1)

    def test_with_coverage(self):
        from nusol.validation.metrics import compute_inverse_metrics

        true_fracs = [{"a": 0.5, "b": 0.5}]
        est_fracs = [{"a": 0.5, "b": 0.5}]
        est_lower = [{"a": 0.4, "b": 0.4}]
        est_upper = [{"a": 0.6, "b": 0.6}]

        metrics = compute_inverse_metrics(
            true_fracs, est_fracs,
            estimated_lower=est_lower,
            estimated_upper=est_upper,
        )
        assert metrics.interval_coverage_80 == 1.0
        assert metrics.average_interval_width == pytest.approx(0.2)

    def test_solve_rate(self):
        from nusol.validation.metrics import compute_inverse_metrics

        true_fracs = [{"a": 0.5, "b": 0.5}, {"a": 0.6, "b": 0.4}]
        est_fracs = [{"a": 0.5, "b": 0.5}, {"a": 0.6, "b": 0.4}]

        metrics = compute_inverse_metrics(true_fracs, est_fracs, solve_success=[True, False])
        assert metrics.solve_rate == 0.5

    def test_empty_input(self):
        from nusol.validation.metrics import compute_inverse_metrics

        metrics = compute_inverse_metrics([], [])
        assert metrics.n_samples == 0
        assert metrics.ingredient_mae == 0.0
