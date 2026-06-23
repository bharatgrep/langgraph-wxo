"""Direct tests of the AST analysis layer."""

from __future__ import annotations

from pathlib import Path

from conftest import write_project

from langgraph_wxo.analyze import FactoryAnalysis, analyze_factory
from langgraph_wxo.config import load_project


def _analyze(root: Path) -> FactoryAnalysis:
    return analyze_factory(load_project(root))


def test_good_factory(good_project: Path) -> None:
    a = _analyze(good_project)
    assert a.factory_found
    assert a.has_runnable_config_param
    assert not a.returns_compiled
    assert a.returns_state_graph is True
    assert any(r.key == "openai_api_api_key" for r in a.credential_reads)


def test_compiled_factory(tmp_path: Path) -> None:
    write_project(
        tmp_path,
        agent_py=(
            "from langchain_core.runnables.config import RunnableConfig\n"
            "from langgraph.graph import StateGraph\n\n\n"
            "def create_agent(config: RunnableConfig):\n"
            "    g = StateGraph(dict)\n"
            "    return g.compile()\n"
        ),
    )
    a = _analyze(tmp_path)
    assert a.returns_compiled


def test_missing_config_factory(tmp_path: Path) -> None:
    write_project(
        tmp_path,
        agent_py=(
            "from langgraph.graph import StateGraph\n\n\n"
            "def create_agent():\n"
            "    return StateGraph(dict)\n"
        ),
    )
    a = _analyze(tmp_path)
    assert a.factory_found
    assert not a.has_runnable_config_param


def test_getenv_credential_read(tmp_path: Path) -> None:
    write_project(
        tmp_path,
        agent_py=(
            "import os\n"
            "from langchain_core.runnables.config import RunnableConfig\n"
            "from langgraph.graph import StateGraph\n\n\n"
            "def create_agent(config: RunnableConfig) -> StateGraph:\n"
            "    token = os.getenv('openai_api_api_key')\n"
            "    return StateGraph(dict)\n"
        ),
    )
    a = _analyze(tmp_path)
    assert any(r.key == "openai_api_api_key" for r in a.credential_reads)
