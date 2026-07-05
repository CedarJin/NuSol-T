"""NuSol-T command-line interface (Typer).

Commands:
  validate    Validate a YAML problem document against the schema.
  resolve     Resolve extends and output canonical YAML.
  inspect     Display problem structure without solving.
  solve       Run the full solve pipeline (Phase 5+).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="nusol",
    help="NuSol-T: An Extensible Unified Framework for Food Nutrient Composition Analysis.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Show NuSol-T version."""
    from nusol import __version__

    typer.echo(f"NuSol-T v{__version__}")


@app.command()
def validate(
    path: str = typer.Argument(..., help="Path to YAML problem document"),
) -> None:
    """Validate a YAML problem document against the schema.

    Exit codes:
        0 — validation passed
        1 — config/schema error
    """
    from nusol.config.errors import ConfigError, ResourceError, SchemaValidationError
    from nusol.config.loader import ConfigLoader

    try:
        loader = ConfigLoader()
        doc = loader.load_from_path(path)
        typer.secho(
            f"Validation PASSED ✓  ({doc.problem_id})",
            fg=typer.colors.GREEN,
            bold=True,
        )
        typer.echo(f"  schema_version: {doc.schema_version}")
        typer.echo(f"  ingredients: {len(doc.ingredients)}")
        typer.echo(f"  observations: {len(doc.observations)}")
        typer.echo(f"  constraints: {len(doc.constraints)}")
        typer.echo(f"  priors: {len(doc.priors)}")
    except SchemaValidationError as e:
        typer.secho("Schema validation FAILED:", fg=typer.colors.RED, bold=True)
        typer.echo(f"  {e}")
        raise typer.Exit(code=1)
    except ResourceError as e:
        typer.secho("Resource error:", fg=typer.colors.RED, bold=True)
        typer.echo(f"  {e}")
        raise typer.Exit(code=1)
    except ConfigError as e:
        typer.secho("Config error:", fg=typer.colors.RED, bold=True)
        typer.echo(f"  {e}")
        raise typer.Exit(code=1)


@app.command()
def resolve(
    path: str = typer.Argument(..., help="Path to YAML problem document"),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output path for resolved YAML (default: stdout)",
    ),
) -> None:
    """Resolve extends and output canonical YAML.

    Shows the fully-resolved configuration with all defaults applied and
    all inheritance flattened. If --output is provided, writes to file;
    otherwise prints to stdout.
    """
    from nusol.config.errors import ConfigError, SchemaValidationError
    from nusol.config.resolver import ConfigResolver, yaml_to_canonical_string

    try:
        resolver = ConfigResolver()
        resolved_dict = resolver.resolve_to_dict(path)
        yaml_str = yaml_to_canonical_string(resolved_dict)

        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(yaml_str, encoding="utf-8")
            typer.secho(
                f"Resolved config written to {out_path}",
                fg=typer.colors.GREEN,
            )
        else:
            typer.echo(yaml_str)

    except ConfigError as e:
        typer.secho(f"Resolution failed: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(code=1)


@app.command()
def inspect(
    path: str = typer.Argument(..., help="Path to YAML problem document"),
) -> None:
    """Display a summary of the problem structure without solving."""
    from nusol.config.loader import ConfigLoader

    loader = ConfigLoader()
    doc = loader.load_from_path(path)

    typer.secho(f"Problem: {doc.problem_id}", bold=True)
    typer.echo(f"  schema:     {doc.schema_version}")
    typer.echo("")
    typer.secho("Ingredients:", bold=True)
    for ing in doc.ingredients:
        pos = ing.declaration_position
        grp = "≤2%" if ing.declaration_group.value == "two_percent_or_less" else "main"
        typer.echo(f"  [{pos}] {ing.id:20s} \"{ing.name}\"  ({grp})")
    typer.echo("")
    typer.secho("Observations:", bold=True)
    for obs in doc.observations:
        mode = "interval" if obs.interval else "exact" if obs.exact else "less_than"
        val = obs.interval or [obs.exact, obs.exact] if obs.exact else [0, obs.less_than]
        typer.echo(f"  {obs.nutrient:20s} {mode:12s} {val} {obs.unit}")
    typer.echo("")
    typer.secho("Constraints:", bold=True)
    for c in doc.constraints:
        status = "✓" if c.enabled else "✗"
        typer.echo(f"  {status} {c.id:20s} type={c.type:20s} mode={c.mode.value}")
    typer.echo("")
    typer.secho("Solver:", bold=True)
    if doc.solver.point:
        typer.echo(f"  point:  {doc.solver.point.backend.value}")
    if doc.solver.bounds:
        typer.echo(f"  bounds: {doc.solver.bounds.backend.value}")


@app.command()
def solve(
    path: str = typer.Argument(..., help="Path to YAML problem document"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Compile and show IR, do not solve",
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output path for result JSON",
    ),
) -> None:
    """Solve an ingredient estimation problem.

    Runs the full pipeline: load → resolve → build → compile → solve → output.
    """
    from nusol.api import solve as solve_api
    from nusol.compiler.compiler import compile_problem
    from nusol.config.errors import ConfigError, NuSolError
    from nusol.config.loader import ConfigLoader
    from nusol.domain.builder import build_problem

    try:
        if dry_run:
            # Load, build, compile — show structure only
            loader = ConfigLoader()
            doc = loader.load_from_path(path)
            problem = build_problem(doc)
            compiled = compile_problem(problem)

            typer.secho(f"Problem: {problem.problem_id}", bold=True)
            typer.echo(f"  Ingredients: {len(compiled.variables)}")
            typer.echo(f"  Hard constraints: {sum(1 for lc in compiled.linear_constraints if lc.mode == 'hard')}")
            typer.echo(f"  Soft constraints: {sum(1 for lc in compiled.linear_constraints if lc.mode == 'soft')}")
            typer.echo(f"  Capabilities: {compiled.required_capabilities}")
            typer.echo("")
            typer.echo("DRY-RUN: problem compiled but not solved")
            return

        result = solve_api(path)

        if result["success"]:
            typer.secho(
                f"Solve SUCCESS ✓  ({result['problem_id']})",
                fg=typer.colors.GREEN, bold=True,
            )
            typer.echo(f"  fractions:")
            for ing, frac in sorted(result["fractions"].items(),
                                     key=lambda x: x[1], reverse=True):
                lo, hi = result["bounds"].get(ing, [0, 1])
                typer.echo(f"    {ing:20s} {frac:.4f}  [{lo:.4f}, {hi:.4f}]")
            typer.echo(f"  solve_time: {result['diagnostics']['total_time_s']:.4f}s")
        else:
            typer.secho(
                f"Solve FAILED  ({result.get('error', 'unknown error')})",
                fg=typer.colors.RED, bold=True,
            )

        if output:
            out_path = Path(output)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(result, f, indent=2)
            typer.echo(f"  result written to {out_path}")

        if not result["success"]:
            raise typer.Exit(code=2)

    except NuSolError as e:
        typer.secho(f"Solve failed: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(code=2)
    except ConfigError as e:
        typer.secho(f"Config error: {e}", fg=typer.colors.RED, bold=True)
        raise typer.Exit(code=1)


def main() -> None:
    """Entry point for the nusol CLI."""
    app()


if __name__ == "__main__":
    main()
