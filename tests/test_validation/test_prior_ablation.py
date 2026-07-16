from __future__ import annotations

from nusol.config.loader import ConfigLoader
from nusol.config.schema import PriorSpec
from nusol.validation.prior_ablation import generate_prior_ablation_documents


def test_generate_prior_ablation_documents() -> None:
    doc = ConfigLoader().load_from_path("examples/bread_minimal.yaml")
    doc.priors = [
        PriorSpec(
            id="flour_prior",
            type="fraction_interval_prior",
            weight=1.0,
            evidence={"status": "experimental", "source": "unit_test"},
            config={"ingredient": "flour", "interval": [0.4, 0.8]},
        ),
        PriorSpec(
            id="sugar_prior",
            type="fraction_interval_prior",
            weight=1.0,
            evidence={"status": "experimental", "source": "unit_test"},
            config={"ingredient": "sugar", "interval": [0.0, 0.2]},
        ),
    ]

    variants = generate_prior_ablation_documents(doc)

    assert set(variants) == {
        "no_prior",
        "single_prior__flour_prior",
        "single_prior__sugar_prior",
        "all_priors",
    }
    assert [prior.enabled for prior in variants["no_prior"].priors] == [False, False]
    assert [prior.enabled for prior in variants["single_prior__flour_prior"].priors] == [
        True,
        False,
    ]
    assert [prior.enabled for prior in variants["all_priors"].priors] == [True, True]
