"""Backend registry — global registration and capability matching."""

from __future__ import annotations

from nusol.backends.base import PointBackend, BoundsBackend
from nusol.config.errors import UnsupportedConstraintError


class BackendRegistry:
    """Global registry of solver backends.

    Supports capability matching: when compiling a problem, the registry
    verifies that the selected backend can handle all required capabilities.
    """

    def __init__(self) -> None:
        self._point: dict[str, type[PointBackend]] = {}
        self._bounds: dict[str, type[BoundsBackend]] = {}

    def register_point(self, name: str, cls: type[PointBackend]) -> None:
        if name in self._point:
            raise ValueError(f"Point backend '{name}' already registered")
        self._point[name] = cls

    def register_bounds(self, name: str, cls: type[BoundsBackend]) -> None:
        if name in self._bounds:
            raise ValueError(f"Bounds backend '{name}' already registered")
        self._bounds[name] = cls

    def get_point(self, name: str) -> type[PointBackend]:
        backend = self._point.get(name)
        if backend is None:
            raise KeyError(
                f"Unknown point backend '{name}'. "
                f"Available: {sorted(self._point.keys())}"
            )
        return backend

    def get_bounds(self, name: str) -> type[BoundsBackend]:
        backend = self._bounds.get(name)
        if backend is None:
            raise KeyError(
                f"Unknown bounds backend '{name}'. "
                f"Available: {sorted(self._bounds.keys())}"
            )
        return backend

    def check_point_capabilities(
        self, name: str, required: frozenset[str],
    ) -> None:
        """Raise if backend cannot satisfy required capabilities."""
        backend = self.get_point(name)
        missing = required - backend.capabilities
        if missing:
            raise UnsupportedConstraintError(
                f"Point backend '{name}' lacks required capabilities: {missing}. "
                f"Has: {backend.capabilities}"
            )

    def check_bounds_capabilities(
        self, name: str, required: frozenset[str],
    ) -> None:
        backend = self.get_bounds(name)
        missing = required - backend.capabilities
        if missing:
            raise UnsupportedConstraintError(
                f"Bounds backend '{name}' lacks required capabilities: {missing}. "
                f"Has: {backend.capabilities}"
            )


# Global singleton
_backend_registry: BackendRegistry | None = None


def get_backend_registry() -> BackendRegistry:
    global _backend_registry
    if _backend_registry is None:
        _backend_registry = BackendRegistry()
        _register_builtin_backends(_backend_registry)
    return _backend_registry


def _register_builtin_backends(registry: BackendRegistry) -> None:
    from nusol.backends.scipy_slsqp import ScipySLSQPBackend
    from nusol.backends.highs_lp import HighsLPBackend

    registry.register_point(ScipySLSQPBackend.name, ScipySLSQPBackend)
    registry.register_bounds(HighsLPBackend.name, HighsLPBackend)
