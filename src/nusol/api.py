"""NuSol-T public API — ``solve(yaml_path)`` is the single entry point.

Usage::

    import nusol
    result = nusol.solve("problem.yaml")
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nusol.backends.highs_lp import HighsLPBackend
from nusol.backends.registry import get_backend_registry
from nusol.backends.scipy_slsqp import ScipySLSQPBackend
from nusol.compiler.compiler import compile_problem
from nusol.config.errors import ConfigError, NuSolError
from nusol.config.loader import ConfigLoader
from nusol.config.resolver import ConfigResolver, yaml_to_canonical_string
from nusol.domain.builder import build_problem


def solve(yaml_path: str | Path) -> dict[str, Any]:
    """Solve an ingredient estimation problem from a YAML file.

    This is the single public entry point for NuSol-T.
    Full pipeline: load → resolve → build → compile → solve → results.

    Args:
        yaml_path: Path to a YAML problem document.

    Returns:
        A dict with keys::

            success (bool)
            status (str): "optimal", "infeasible", "error"
            problem_id (str)
            fractions (dict): ingredient_id → point estimate
            bounds (dict): ingredient_id → [lower, upper]
            diagnostics (dict): backend stats and constraint info
            manifest (dict): run metadata (config, resources, versions)
            error (str, optional): error message if not successful

    Raises:
        ConfigError: On YAML schema or resolution errors.
        NuSolError: On domain, compile, or solve errors.

    Example::

        import nusol
        result = nusol.solve("examples/bread_minimal.yaml")
        print(result["fractions"])
    """
    path = Path(yaml_path)
    t_start = time.perf_counter()

    # 1. Load and resolve
    loader = ConfigLoader()
    doc = loader.load_from_path(str(path))
    resolver = ConfigResolver()
    resolved_dict = resolver.resolve_to_dict(str(path))

    # 2. Build domain model
    problem = build_problem(doc)

    # 3. Compile to IR
    compiled = compile_problem(problem)

    # 4. Solve point
    point_backend = ScipySLSQPBackend()
    reg = get_backend_registry()
    reg.check_point_capabilities("scipy_slsqp", compiled.required_capabilities)

    try:
        fractions, point_stats = point_backend.solve_point(compiled)
    except NuSolError as e:
        fractions = {}
        point_stats = None

    # 5. Solve bounds (only using hard constraints, ignoring soft)
    bounds_backend = HighsLPBackend()
    try:
        # Bounds solver only needs continuous + linear_constraints (ignores soft)
        bounds_caps = frozenset({"continuous", "linear_constraints"})
        reg.check_bounds_capabilities("highs_lp", bounds_caps)
        bounds_dict, bounds_stats = bounds_backend.solve_bounds(compiled)
    except NuSolError:
        bounds_dict = {}
        bounds_stats = None

    # 6. Build result
    t_end = time.perf_counter()

    diagnostics = {
        "point": point_stats.as_dict() if point_stats else {"success": False, "status": "error"},
        "bounds": bounds_stats.as_dict() if bounds_stats else {"success": False, "status": "error"},
        "n_variables": compiled.n_variables,
        "n_constraints": len(compiled.linear_constraints),
        "total_time_s": t_end - t_start,
    }

    result: dict[str, Any] = {
        "success": point_stats is not None and point_stats.success if point_stats else False,
        "status": "optimal" if point_stats and point_stats.success else "error",
        "problem_id": problem.problem_id,
        "fractions": fractions,
        "bounds": {
            ing: list(bounds_dict.get(ing, (0.0, 1.0)))
            for ing in problem.ingredient_ids
        } if bounds_dict else {},
        "diagnostics": diagnostics,
        "manifest": _build_manifest(
            problem.problem_id, str(path), resolved_dict,
            diagnostics, fractions,
        ),
    }

    if not result["success"] and point_stats is not None:
        result["error"] = point_stats.message

    return result


def _build_manifest(
    problem_id: str,
    yaml_path: str,
    resolved_dict: dict[str, Any],
    diagnostics: dict[str, Any],
    fractions: dict[str, float],
) -> dict[str, Any]:
    """Build run manifest with reproducibility information."""
    now = datetime.now(timezone.utc)

    # Compute config checksum
    config_str = yaml_to_canonical_string(resolved_dict)
    config_sha256 = hashlib.sha256(config_str.encode()).hexdigest()

    # Get git info
    git_commit = _get_git_commit(yaml_path)

    manifest: dict[str, Any] = {
        "schema_version": "1.0",
        "problem_id": problem_id,
        "run_id": now.strftime("%Y%m%dT%H%M%S-") + config_sha256[:8],
        "timestamps": {
            "started": now.isoformat(),
        },
        "software": {
            "nusol_version": _get_version(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "git": {
            "commit": git_commit or "unknown",
        },
        "resolved_config": {
            "sha256": config_sha256,
        },
        "solver": {
            "point": diagnostics.get("point", {}),
            "bounds": diagnostics.get("bounds", {}),
        },
    }
    return manifest


def _get_git_commit(path: str) -> str | None:
    """Get the current git commit hash."""
    repo_dir = Path(path).resolve().parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=repo_dir, timeout=2,
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def _get_version() -> str:
    try:
        from nusol import __version__
        return __version__
    except ImportError:
        return "unknown"
