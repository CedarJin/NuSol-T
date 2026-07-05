"""NuSol-T: An Extensible Unified Framework for Food Nutrient Composition Analysis.

YAML-driven ingredient estimation::

    import nusol
    result = nusol.solve("problem.yaml")
"""

from nusol.api import solve
from nusol.config.schema import SolveDocument

__all__ = [
    "solve",
    "SolveDocument",
]

__version__ = "0.2.0"
