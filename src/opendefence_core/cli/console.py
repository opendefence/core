"""CLI entrypoints for opendefence-core"""

import logging

import click

from opendefence_core import __version__
from opendefence_core.k8s_operator.app import app


LOGGER = logging.getLogger(__name__)

# Pass everything after the subcommand through to the cloudcoil application
PASSTHROUGH = {
    "ignore_unknown_options": True,
    "allow_extra_args": True,
    "allow_interspersed_args": False,
}


def _configure_logging(loglevel: int, verbose: int) -> None:
    """Apply verbose shorthand and initialize logging."""
    if verbose == 1:
        loglevel = 20
    if verbose >= 2:
        loglevel = 10
    logging.basicConfig(level=loglevel, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    LOGGER.setLevel(loglevel)


@click.group(invoke_without_command=True)
@click.version_option(version=__version__)
@click.option("-l", "--loglevel", help="Python log level, 10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR", default=30)
@click.option("-v", "--verbose", count=True, help="Shorthand for info/debug loglevel (-v/-vv)")
@click.pass_context
def opendefence_core_cli(ctx: click.Context, loglevel: int, verbose: int) -> None:
    """CLI"""
    _configure_logging(loglevel, verbose)
    if ctx.invoked_subcommand is None:
        click.echo("Do your thing")


@opendefence_core_cli.group()
def operator() -> None:
    """Kubernetes operator and CRDs for OpenDefence platform entities"""


@operator.command(context_settings=PASSTHROUGH)
@click.pass_context
def manifests(ctx: click.Context) -> None:
    """Print CRD, RBAC, and optional Deployment manifests (offline)."""
    app.main(["manifests", *ctx.args])


@operator.command(context_settings=PASSTHROUGH)
@click.pass_context
def install(ctx: click.Context) -> None:
    """Apply CRDs and runtime RBAC using the current kubeconfig."""
    app.main(["install", *ctx.args])


@operator.command(context_settings=PASSTHROUGH)
@click.pass_context
def run(ctx: click.Context) -> None:
    """Run the operator against the current cluster."""
    app.main(["run", *ctx.args])
