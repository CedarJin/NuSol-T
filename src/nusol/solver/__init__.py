"""Inverse solver layer — legacy solvers (to be replaced by refactored framework).

LEGACY — These solvers use a loose context-dict input format and hard-code only
3 constraint types (mass balance, ingredient order, label interval). They are
being replaced by the YAML-driven solver framework (refactor/yaml-solver-framework).

See `docs/REFACTOR_PLAN.md` and `docs/DEVELOPMENT_PLAN.md` for the replacement.
"""

import warnings

from nusol.solver.qp_solver import QPSolver
from nusol.solver.bound_solver import BoundSolver
from nusol.solver.ensemble_solver import EnsembleSolver
from nusol.solver.initializer import generate_initial_guesses

__all__ = [
    "QPSolver",
    "BoundSolver",
    "EnsembleSolver",
    "generate_initial_guesses",
]

warnings.warn(
    "nusol.solver is legacy and will be replaced by the YAML-driven solver framework. "
    "See docs/REFACTOR_PLAN.md",
    DeprecationWarning,
    stacklevel=2,
)
