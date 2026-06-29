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


def test_infers_agent_py_when_entrypoint_missing(tmp_path: Path) -> None:
    write_project(
        tmp_path,
        agent_yaml=(
            "spec_version: v1\nkind: native\nname: demo_agent\ndescription: Placeholder.\n"
        ),
    )
    a = _analyze(tmp_path)
    assert a.inferred_entrypoint
    assert a.factory_found
    assert a.factory_name == "create_agent"


def test_config_credential_read_from_constant_fstring(tmp_path: Path) -> None:
    write_project(
        tmp_path,
        agent_py=(
            "from langchain_core.runnables.config import RunnableConfig\n"
            "from langgraph.graph import StateGraph\n\n"
            "APP_ID = 'demo_api'\n"
            "CREDENTIAL_KEY = f'{APP_ID}_api_key'\n\n"
            "def create_agent(config: RunnableConfig) -> StateGraph:\n"
            "    credentials = config.get('configurable', {}).get('credentials', {})\n"
            "    api_key = credentials.get(CREDENTIAL_KEY)\n"
            "    return StateGraph(dict)\n"
        ),
    )
    a = _analyze(tmp_path)
    assert any(r.key == "demo_api_api_key" and r.source == "config" for r in a.credential_reads)


def test_custom_state_and_wxo_platform_access(tmp_path: Path) -> None:
    write_project(
        tmp_path,
        agent_py=(
            "from typing import TypedDict\n"
            "from langchain_core.runnables.config import RunnableConfig\n"
            "from langgraph.graph import StateGraph\n"
            "from ibm_watsonx_orchestrate.run import connections\n\n"
            "class AgentState(TypedDict):\n"
            "    messages: list[str]\n"
            "    turn_count: int\n\n"
            "def create_agent(config: RunnableConfig) -> StateGraph:\n"
            "    return StateGraph(AgentState)\n"
        ),
    )
    a = _analyze(tmp_path)
    assert a.custom_state_fields == ["turn_count"]
    assert a.wxo_platform_access
