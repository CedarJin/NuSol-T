"""Prior ablation utilities for YAML SolveDocument experiments."""

from __future__ import annotations

from nusol.config.schema import SolveDocument


def generate_prior_ablation_documents(
    document: SolveDocument,
) -> dict[str, SolveDocument]:
    """Generate no-prior, single-prior, and all-prior document variants.

    The returned documents are deep copies and safe to mutate independently.
    Disabled priors remain disabled in all variants; only originally enabled
    priors participate in the ablation.
    """
    enabled_prior_ids = [prior.id for prior in document.priors if prior.enabled]

    no_prior = document.model_copy(deep=True)
    for prior in no_prior.priors:
        prior.enabled = False

    variants = {"no_prior": no_prior}

    for prior_id in enabled_prior_ids:
        variant = document.model_copy(deep=True)
        for prior in variant.priors:
            prior.enabled = prior.id == prior_id
        variants[f"single_prior__{prior_id}"] = variant

    all_priors = document.model_copy(deep=True)
    for prior in all_priors.priors:
        prior.enabled = prior.id in enabled_prior_ids
    variants["all_priors"] = all_priors

    return variants
