"""Command line entrypoint for the core operator and REST API."""

import json
import logging
from pathlib import Path

import click
import uvicorn

from lib_opendefence_core.logging import init_logging
from opendefence_core import __version__, config
from opendefence_core.k8s_operator import render
from opendefence_core.k8s_operator.app import app as operator_app
from opendefence_core.k8s_operator.config import get_operator_config


def _configure_logging(loglevel: int, verbose: int) -> None:
    """Apply verbose shorthand and initialize logging."""
    if verbose == 1:
        loglevel = logging.INFO
    if verbose >= 2:
        loglevel = logging.DEBUG
    init_logging(loglevel)


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
    """OpenDefence core: the platform operator and REST API."""
    _configure_logging(loglevel, verbose)


@opendefence_core_cli.group()
def api() -> None:
    """REST API for enrollment and certificate downloads."""


@api.command("run")
@click.option("--host", default="0.0.0.0", show_default=True, help="Address to listen on.")  # nosec B104
@click.option("--port", type=int, default=8000, show_default=True, help="Port to listen on.")
@click.option("--reload", is_flag=True, help="Restart when the source changes (development).")
@click.option(
    "--reload-dir",
    "reload_dirs",
    multiple=True,
    type=click.Path(file_okay=False),
    help="Directory to watch with --reload; repeatable.",
)
def api_run(host: str, port: int, reload: bool, reload_dirs: tuple[str, ...]) -> None:
    """Serve the REST API with uvicorn."""
    uvicorn.run(
        "opendefence_core.api.app:app",
        host=host,
        port=port,
        reload=reload,
        reload_dirs=list(reload_dirs) or None,
    )


@api.command("schema")
def api_schema() -> None:
    """Print the OpenAPI document."""
    from opendefence_core.api.app import app as api_app  # noqa: PLC0415

    click.echo(json.dumps(api_app.openapi(), indent=2, ensure_ascii=False))


@opendefence_core_cli.group()
def operator() -> None:
    """Kubernetes operator for the platform.opendefence.fi resources."""


@operator.command("run")
def operator_run() -> None:
    """Run the operator against the current cluster."""
    config.get_core_config()
    get_operator_config()
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
