"""Prior registry — typed PriorSpec compilation to solver-neutral IR."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from nusol.compiler.ir import LinearConstraintIR, QuadraticPenaltyIR


class PriorPlugin:
    """A registered prior type that compiles to objective/soft IR."""

    def __init__(
        self,
        name: str,
        parameter_model: type[BaseModel],
        compile_fn: callable,
        version: str = "0.1.0",
    ) -> None:
        self.name = name
        self.parameter_model = parameter_model
        self.compile_fn = compile_fn
        self.version = version

    def validate_params(self, config: dict[str, Any]) -> dict[str, Any]:
        validated = self.parameter_model.model_validate(config)
        return validated.model_dump()

    def compile(
        self,
        params: dict[str, Any],
        ingredient_ids: list[str],
        n_vars: int,
    ) -> list[LinearConstraintIR | QuadraticPenaltyIR]:
        return self.compile_fn(params, ingredient_ids, n_vars)


class PriorRegistry:
    """Global registry of prior types."""

    def __init__(self) -> None:
        self._plugins: dict[str, PriorPlugin] = {}

    def register(
        self,
        name: str,
        parameter_model: type[BaseModel],
        version: str = "0.1.0",
    ) -> callable:
        def decorator(compile_fn: callable) -> callable:
            if name in self._plugins:
                raise ValueError(f"Prior type '{name}' already registered")
            self._plugins[name] = PriorPlugin(
                name=name,
                parameter_model=parameter_model,
                compile_fn=compile_fn,
                version=version,
            )
            return compile_fn

        return decorator

    def get(self, name: str) -> PriorPlugin:
        plugin = self._plugins.get(name)
        if plugin is None:
            raise KeyError(
                f"Unknown prior type '{name}'. Available: {sorted(self._plugins)}"
            )
        return plugin

    def has(self, name: str) -> bool:
        return name in self._plugins

    def names(self) -> list[str]:
        return sorted(self._plugins)


_PRIOR_REGISTRY: PriorRegistry | None = None


def get_prior_registry() -> PriorRegistry:
    global _PRIOR_REGISTRY
    if _PRIOR_REGISTRY is None:
        _PRIOR_REGISTRY = PriorRegistry()
        _register_builtin_priors(_PRIOR_REGISTRY)
    return _PRIOR_REGISTRY


def _register_builtin_priors(registry: PriorRegistry) -> None:
    from nusol.priors.builtin.anti_extreme import register as reg_anti
    from nusol.priors.builtin.fraction_interval import register as reg_frac
    from nusol.priors.builtin.group_total import register as reg_group
    from nusol.priors.builtin.ratio import register as reg_ratio
    from nusol.priors.builtin.recipe_center import register as reg_center

    for register_fn in [reg_frac, reg_group, reg_center, reg_anti, reg_ratio]:
        register_fn(registry)
