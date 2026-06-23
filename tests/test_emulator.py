"""Emulator: runs minimal end-to-end; contract violations map to finding IDs."""

from __future__ import annotations

from pathlib import Path

from conftest import write_project
from typer.testing import CliRunner

from langgraph_wxo.cli import EXIT_FINDINGS, EXIT_OK, app
from langgraph_wxo.config import ConnectionSpec, load_project
from langgraph_wxo.emulate import build_mock_creds, run_agent
from langgraph_wxo.templates import render_template

runner = CliRunner()

COMPILED_PY = """\
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import END, START, MessagesState, StateGraph


def create_agent(config: RunnableConfig):
    g = StateGraph(MessagesState)
    g.add_node("n", lambda s: {"messages": []})
    g.add_edge(START, "n")
    g.add_edge("n", END)
    return g.compile()
"""

NO_CONFIG_PY = """\
from langgraph.graph import END, START, MessagesState, StateGraph


def create_agent():
    g = StateGraph(MessagesState)
    g.add_node("n", lambda s: {"messages": []})
    g.add_edge(START, "n")
    g.add_edge("n", END)
    return g
"""


def test_build_mock_creds_format() -> None:
    conns = [ConnectionSpec(app_id="openai_api", type="api_key")]
    creds = build_mock_creds(conns)
    assert creds == {"openai_api_api_key": "MOCK-openai_api-api_key"}


def test_minimal_runs_end_to_end(tmp_path: Path) -> None:
    target = tmp_path / "proj"
    render_template("minimal", target, {"name": "demo", "checkpointer": "memory", "model": "x"})
    result = run_agent(load_project(target), "hello")
    assert result.ok, result.message
    assert any(m["type"] == "ai" and "echo: hello" in m["content"] for m in result.transcript)
    assert result.notices


def test_react_tools_runs_offline(tmp_path: Path) -> None:
    target = tmp_path / "proj"
    render_template("react-tools", target, {"name": "demo", "checkpointer": "memory", "model": "x"})
    result = run_agent(load_project(target), "hi")
    assert result.ok, result.message


def test_compiled_graph_is_lgwxo003(tmp_path: Path) -> None:
    write_project(tmp_path, agent_py=COMPILED_PY)
    result = run_agent(load_project(tmp_path), "hi")
    assert result.status == "contract"
    assert result.finding_id == "LGWXO003"


def test_missing_config_is_lgwxo002(tmp_path: Path) -> None:
    write_project(tmp_path, agent_py=NO_CONFIG_PY)
    result = run_agent(load_project(tmp_path), "hi")
    assert result.status == "contract"
    assert result.finding_id == "LGWXO002"


def test_run_cli_minimal(tmp_path: Path) -> None:
    target = tmp_path / "proj"
    render_template("minimal", target, {"name": "demo", "checkpointer": "memory", "model": "x"})
    result = runner.invoke(app, ["run", "--path", str(target), "--message", "hey"])
    assert result.exit_code == EXIT_OK, result.stdout
    assert "echo: hey" in result.stdout


def test_run_cli_compiled_exit_1(tmp_path: Path) -> None:
    write_project(tmp_path, agent_py=COMPILED_PY)
    result = runner.invoke(app, ["run", "--path", str(tmp_path), "--message", "hi"])
    assert result.exit_code == EXIT_FINDINGS
    assert "LGWXO003" in result.stdout
