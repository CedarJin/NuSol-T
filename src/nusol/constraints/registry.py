"""Constraint registry — global registration, discovery, and capability declarations.

Supports both built-in constraints (registered programmatically) and
external plugins discovered via ``nusol.constraints`` entry points.

Plugin discovery::

    # In your plugin package's pyproject.toml:
    [project.entry-points."nusol.constraints"]
    my_constraint = "my_package:register"

    # The register function receives a ConstraintRegistry:
    def register(registry: ConstraintRegistry) -> None:
        @registry.register("my_constraint", version="1.0")
        def compile_my_constraint(params, ing_ids, nut_ids, n_vars):
            ...
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from nusol.compiler.ir import LinearConstraintIR, QuadraticPenaltyIR


class ConstraintPlugin:
    """A registered constraint type that can compile to IR."""

    def __init__(
        self,
        name: str,
        parameter_model: type[BaseModel] | None,
        capabilities: frozenset[str],
        compile_fn: callable,
        version: str = "0.1.0",
        source: str = "builtin",
        package_version: str = "",
    ) -> None:
        self.name = name
        self.version = version
        self.source = source  # "builtin" or package distribution name
        self.package_version = package_version
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
    """

    def __init__(self) -> None:
        self._plugins: dict[str, ConstraintPlugin] = {}

    def register(
        self,
        name: str,
        parameter_model: type[BaseModel] | None = None,
        capabilities: frozenset[str] | None = None,
        version: str = "0.1.0",
    ) -> callable:
        """Decorator to register a constraint compile function.

        Args:
            name: Constraint type name (used in YAML ``type`` field).
            parameter_model: Optional Pydantic model for config validation.
            capabilities: Required backend capabilities.
            version: Semantic version of this constraint type.

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
                version=version,
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

    def discover_plugins(self) -> list[str]:
        """Discover external constraint plugins via entry points.

        Scans the ``nusol.constraints`` entry point group.
        Each entry point should point to a ``register(registry)`` function.

        Returns:
            List of discovered constraint type names.
        """
        import importlib.metadata as md

        discovered = []
        for ep in md.entry_points(group="nusol.constraints"):
            try:
                register_fn = ep.load()
                dist = md.distribution(ep.dist.name) if ep.dist else None
                pkg_ver = dist.version if dist else "unknown"

                # Call register function, which will use decorator
                register_fn(self)

                # Update source info for plugins registered by this call
                for name, plugin in self._plugins.items():
                    if plugin.source == "builtin" and name not in _BUILTIN_NAMES:
                        plugin.source = ep.dist.name if ep.dist else "plugin"
                        plugin.package_version = pkg_ver
                        discovered.append(name)
            except Exception as e:
                import warnings
                warnings.warn(
                    f"Failed to load constraint plugin '{ep.name}': {e}"
                )

        return discovered


# ── Singleton + initialization ──

_BUILTIN_NAMES: set[str] = set()
_CONSTRAINT_REGISTRY: ConstraintRegistry | None = None


def get_constraint_registry() -> ConstraintRegistry:
    """Get or create the global constraint registry singleton."""
    global _CONSTRAINT_REGISTRY
    if _CONSTRAINT_REGISTRY is None:
        _CONSTRAINT_REGISTRY = ConstraintRegistry()
        _register_builtin_constraints(_CONSTRAINT_REGISTRY)
        # Discover external plugins
        _CONSTRAINT_REGISTRY.discover_plugins()
    return _CONSTRAINT_REGISTRY


def _register_builtin_constraints(registry: ConstraintRegistry) -> None:
    """Register all built-in constraint types and track their names."""
    from nusol.constraints.builtin.mass_balance import register as reg_mb
    from nusol.constraints.builtin.ingredient_order import register as reg_io
    from nusol.constraints.builtin.two_percent import register as reg_tp
    from nusol.constraints.builtin.nutrient_interval import register as reg_ni
    from nusol.constraints.builtin.declared_percentage import register as reg_dp
    from nusol.constraints.builtin.linear_expression import register as reg_le
    from nusol.constraints.builtin.unique_source import register as reg_us

    for register_fn in [reg_mb, reg_io, reg_tp, reg_ni, reg_dp, reg_le]:
        register_fn(registry)

    global _BUILTIN_NAMES
    _BUILTIN_NAMES = set(registry.names())
