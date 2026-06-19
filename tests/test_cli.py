"""CLI exit codes and help via Typer's CliRunner."""

from __future__ import annotations

import json
from pathlib import Path

from conftest import GOOD_AGENT_YAML, write_project
from typer.testing import CliRunner

from langgraph_wxo.cli import EXIT_FINDINGS, EXIT_OK, app
from langgraph_wxo.version import __version__

runner = CliRunner()


def test_version_flag() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == EXIT_OK
    assert __version__ in result.stdout


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == EXIT_OK
    for cmd in ("validate", "doctor", "check-env"):
        assert cmd in result.stdout


def test_validate_good_project(good_project: Path) -> None:
    result = runner.invoke(app, ["validate", "--path", str(good_project)])
    assert result.exit_code == EXIT_OK
    assert "valid" in result.stdout


def test_validate_bad_project_exit_1(tmp_path: Path) -> None:
    yaml = GOOD_AGENT_YAML.replace("kind: agent", "kind: tool")
    write_project(tmp_path, agent_yaml=yaml)
    result = runner.invoke(app, ["validate", "--path", str(tmp_path)])
    assert result.exit_code == EXIT_FINDINGS
    assert "LGWXO011" in result.stdout


def test_validate_json_output(good_project: Path) -> None:
    result = runner.invoke(app, ["validate", "--path", str(good_project), "--json"])
    assert result.exit_code == EXIT_OK
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert "findings" in payload


def test_doctor_alias(good_project: Path) -> None:
    result = runner.invoke(app, ["doctor", "--path", str(good_project)])
    assert result.exit_code == EXIT_OK


def test_validate_missing_project(tmp_path: Path) -> None:
    result = runner.invoke(app, ["validate", "--path", str(tmp_path / "nope")])
    assert result.exit_code == EXIT_FINDINGS


def test_check_env_runs() -> None:
    result = runner.invoke(app, ["check-env"])
    assert result.exit_code == EXIT_OK
    assert "Python" in result.stdout


def test_check_env_json() -> None:
    result = runner.invoke(app, ["check-env", "--json"])
    payload = json.loads(result.stdout)
    assert payload["python"]["ok"] is True
    assert payload["target_spec"] == "v1"
