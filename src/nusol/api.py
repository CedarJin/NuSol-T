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

from nusol.backends.registry import get_backend_registry
from nusol.compiler.compiler import compile_problem
from nusol.config.errors import ConfigError, NuSolError
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

    # 1. Resolve (load + extends + defaults) into a single validated SolveDocument
    resolver = ConfigResolver()
    doc = resolver.resolve(str(path))

    # Also get canonical dict for manifest
    resolved_dict = resolver.resolve_to_dict(str(path))

    # 2. Build domain model from resolved document
    problem = build_problem(doc)

    # 3. Compile to IR
    compiled = compile_problem(problem)

    # 4. Read solver config from resolved YAML
    reg = get_backend_registry()
    solver_spec = doc.solver

    # 5. Solve point (if configured)
    fractions = {}
    point_stats = None
    if solver_spec.point:
        point_name = solver_spec.point.backend.value
        point_opts = solver_spec.point.options
        reg.check_point_capabilities(point_name, compiled.required_capabilities)
        p_cls = reg.get_point(point_name)
        p_backend = p_cls(options=point_opts)
        try:
            fractions, point_stats = p_backend.solve_point(compiled)
        except NuSolError:
            point_stats = None

    # 6. Solve bounds (default: use highs_lp even without explicit bounds config)
    bounds_dict = {}
    bounds_stats = None
    b_name = solver_spec.bounds.backend.value if solver_spec.bounds else "highs_lp"
    b_caps = frozenset({"continuous", "linear_constraints"})
    try:
        reg.check_bounds_capabilities(b_name, b_caps)
        b_cls = reg.get_bounds(b_name)
        b_backend = b_cls()
        bounds_dict, bounds_stats = b_backend.solve_bounds(compiled)
    except NuSolError:
        bounds_dict = {}

    # 7. Build result
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
