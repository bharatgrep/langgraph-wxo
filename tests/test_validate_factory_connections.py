"""Factory (001–005) and connection (030–032) rules + strict mode."""

from __future__ import annotations

from pathlib import Path

from conftest import GOOD_AGENT_PY, GOOD_AGENT_YAML, finding_ids, write_project

from langgraph_wxo.config import load_project
from langgraph_wxo.validate import Severity, run_all

COMPILED_PY = """\
from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph


def create_agent(config: RunnableConfig) -> StateGraph:
    workflow = StateGraph(dict)
    return workflow.compile()
"""

NO_CONFIG_PY = """\
from langgraph.graph import StateGraph


def create_agent():
    return StateGraph(dict)
"""

IMPORT_SIDE_EFFECT_PY = """\
import requests

from langchain_core.runnables.config import RunnableConfig
from langgraph.graph import StateGraph

requests.get("https://example.com")


def create_agent(config: RunnableConfig) -> StateGraph:
    return StateGraph(dict)
"""


def test_lgwxo001_factory_missing(tmp_path: Path) -> None:
    write_project(tmp_path, agent_py="x = 1\n")
    assert "LGWXO001" in finding_ids(tmp_path)


def test_lgwxo002_missing_runnable_config(tmp_path: Path) -> None:
    write_project(tmp_path, agent_py=NO_CONFIG_PY)
    assert "LGWXO002" in finding_ids(tmp_path)


def test_lgwxo003_compiled_graph(tmp_path: Path) -> None:
    write_project(tmp_path, agent_py=COMPILED_PY)
    assert "LGWXO003" in finding_ids(tmp_path)


def test_lgwxo005_import_side_effect(tmp_path: Path) -> None:
    write_project(tmp_path, agent_py=IMPORT_SIDE_EFFECT_PY)
    assert "LGWXO005" in finding_ids(tmp_path)


def test_lgwxo031_credential_mismatch(tmp_path: Path) -> None:
    py = GOOD_AGENT_PY.replace('os.environ["openai_api_api_key"]', 'os.environ["OPENAI_API_KEY"]')
    write_project(tmp_path, agent_py=py)
    assert "LGWXO031" in finding_ids(tmp_path)


def test_lgwxo030_undeclared_credential(tmp_path: Path) -> None:
    # Drop the whole trailing connections block, leaving none declared.
    yaml = GOOD_AGENT_YAML[: GOOD_AGENT_YAML.index("connections:")]
    py = GOOD_AGENT_PY.replace(
        'os.environ["openai_api_api_key"]', 'os.environ["SOME_SECRET_TOKEN"]'
    )
    write_project(tmp_path, agent_yaml=yaml, agent_py=py)
    ids = finding_ids(tmp_path)
    assert "LGWXO030" in ids


def test_lgwxo032_unused_connection(tmp_path: Path) -> None:
    py = GOOD_AGENT_PY.replace('    api_key = os.environ["openai_api_api_key"]\n', "")
    write_project(tmp_path, agent_py=py)
    assert "LGWXO032" in finding_ids(tmp_path)


def test_strict_promotes_warnings(tmp_path: Path) -> None:
    write_project(tmp_path, requirements="langgraph>=0.6.0\nlangchain-ibm\n")
    report = run_all(load_project(tmp_path), strict=True)
    # LGWXO022 (unpinned, normally warning) must now be an error.
    assert any(f.id == "LGWXO022" and f.severity is Severity.ERROR for f in report.findings)
