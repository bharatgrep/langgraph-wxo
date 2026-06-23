"""Shared test helpers: build valid/invalid project trees on disk."""

from __future__ import annotations

from pathlib import Path

import pytest

from langgraph_wxo.config import load_project
from langgraph_wxo.validate import run_all

# A factory that satisfies the whole contract: accepts RunnableConfig, returns an
# uncompiled StateGraph, and reads its credential under the injected key.
GOOD_AGENT_PY = """\
import os

from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph


def create_agent(config: RunnableConfig) -> StateGraph:
    api_key = os.environ["openai_api_api_key"]
    workflow = StateGraph(dict)
    return workflow
"""

GOOD_AGENT_YAML = """\
spec_version: v1
kind: agent
name: demo_agent
description: A demo agent for tests.
framework: langgraph
deployment:
  code_bundle:
    entrypoint: agent:create_agent
checkpointer:
  type: memory
connections:
  - app_id: openai_api
    type: api_key
"""

GOOD_REQUIREMENTS = "langgraph>=0.6.0\nlangchain-core>=0.3\n"


def write_project(
    root: Path,
    *,
    agent_yaml: str | None = GOOD_AGENT_YAML,
    agent_py: str | None = GOOD_AGENT_PY,
    requirements: str | None = GOOD_REQUIREMENTS,
) -> Path:
    """Write a project tree under ``root``; pass ``None`` to omit a file."""
    if agent_yaml is not None:
        (root / "agent.yaml").write_text(agent_yaml, encoding="utf-8")
    if agent_py is not None:
        (root / "agent.py").write_text(agent_py, encoding="utf-8")
    if requirements is not None:
        (root / "requirements.txt").write_text(requirements, encoding="utf-8")
    return root


@pytest.fixture
def good_project(tmp_path: Path) -> Path:
    return write_project(tmp_path)


def finding_ids(root: Path, *, strict: bool = False) -> list[str]:
    """Run validation on ``root`` and return the finding IDs."""
    report = run_all(load_project(root), strict=strict)
    return [f.id for f in report.findings]
