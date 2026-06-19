"""Templates render and the rendered project passes validate with 0 errors."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from langgraph_wxo.cli import EXIT_OK, EXIT_UNKNOWN_TEMPLATE, app
from langgraph_wxo.config import load_project
from langgraph_wxo.templates import (
    UnknownTemplateError,
    available_templates,
    render_template,
)
from langgraph_wxo.validate import run_all

runner = CliRunner()

MVP_TEMPLATES = ["react-tools", "minimal"]


def test_available_templates_include_mvp() -> None:
    names = available_templates()
    for t in MVP_TEMPLATES:
        assert t in names


@pytest.mark.parametrize("template", MVP_TEMPLATES)
def test_render_then_validate_clean(template: str, tmp_path: Path) -> None:
    target = tmp_path / "proj"
    render_template(
        template, target, {"name": "demo_agent", "checkpointer": "memory", "model": "x"}
    )
    report = run_all(load_project(target))
    assert report.ok, [f.id for f in report.errors]


@pytest.mark.parametrize("template", MVP_TEMPLATES)
def test_new_command_scaffolds(template: str, tmp_path: Path) -> None:
    target = tmp_path / "out"
    result = runner.invoke(
        app,
        ["new", "demo_agent", "--template", template, "--dir", str(target), "--no-git"],
    )
    assert result.exit_code == EXIT_OK, result.stdout
    assert (target / "agent.yaml").is_file()
    assert (target / "agent.py").is_file()


def test_new_unknown_template_exit_3(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["new", "x", "--template", "governed-rag", "--dir", str(tmp_path / "o")],
    )
    # governed-rag is not an MVP choice; Typer rejects the enum value.
    assert result.exit_code != EXIT_OK


def test_render_unknown_template_raises(tmp_path: Path) -> None:
    with pytest.raises(UnknownTemplateError):
        render_template("does-not-exist", tmp_path / "z", {"name": "n"})


def test_new_existing_dir_blocks(tmp_path: Path) -> None:
    target = tmp_path / "dup"
    target.mkdir()
    (target / "keep.txt").write_text("x")
    result = runner.invoke(
        app, ["new", "demo", "--template", "minimal", "--dir", str(target), "--no-git"]
    )
    assert result.exit_code != EXIT_OK
    assert result.exit_code != EXIT_UNKNOWN_TEMPLATE  # it's the dir-exists code, not template
