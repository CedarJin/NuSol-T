"""NuSol-T error hierarchy.

Three layers: ConfigError (YAML/schema) → CompileError (IR) → SolveError (backend).
Each layer throws only its own error types.
"""

from __future__ import annotations


class NuSolError(Exception):
    """Base error for all NuSol-T failures."""


# Layer 1: Configuration phase

class ConfigError(NuSolError):
    """Base for all configuration-time errors."""
    exit_code: int = 1


class SchemaValidationError(ConfigError):
    """Pydantic validation failure with field paths."""


class InheritanceError(ConfigError):
    """Cycle detected, parent not found, merge conflict."""


class ResourceError(ConfigError):
    """File not found, checksum mismatch, unsupported format."""


# Layer 2: Compilation phase

class CompileError(NuSolError):
    """Missing nutrient, shape mismatch, unsupported constraint, etc."""
    exit_code: int = 2


class MissingNutrientError(CompileError):
    """Observation references a nutrient not in composition matrix."""


class UnsupportedConstraintError(CompileError):
    """Enabled constraint type has no backend that supports it."""


# Layer 3: Solve phase

class SolveError(NuSolError):
    """Infeasible, unbounded, numerical failure, timeout."""
    exit_code: int = 3
