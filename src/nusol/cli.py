"""NuSol-T command-line interface (Typer)."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="nusol",
    help="NuSol-T: An Extensible Unified Computational Framework for Food Nutrient Composition Analysis.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Show NuSol-T version."""
    from nusol import __version__

    typer.echo(f"NuSol-T v{__version__}")


@app.command()
def validate_config(
    config_path: str = typer.Argument(..., help="Path to YAML config file"),
) -> None:
    """Validate a NuSol-T configuration file."""
    from nusol.config import ConfigLoader

    loader = ConfigLoader()
    data = loader.load(config_path)
    errors = loader.validate(data)

    if errors:
        typer.secho("Config validation FAILED:", fg=typer.colors.RED, bold=True)
        for err in errors:
            typer.echo(f"  ✗ {err}")
        raise typer.Exit(code=1)
    else:
        typer.secho("Config validation PASSED ✓", fg=typer.colors.GREEN, bold=True)
        typer.echo(f"  Run ID: {data.get('run_id', 'N/A')}")


@app.command()
def run_forward(
    config_path: str = typer.Option(
        "config/fndds_forward.yaml", "--config", "-c", help="Path to YAML config"
    ),
    fdc_id: Optional[int] = typer.Option(None, "--fdc-id", help="FDC ID of a single recipe to run"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
) -> None:
    """Run forward nutrition calculation (FNDDS validation)."""
    from nusol.config import ConfigLoader
    from nusol.data.fndds import FNDDSDataAdapter

    typer.echo(f"Loading config: {config_path}")
    loader = ConfigLoader()
    data = loader.load(config_path)

    if output_dir:
        data["reporting"]["output_dir"] = output_dir

    typer.echo(f"Loading FNDDS data...")
    adapter = FNDDSDataAdapter(data.get("data", {}))

    # TODO: Phase 1 - full forward pipeline
    typer.echo("Forward nutrition calculation — to be implemented in Phase 1")


@app.command()
def run_inverse(
    config_path: str = typer.Option(
        "config/fndds_inverse.yaml", "--config", "-c", help="Path to YAML config"
    ),
    fdc_id: Optional[int] = typer.Option(None, "--fdc-id", help="FDC ID of a single product"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
) -> None:
    """Run inverse ingredient inference."""
    from nusol.config import ConfigLoader

    typer.echo(f"Loading config: {config_path}")
    loader = ConfigLoader()
    data = loader.load(config_path)

    if output_dir:
        data["reporting"]["output_dir"] = output_dir

    typer.echo("Inverse ingredient inference — to be implemented in Phase 2-3")


@app.command()
def run_ablation(
    config_path: str = typer.Option(
        "config/fndds_inverse.yaml", "--config", "-c", help="Base config path"
    ),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory"),
) -> None:
    """Run ablation study across constraint levels G0-G7."""
    typer.echo("Ablation study — to be implemented in Phase 4")


def main() -> None:
    """Entry point for the nusol CLI."""
    app()


if __name__ == "__main__":
    main()
