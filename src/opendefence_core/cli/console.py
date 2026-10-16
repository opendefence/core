"""Command line entrypoint for the core operator."""

import logging
from pathlib import Path

import click

from opendefence_core import __version__
from opendefence_core.k8s_operator import render
from opendefence_core.k8s_operator.app import app as operator_app


def _configure_logging(loglevel: int, verbose: int) -> None:
    """Apply verbose shorthand and initialize logging."""
    if verbose == 1:
        loglevel = logging.INFO
    if verbose >= 2:
        loglevel = logging.DEBUG
    logging.basicConfig(level=loglevel, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@click.group()
@click.version_option(version=__version__)
@click.option(
    "-l",
    "--loglevel",
    type=int,
    default=logging.WARNING,
    show_default=True,
    help="Python log level, 10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR",
)
@click.option("-v", "--verbose", count=True, help="Shorthand for info/debug loglevel (-v/-vv)")
def opendefence_core_cli(loglevel: int, verbose: int) -> None:
    """OpenDefence core: the platform operator."""
    _configure_logging(loglevel, verbose)


@opendefence_core_cli.group()
def operator() -> None:
    """Kubernetes operator for the platform.opendefence.fi resources."""


@operator.command("run")
def operator_run() -> None:
    """Run the operator against the current cluster."""
    operator_app.main(["run"])


@operator.command("render")
@click.option("--check", is_flag=True, help="Fail if the committed files are stale instead of writing them.")
@click.option(
    "--root",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("."),
    show_default=True,
    help="Repository root.",
)
def operator_render(check: bool, root: Path) -> None:
    """Write the CRDs and the operator's deployment manifests from the operator code."""
    if check:
        stale = render.stale_files(root)
        if stale:
            raise click.ClickException(f"Out of date, run `task build:manifests`: {', '.join(map(str, stale))}")
        return
    for path in render.write_files(root):
        click.echo(f"wrote {path}")
