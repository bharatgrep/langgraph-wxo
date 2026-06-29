"""Regression coverage for placeholder manifests plus real LangGraph source."""

from __future__ import annotations

from pathlib import Path

from conftest import finding_ids, write_project

PLACEHOLDER_YAML = """\
spec_version: v1
kind: native
name: demo_agent
description: SaaS placeholder for a LangGraph diagnostic test.
instructions: Echo messages.
llm: watsonx/ibm/granite-3-8b-instruct
style: default
tools: []
"""

PLACEHOLDER_WITH_CONNECTION_YAML = (
    PLACEHOLDER_YAML
    + """\
connections:
  - app_id: demo_api
    type: api_key
"""
)

BASE_IMPORTS = """\
from typing import TypedDict

from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph


class AgentState(TypedDict):
    messages: list[str]
"""


def _ids(tmp_path: Path, *, agent_py: str, requirements: str = "langgraph>=0.6.0\n") -> list[str]:
    tmp_path.mkdir()
    write_project(
        tmp_path,
        agent_yaml=PLACEHOLDER_YAML,
        agent_py=agent_py,
        requirements=requirements,
    )
    ids = finding_ids(tmp_path)
    assert "LGWXO015" in ids
    return ids


def test_placeholder_compile_scenario_distinguishes_broken(tmp_path: Path) -> None:
    working_py = (
        BASE_IMPORTS
        + """\


def create_agent(config: RunnableConfig) -> StateGraph:
    return StateGraph(AgentState)
"""
    )
    broken_py = (
        BASE_IMPORTS
        + """\


def create_agent(config: RunnableConfig):
    return StateGraph(AgentState).compile()
"""
    )

    assert "LGWXO003" not in _ids(tmp_path / "working", agent_py=working_py)
    assert "LGWXO003" in _ids(tmp_path / "broken", agent_py=broken_py)


def test_placeholder_runnable_config_scenario_distinguishes_broken(tmp_path: Path) -> None:
    working_py = (
        BASE_IMPORTS
        + """\


def create_agent(config: RunnableConfig) -> StateGraph:
    return StateGraph(AgentState)
"""
    )
    broken_py = (
        BASE_IMPORTS.replace("from langchain_core.runnables.config import RunnableConfig\n", "")
        + """\


def create_agent() -> StateGraph:
    return StateGraph(AgentState)
"""
    )

    assert "LGWXO002" not in _ids(tmp_path / "working", agent_py=working_py)
    assert "LGWXO002" in _ids(tmp_path / "broken", agent_py=broken_py)


def test_placeholder_version_scenario_distinguishes_broken(tmp_path: Path) -> None:
    agent_py = (
        BASE_IMPORTS
        + """\


def create_agent(config: RunnableConfig) -> StateGraph:
    return StateGraph(AgentState)
"""
    )

    assert "LGWXO020" not in _ids(
        tmp_path / "working",
        agent_py=agent_py,
        requirements="langgraph>=0.6.0\nlangchain-core>=0.3\n",
    )
    assert "LGWXO020" in _ids(
        tmp_path / "broken",
        agent_py=agent_py,
        requirements="langgraph==0.2.76\nlangchain-core>=0.2,<0.3\n",
    )


def test_placeholder_credentials_scenario_distinguishes_broken(tmp_path: Path) -> None:
    working_py = (
        BASE_IMPORTS
        + """\

APP_ID = "demo_api"
CREDENTIAL_KEY = f"{APP_ID}_api_key"


def create_agent(config: RunnableConfig) -> StateGraph:
    credentials = config.get("configurable", {}).get("credentials", {})
    api_key = credentials.get(CREDENTIAL_KEY)
    _ = api_key
    return StateGraph(AgentState)
"""
    )
    broken_py = (
        BASE_IMPORTS
        + """\
import os

from dotenv import load_dotenv

ENV_KEY = "DEMO_API_KEY"
load_dotenv()


def create_agent(config: RunnableConfig) -> StateGraph:
    api_key = os.getenv(ENV_KEY)
    _ = api_key
    return StateGraph(AgentState)
"""
    )

    (tmp_path / "working").mkdir()
    write_project(
        tmp_path / "working",
        agent_yaml=PLACEHOLDER_WITH_CONNECTION_YAML,
        agent_py=working_py,
    )
    working_ids = finding_ids(tmp_path / "working")
    assert "LGWXO030" not in working_ids
    assert "LGWXO032" not in working_ids

    broken_ids = _ids(tmp_path / "broken", agent_py=broken_py)
    assert {"LGWXO030", "LGWXO033"} <= set(broken_ids)


def test_placeholder_state_scenario_distinguishes_broken(tmp_path: Path) -> None:
    working_py = (
        BASE_IMPORTS
        + """\


def create_agent(config: RunnableConfig) -> StateGraph:
    return StateGraph(AgentState)
"""
    )
    broken_py = (
        BASE_IMPORTS
        + """\
    turn_count: int


def create_agent(config: RunnableConfig) -> StateGraph:
    return StateGraph(AgentState)
"""
    )

    assert "LGWXO040" not in _ids(tmp_path / "working", agent_py=working_py)
    assert "LGWXO040" in _ids(tmp_path / "broken", agent_py=broken_py)


def test_placeholder_isolation_scenario_distinguishes_broken(tmp_path: Path) -> None:
    working_py = (
        BASE_IMPORTS
        + """\


def internal_tool(text: str) -> str:
    return text


def create_agent(config: RunnableConfig) -> StateGraph:
    return StateGraph(AgentState)
"""
    )
    broken_py = (
        BASE_IMPORTS
        + """\
from ibm_watsonx_orchestrate.run import connections


def create_agent(config: RunnableConfig) -> StateGraph:
    _ = connections
    return StateGraph(AgentState)
"""
    )

    assert "LGWXO053" not in _ids(tmp_path / "working", agent_py=working_py)
    assert "LGWXO053" in _ids(tmp_path / "broken", agent_py=broken_py)
