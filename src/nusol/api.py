"""NuSol-T public API — ``solve(yaml_path)`` is the single entry point.

Usage::

    import nusol
    result = nusol.solve("problem.yaml")
"""

from __future__ import annotations

import hashlib
import platform
import subprocess
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nusol.backends.base import SolveStats
from nusol.backends.registry import get_backend_registry
from nusol.compiler.compiler import compile_problem
from nusol.compiler.ir import CompiledProblem
from nusol.config.errors import ConfigError, NuSolError, UnsupportedConstraintError
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
    resolved_dict = doc.model_dump(mode="json")

    # 2. Build domain model from resolved document
    problem = build_problem(doc, base_dir=path.resolve().parent)

    # 3. Compile to IR
    compiled = compile_problem(problem)

    # 4. Read solver config from resolved YAML
    reg = get_backend_registry()
    solver_spec = doc.solver

    # 5. Solve point (if configured)
    fractions: dict[str, float] = {}
    point_stats = None
    if solver_spec.point:
        point_name = solver_spec.point.backend.value
        point_opts = solver_spec.point.options
        reg.check_point_capabilities(point_name, compiled.required_capabilities)
        p_cls = reg.get_point(point_name)
        p_backend = p_cls(options=point_opts)  # type: ignore[call-arg]
        try:
            fractions, point_stats = p_backend.solve_point(compiled)
        except NuSolError as exc:
            point_stats = SolveStats(False, "error", str(exc))

    # 6. Solve bounds only when configured in YAML.
    bounds_dict: dict[str, tuple[float, float]] = {}
    bounds_stats = None
    if solver_spec.bounds is not None:
        b_name = solver_spec.bounds.backend.value
        bounds_problem = _problem_for_bounds(
            compiled,
            solver_spec.bounds.feasible_region,
            solver_spec.bounds.slack_budgets,
        )
        b_caps = frozenset({"continuous", "linear_constraints"})
        try:
            reg.check_bounds_capabilities(b_name, b_caps)
            b_cls = reg.get_bounds(b_name)
            b_backend = b_cls()
            bounds_dict, bounds_stats = b_backend.solve_bounds(bounds_problem)
        except NuSolError as exc:
            bounds_stats = SolveStats(False, "error", str(exc))

    # 7. Build result
    t_end = time.perf_counter()

    diagnostics = {
        "point": point_stats.as_dict() if point_stats else {"success": False, "status": "error"},
        "bounds": bounds_stats.as_dict() if bounds_stats else {"success": False, "status": "error"},
        "n_variables": compiled.n_variables,
        "n_constraints": len(compiled.linear_constraints),
        "total_time_s": t_end - t_start,
    }

    configured_stats = [
        stats
        for configured, stats in (
            (solver_spec.point is not None, point_stats),
            (solver_spec.bounds is not None, bounds_stats),
        )
        if configured
    ]
    success = bool(configured_stats) and all(
        stats is not None and stats.success for stats in configured_stats
    )
    result: dict[str, Any] = {
        "success": success,
        "status": "optimal" if success else "error",
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
            resources=[problem.composition.resource_metadata]
            if problem.composition.resource_metadata else [],
            feasible_region=(
                solver_spec.bounds.feasible_region if solver_spec.bounds else None
            ),
        ),
    }

    if not result["success"]:
        failed = next(
            (stats for stats in configured_stats if stats is not None and not stats.success),
            None,
        )
        result["error"] = failed.message if failed else "Configured solver did not run"

    return result


def _build_manifest(
    problem_id: str,
    yaml_path: str,
    resolved_dict: dict[str, Any],
    diagnostics: dict[str, Any],
    fractions: dict[str, float],
    resources: list[dict[str, str]],
    feasible_region: str | None,
) -> dict[str, Any]:
    """Build run manifest with reproducibility information."""
    now = datetime.now(UTC)

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
        "resources": resources,
        "solver": {
            "point": diagnostics.get("point", {}),
            "bounds": diagnostics.get("bounds", {}),
            "bounds_feasible_region": feasible_region,
        },
    }
    return manifest


def _problem_for_bounds(
    problem: CompiledProblem,
    feasible_region: str,
    slack_budgets: dict[str, float],
) -> CompiledProblem:
    """Build the bounds feasible region declared by YAML."""
    if feasible_region == "hard_constraints_only":
        return problem

    known_sources = {
        constraint.source_id
        for constraint in problem.linear_constraints
        if constraint.mode == "soft" and constraint.source_id is not None
    }
    quadratic_sources = {
        penalty.source_id
        for penalty in problem.quadratic_penalties
        if penalty.source_id is not None
    }
    unknown = set(slack_budgets) - known_sources - quadratic_sources
    if unknown:
        raise ConfigError(
            f"Slack budgets reference unknown soft constraints: {sorted(unknown)}"
        )
    nonlinear = set(slack_budgets) & quadratic_sources
    if nonlinear:
        raise UnsupportedConstraintError(
            "HiGHS bounds cannot linearize budgets for quadratic constraints: "
            f"{sorted(nonlinear)}"
        )

    constraints = []
    for constraint in problem.linear_constraints:
        budget = slack_budgets.get(constraint.source_id or "")
        if constraint.mode == "soft" and budget is not None:
            constraints.append(
                replace(
                    constraint,
                    lower=(
                        constraint.lower - budget
                        if constraint.lower is not None else None
                    ),
                    upper=(
                        constraint.upper + budget
                        if constraint.upper is not None else None
                    ),
                    mode="hard",
                )
            )
        else:
            constraints.append(constraint)
    return replace(problem, linear_constraints=tuple(constraints))


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
