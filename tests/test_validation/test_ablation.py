"""Tests for ablation study module."""

from __future__ import annotations

import pytest


class TestAblation:
    """Tests for ablation config generation and execution."""

    def test_generate_ablation_configs(self):
        from nusol.validation.ablation import generate_ablation_configs

        base_config = {
            "run_id": "test",
            "inverse_solver": {
                "constraints": {
                    "mass_balance": {"enabled": True},
                    "ingredient_order": {"enabled": True},
                    "label_interval_fit": {"enabled": True},
                    "energy_closure": {"enabled": True},
                }
            }
        }

        configs = generate_ablation_configs(base_config)
        assert "G0" in configs
        assert "G7" in configs

        # G0 should only have mass_balance enabled
        g0 = configs["G0"]
        g0_constraints = g0["inverse_solver"]["constraints"]
        assert g0_constraints["mass_balance"]["enabled"] is True
        assert g0_constraints["ingredient_order"]["enabled"] is False

        # G2 should have mass_balance, ingredient_order, label_interval_fit
        g2 = configs["G2"]
        g2_constraints = g2["inverse_solver"]["constraints"]
        assert g2_constraints["mass_balance"]["enabled"] is True
        assert g2_constraints["ingredient_order"]["enabled"] is True
        assert g2_constraints["label_interval_fit"]["enabled"] is True
        assert g2_constraints["energy_closure"]["enabled"] is False

    def test_ablation_levels_progressive(self):
        """Each successive level should have more constraints enabled."""
        from nusol.validation.ablation import generate_ablation_configs, ABLATION_LEVELS

        base_config = {"inverse_solver": {"constraints": {}}}
        configs = generate_ablation_configs(base_config)

        for i in range(len(ABLATION_LEVELS) - 1):
            curr = f"G{i}"
            next_lvl = f"G{i+1}"
            curr_count = len(ABLATION_LEVELS[curr])
            next_count = len(ABLATION_LEVELS[next_lvl])
            assert next_count >= curr_count

    def test_ablation_summary(self):
        from nusol.validation.ablation import ablation_summary
        from nusol.validation.metrics import InverseMetrics

        results = {
            "G0": InverseMetrics(n_samples=10, ingredient_mae=0.15, rank_correlation=0.3),
            "G2": InverseMetrics(n_samples=10, ingredient_mae=0.10, rank_correlation=0.6),
            "G7": InverseMetrics(n_samples=10, ingredient_mae=0.05, rank_correlation=0.9),
        }

        summary = ablation_summary(results)
        assert "ABLATION STUDY" in summary
        assert "G0" in summary
        assert "G7" in summary
