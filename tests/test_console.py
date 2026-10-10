"""Test CLI scripts"""

import asyncio

import pytest
from click.testing import CliRunner

from opendefence_core import __version__
from opendefence_core.cli.console import opendefence_core_cli


@pytest.mark.asyncio
async def test_version_cli() -> None:
    """Test the CLI parsing for default version dumping works"""
    cmd = "opendefence_core --version"
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(process.communicate(), 10)
    # Demand clean exit
    assert process.returncode == 0
    assert __version__ in stdout.decode()


@pytest.mark.asyncio
async def test_cli_output() -> None:
    """Run the entrypoint and check output"""
    cmd = "opendefence_core"
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await asyncio.wait_for(process.communicate(), 10)
    # Demand clean exit
    assert process.returncode == 0
    assert "Do your thing" in stdout.decode()


@pytest.mark.asyncio
async def test_cli_operator_manifests() -> None:
    """operator manifests prints CRD YAML without talking to a cluster."""
    cmd = "opendefence_core operator manifests --without-webhooks"
    process = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await asyncio.wait_for(process.communicate(), 15)
    assert process.returncode == 0, stderr.decode()
    output = stdout.decode()
    assert "kind: CustomResourceDefinition" in output
    assert "users.platform.opendefence.fi" in output
    assert "invites.platform.opendefence.fi" in output
    assert "userbindings.platform.opendefence.fi" in output


def test_verbose_logging_flags() -> None:
    """-v and -vv select info and debug log levels before a subcommand runs."""
    runner = CliRunner()
    info = runner.invoke(opendefence_core_cli, ["-v", "operator", "manifests", "--without-webhooks"])
    debug = runner.invoke(opendefence_core_cli, ["-vv", "operator", "manifests", "--without-webhooks"])
    assert info.exit_code == 0
    assert debug.exit_code == 0
    assert "CustomResourceDefinition" in info.output
