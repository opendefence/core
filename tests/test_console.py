"""Command line interface."""

import json
import logging
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from click.testing import CliRunner
from cloudcoil.errors import APIError

from opendefence_core import __version__, naming
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
    """--help lists the API and operator command groups."""
    result = runner.invoke(opendefence_core_cli, ["--help"])
    assert result.exit_code == 0
    assert "api" in result.output
    assert "operator" in result.output


def test_api_run_serves_app_with_uvicorn(monkeypatch: pytest.MonkeyPatch) -> None:
    """api run hands the app to uvicorn with the given options."""
    calls: list[tuple[str, dict[str, Any]]] = []

    def run(app: str, **kwargs: Any) -> None:
        calls.append((app, kwargs))

    monkeypatch.setattr(uvicorn, "run", run)
    result = runner.invoke(opendefence_core_cli, ["api", "run", "--port", "9000", "--reload", "--reload-dir", "src"])
    assert result.exit_code == 0, result.output
    assert calls == [
        ("opendefence_core.api.app:app", {"host": "0.0.0.0", "port": 9000, "reload": True, "reload_dirs": ["src"]})
    ]


def test_api_schema_prints_the_openapi_document() -> None:
    """api schema prints the document that the UI's client is generated from."""
    result = runner.invoke(opendefence_core_cli, ["api", "schema"])
    assert result.exit_code == 0, result.output
    document = json.loads(result.output)
    assert document["openapi"].startswith("3.")
    assert "/api/v3/certificates/csr" in document["paths"]


def test_api_invite_prints_the_code_it_created(monkeypatch: pytest.MonkeyPatch) -> None:
    """api invite creates the invite and prints nothing but its code."""
    created: list[tuple[str, str]] = []

    async def create_admin_invite(role: str, display_name: str) -> str:
        created.append((role, display_name))
        return "CODE"

    monkeypatch.setattr(console, "create_admin_invite", create_admin_invite)
    result = runner.invoke(opendefence_core_cli, ["api", "invite"])
    assert result.exit_code == 0, result.output
    assert result.output == "CODE\n"
    assert created == [(naming.SUPERADMIN_ROLE, naming.SUPERADMIN_ROLE)]


def test_api_invite_names_the_role_as_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neither name is derived from the other, so two spellings stay two roles."""
    created: list[tuple[str, str]] = []

    async def create_admin_invite(role: str, display_name: str) -> str:
        created.append((role, display_name))
        return "CODE"

    monkeypatch.setattr(console, "create_admin_invite", create_admin_invite)
    result = runner.invoke(
        opendefence_core_cli, ["api", "invite", "--role", "group-admin", "--display-name", "Group admin"]
    )
    assert result.exit_code == 0, result.output
    assert created == [("group-admin", "Group admin")]


@pytest.mark.parametrize("name", ["Superadmin", "super admin", "-admin", "a" * 64])
def test_api_invite_rejects_an_impossible_role_name(name: str) -> None:
    """A name Kubernetes would refuse fails before the command reaches the cluster."""
    result = runner.invoke(opendefence_core_cli, ["api", "invite", "--role", name])
    assert result.exit_code == 2
    assert "lowercase letters" in result.output


def test_api_invite_reports_a_rejected_invite(monkeypatch: pytest.MonkeyPatch) -> None:
    """A Kubernetes error becomes a message rather than a traceback."""

    async def create_admin_invite(role: str, display_name: str) -> str:
        _ = role, display_name
        raise APIError("denied")

    monkeypatch.setattr(console, "create_admin_invite", create_admin_invite)
    result = runner.invoke(opendefence_core_cli, ["api", "invite"])
    assert result.exit_code == 1
    assert "Creating the invite failed" in result.output


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
    monkeypatch.setattr(console, "init_logging", levels.append)
    result = runner.invoke(opendefence_core_cli, [*flags, "operator", "render", "--check", "--root", str(ROOT)])
    assert result.exit_code == 0, result.output
    assert levels == [level]
