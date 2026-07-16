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

import numpy as np

from nusol.backends.base import SolveStats
from nusol.backends.registry import get_backend_registry
from nusol.compiler.compiler import compile_problem
from nusol.compiler.ir import CompiledProblem
from nusol.config.errors import ConfigError, NuSolError, UnsupportedConstraintError
from nusol.config.resolver import ConfigResolver, yaml_to_canonical_string
from nusol.domain.builder import build_problem
from nusol.results.schema import SolveResult


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

    # 7. Compute per-constraint diagnostics
    constraint_diagnostics = _compute_diagnostics(compiled, fractions)
    observation_diagnostics = _compute_observation_diagnostics(
        constraint_diagnostics
    )
    prior_contributions = [
        item for item in constraint_diagnostics
        if item.get("source_id") in problem.prior_ids
    ]

    # 8. Build result
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
        "bounds": _format_bounds(
            bounds_dict,
            problem.ingredient_ids,
            solver_spec.bounds,
        ),
        "diagnostics": diagnostics,
        "constraint_diagnostics": constraint_diagnostics,
        "observation_diagnostics": observation_diagnostics,
        "prior_contributions": prior_contributions,
        "manifest": _build_manifest(
            problem.problem_id, str(path), resolved_dict,
            diagnostics, fractions,
            resources=[problem.composition.resource_metadata]
            if problem.composition.resource_metadata else [],
            feasible_region=(
                solver_spec.bounds.feasible_region if solver_spec.bounds else None
            ),
            priors=[
                {
                    "id": prior_id,
                    **problem.prior_configs.get(prior_id, {}),
                }
                for prior_id in problem.prior_ids
            ],
        ),
    }

    if not result["success"]:
        failed = next(
            (stats for stats in configured_stats if stats is not None and not stats.success),
            None,
        )
        result["error"] = failed.message if failed else "Configured solver did not run"

    return SolveResult.model_validate(result).model_dump(mode="json", exclude_none=True)


def _compute_observation_diagnostics(
    constraint_diagnostics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group nutrient interval IR diagnostics into nutrient-level diagnostics."""
    grouped: dict[str, dict[str, Any]] = {}
    for item in constraint_diagnostics:
        constraint_id = item.get("constraint_id", "")
        if not isinstance(constraint_id, str):
            continue
        if constraint_id.startswith("nu_hi_"):
            nutrient = constraint_id.removeprefix("nu_hi_")
            entry = grouped.setdefault(nutrient, {"nutrient": nutrient})
            entry["predicted"] = item.get("value")
            entry["upper"] = item.get("upper")
            entry["upper_violation"] = item.get("raw_violation", 0.0)
            entry["source_id"] = item.get("source_id")
        elif constraint_id.startswith("nu_lo_"):
            nutrient = constraint_id.removeprefix("nu_lo_")
            entry = grouped.setdefault(nutrient, {"nutrient": nutrient})
            value = item.get("value")
            if isinstance(value, int | float):
                entry["predicted"] = round(-float(value), 6)
            upper = item.get("upper")
            if isinstance(upper, int | float):
                entry["lower"] = round(-float(upper), 6)
            entry["lower_violation"] = item.get("raw_violation", 0.0)
            entry["source_id"] = item.get("source_id")
        elif constraint_id.startswith("nu_eq_"):
            nutrient = constraint_id.removeprefix("nu_eq_")
            entry = grouped.setdefault(nutrient, {"nutrient": nutrient})
            entry["predicted"] = item.get("value")
            entry["lower"] = item.get("lower")
            entry["upper"] = item.get("upper")
            entry["lower_violation"] = item.get("raw_violation", 0.0)
            entry["upper_violation"] = item.get("raw_violation", 0.0)
            entry["source_id"] = item.get("source_id")

    result = []
    for _, entry in sorted(grouped.items()):
        lower_violation = float(entry.get("lower_violation", 0.0) or 0.0)
        upper_violation = float(entry.get("upper_violation", 0.0) or 0.0)
        entry["raw_violation"] = round(max(lower_violation, upper_violation), 6)
        result.append(entry)
    return result


def _build_manifest(
    problem_id: str,
    yaml_path: str,
    resolved_dict: dict[str, Any],
    diagnostics: dict[str, Any],
    fractions: dict[str, float],
    resources: list[dict[str, str]],
    feasible_region: str | None,
    priors: list[dict[str, Any]],
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
        "priors": priors,
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


def _compute_diagnostics(
    compiled: CompiledProblem,
    fractions: dict[str, float],
) -> list[dict[str, Any]]:
    """Compute per-constraint diagnostics from solved fractions.

    For each linear constraint, computes the actual value, residual,
    slack, and weighted penalty contribution.
    """
    n = compiled.n_variables
    ing_ids = list(compiled.ingredient_ids)
    x = [fractions.get(iid, 0.0) for iid in ing_ids]
    if not x:
        return []

    result: list[dict[str, Any]] = []
    for lc in compiled.linear_constraints:
        coeff = lc.coefficients
        if coeff.shape[0] != n:
            continue
        value = float(np.dot(coeff, x[:n]))

        lower = lc.lower
        upper = lc.upper
        slack = 0.0
        raw_violation = 0.0

        if lower is not None and value < lower:
            raw_violation = max(raw_violation, lower - value)
        if upper is not None and value > upper:
            raw_violation = max(raw_violation, value - upper)
        if lc.mode == "soft":
            slack = raw_violation

        weighted_penalty = lc.weight * slack * slack if lc.mode == "soft" else 0.0

        result.append({
            "constraint_id": lc.id,
            "source_id": lc.source_id,
            "type": "linear_constraint",
            "mode": lc.mode,
            "weight": lc.weight,
            "value": round(value, 6),
            "lower": lower,
            "upper": upper,
            "raw_violation": round(raw_violation, 6),
            "slack": round(slack, 6),
            "weighted_penalty": round(weighted_penalty, 6),
        })

    x_arr = np.array(x[:n])
    for penalty in compiled.quadratic_penalties:
        value = float(
            x_arr @ penalty.quadratic @ x_arr
            + penalty.linear @ x_arr
            + penalty.constant
        )
        weighted_penalty = penalty.weight * value
        result.append({
            "constraint_id": penalty.id,
            "source_id": penalty.source_id,
            "type": "quadratic_penalty",
            "mode": "soft",
            "weight": penalty.weight,
            "value": round(value, 6),
            "lower": 0.0,
            "upper": 0.0,
            "raw_violation": round(max(0.0, value), 6),
            "slack": round(max(0.0, value), 6),
            "weighted_penalty": round(weighted_penalty, 6),
        })

    return result


def _format_bounds(
    bounds_dict: dict[str, tuple[float, float]],
    ingredient_ids: list[str],
    bounds_spec,
) -> dict[str, Any]:
    """Format bounds output with explicit type information.

    Distinguishes ``hard_feasible_bounds`` (only hard constraints) from
    ``slack_budget_bounds`` (soft constraints tightened by budget).
    """
    if bounds_dict is None or bounds_spec is None:
        return {}

    region = getattr(bounds_spec, "feasible_region", "hard_constraints_only")
    if region == "explicit_slack_budget":
        bounds_type = "slack_budget_bounds"
    else:
        bounds_type = "hard_feasible_bounds"

    return {
        "type": bounds_type,
        "feasible_region": region,
        "values": {
            ing: list(bounds_dict.get(ing, (0.0, 1.0)))
            for ing in ingredient_ids
        },
    }


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
