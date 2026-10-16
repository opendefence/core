"""Command line interface."""

import logging
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from opendefence_core import __version__
from opendefence_core.cli import console
from opendefence_core.cli.console import opendefence_core_cli
from opendefence_core.k8s_operator import render

ROOT = Path(__file__).resolve().parents[1]
runner = CliRunner()


def test_version() -> None:
    """--version prints the package version."""
    result = runner.invoke(opendefence_core_cli, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_commands() -> None:
    """--help lists the operator command group."""
    result = runner.invoke(opendefence_core_cli, ["--help"])
    assert result.exit_code == 0
    assert "api" not in result.output
    assert "operator" in result.output


def test_operator_run_starts_application(monkeypatch: pytest.MonkeyPatch) -> None:
    """operator run runs the cloudcoil Application."""
    calls: list[list[str]] = []
    monkeypatch.setattr(console.operator_app, "main", calls.append)
    result = runner.invoke(opendefence_core_cli, ["operator", "run"])
    assert result.exit_code == 0, result.output
    assert calls == [["run"]]


def test_operator_render_check_accepts_committed_manifests() -> None:
    """The committed manifests match the operator code."""
    result = runner.invoke(opendefence_core_cli, ["operator", "render", "--check", "--root", str(ROOT)])
    assert result.exit_code == 0, result.output


def test_operator_render_writes_what_check_expects(tmp_path: Path) -> None:
    """--check fails on missing files; render writes them; --check then passes."""
    stale = runner.invoke(opendefence_core_cli, ["operator", "render", "--check", "--root", str(tmp_path)])
    assert stale.exit_code == 1
    assert "Out of date" in stale.output

    written = runner.invoke(opendefence_core_cli, ["operator", "render", "--root", str(tmp_path)])
    assert written.exit_code == 0, written.output
    assert (tmp_path / render.CRDS_PATH).is_file()
    assert (tmp_path / render.OPERATOR_PATH).is_file()

    fresh = runner.invoke(opendefence_core_cli, ["operator", "render", "--check", "--root", str(tmp_path)])
    assert fresh.exit_code == 0, fresh.output


@pytest.mark.parametrize(
    ("flags", "level"), [([], logging.WARNING), (["-v"], logging.INFO), (["-vv"], logging.DEBUG), (["-l", "40"], 40)]
)
def test_log_level_flags(monkeypatch: pytest.MonkeyPatch, flags: list[str], level: int) -> None:
    """-v and -vv select info and debug; -l sets the level directly."""
    levels: list[int] = []

    def basic_config(**kwargs: Any) -> None:
        levels.append(kwargs["level"])

    monkeypatch.setattr(logging, "basicConfig", basic_config)
    result = runner.invoke(opendefence_core_cli, [*flags, "operator", "render", "--check", "--root", str(ROOT)])
    assert result.exit_code == 0, result.output
    assert levels == [level]
