"""Constraint registry — global registration, discovery, and capability declarations."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from nusol.compiler.ir import LinearConstraintIR, QuadraticPenaltyIR, CompiledProblem


class ConstraintPlugin:
    """A registered constraint type that can compile to IR."""

    def __init__(
        self,
        name: str,
        parameter_model: type[BaseModel] | None,
        capabilities: frozenset[str],
        compile_fn: callable,
    ) -> None:
        self.name = name
        self.parameter_model = parameter_model
        self.capabilities = capabilities
        self.compile_fn = compile_fn

    def validate_params(self, config: dict[str, Any]) -> dict[str, Any]:
        """Validate constraint-specific config against parameter model."""
        if self.parameter_model is None:
            return config
        validated = self.parameter_model.model_validate(config)
        return validated.model_dump()

    def compile(
        self,
        params: dict[str, Any],
        ingredient_ids: list[str],
        nutrient_ids: list[str],
        n_vars: int,
    ) -> list[LinearConstraintIR | QuadraticPenaltyIR]:
        """Compile this constraint to IR."""
        return self.compile_fn(params, ingredient_ids, nutrient_ids, n_vars)


class ConstraintRegistry:
    """Global registry of constraint types.

    All constraint types must be registered here before they can be used.
    This replaces the legacy ConstraintBuilder's hardcoded class list.
    """

    def __init__(self) -> None:
        self._plugins: dict[str, ConstraintPlugin] = {}

    def register(
        self,
        name: str,
        parameter_model: type[BaseModel] | None = None,
        capabilities: frozenset[str] | None = None,
    ) -> callable:
        """Decorator to register a constraint compile function.

        Args:
            name: Constraint type name (used in YAML ``type`` field).
            parameter_model: Optional Pydantic model for config validation.
            capabilities: Required backend capabilities.

        Usage::

            @registry.register("mass_balance")
            def compile_mass_balance(params, ingredients, nutrients, n_vars):
                ...
        """
        caps = capabilities or frozenset({"linear_constraints"})

        def decorator(compile_fn: callable) -> callable:
            if name in self._plugins:
                raise ValueError(f"Constraint type '{name}' already registered")
            self._plugins[name] = ConstraintPlugin(
                name=name,
                parameter_model=parameter_model,
                capabilities=caps,
                compile_fn=compile_fn,
            )
            return compile_fn

        return decorator

    def get(self, name: str) -> ConstraintPlugin:
        """Get a registered constraint plugin by name."""
        plugin = self._plugins.get(name)
        if plugin is None:
            raise KeyError(
                f"Unknown constraint type '{name}'. "
                f"Available: {sorted(self._plugins.keys())}"
            )
        return plugin

    def has(self, name: str) -> bool:
        return name in self._plugins

    def names(self) -> list[str]:
        return sorted(self._plugins.keys())

    def required_capabilities(self, name: str) -> frozenset[str]:
        return self.get(name).capabilities


# Global singleton
_CONSTRAINT_REGISTRY: ConstraintRegistry | None = None


def get_constraint_registry() -> ConstraintRegistry:
    """Get or create the global constraint registry singleton."""
    global _CONSTRAINT_REGISTRY
    if _CONSTRAINT_REGISTRY is None:
        _CONSTRAINT_REGISTRY = ConstraintRegistry()
        # Built-in constraints are registered on first access
        _register_builtin_constraints(_CONSTRAINT_REGISTRY)
    return _CONSTRAINT_REGISTRY


def _register_builtin_constraints(registry: ConstraintRegistry) -> None:
    """Register all built-in constraint types."""
    from nusol.constraints.builtin.mass_balance import register as reg_mb
    from nusol.constraints.builtin.ingredient_order import register as reg_io
    from nusol.constraints.builtin.two_percent import register as reg_tp
    from nusol.constraints.builtin.nutrient_interval import register as reg_ni
    from nusol.constraints.builtin.declared_percentage import register as reg_dp
    from nusol.constraints.builtin.linear_expression import register as reg_le
    from nusol.constraints.builtin.unique_source import register as reg_us

    for register_fn in [reg_mb, reg_io, reg_tp, reg_ni, reg_dp, reg_le, reg_us]:
        register_fn(registry)
