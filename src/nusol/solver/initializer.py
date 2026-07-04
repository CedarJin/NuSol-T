"""Multi-start initialization strategies for the inverse solver."""

from __future__ import annotations

from typing import Any

import numpy as np


def generate_initial_guesses(
    n_variables: int,
    n_starts: int = 50,
    strategy: str = "dirichlet",
    seed: int = 42,
    context: dict[str, Any] | None = None,
) -> list[np.ndarray]:
    """Generate initial guesses for multi-start optimization.

    Args:
        n_variables: Number of decision variables.
        n_starts: Number of starting points to generate.
        strategy: Initialization strategy:
            - "dirichlet": Sample from Dirichlet distribution (sums to 1).
            - "uniform_random": Uniform random + normalize.
            - "uniform_grid": Evenly spaced starting points.
        seed: Random seed for reproducibility.
        context: Optional context with ingredient order info.

    Returns:
        List of initial guess arrays, each of length n_variables.
    """
    rng = np.random.default_rng(seed)

    guesses = []

    if strategy == "dirichlet":
        # Sample from Dirichlet(α=1) which is uniform over the simplex
        for i in range(n_starts):
            x = rng.dirichlet(np.ones(n_variables))
            guesses.append(x)

    elif strategy == "uniform_random":
        for i in range(n_starts):
            x = rng.uniform(0.1, 2.0, size=n_variables)
            x = x / x.sum()
            guesses.append(x)

    elif strategy == "uniform_grid":
        # Start from uniform + small perturbations
        base = np.ones(n_variables) / n_variables
        guesses.append(base)
        for i in range(1, n_starts):
            perturbation = rng.uniform(-0.05, 0.05, size=n_variables)
            x = base + perturbation
            x = np.clip(x, 0.001, None)
            x = x / x.sum()
            guesses.append(x)

    elif strategy == "decreasing":
        # Generate guesses that already satisfy ingredient order (descending)
        for i in range(n_starts):
            x = rng.exponential(1.0, size=n_variables)
            x.sort()
            x = x[::-1]  # Make descending
            x = x / x.sum()
            guesses.append(x)

    else:
        raise ValueError(f"Unknown initialization strategy: {strategy}")

    return guesses
