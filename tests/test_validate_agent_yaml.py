"""agent.yaml schema rules LGWXO010–016 (positive + negative per rule)."""

from __future__ import annotations

from pathlib import Path

from conftest import GOOD_AGENT_YAML, finding_ids, write_project

from langgraph_wxo.config import load_project
from langgraph_wxo.validate import run_all


def test_good_project_has_no_errors(good_project: Path) -> None:
    report = run_all(load_project(good_project))
    assert report.ok, [f.id for f in report.errors]


def test_lgwxo010_bad_spec_version(tmp_path: Path) -> None:
    yaml = GOOD_AGENT_YAML.replace("spec_version: v1", "spec_version: v9")
    write_project(tmp_path, agent_yaml=yaml)
    assert "LGWXO010" in finding_ids(tmp_path)


def test_lgwxo011_bad_kind(tmp_path: Path) -> None:
    yaml = GOOD_AGENT_YAML.replace("kind: agent", "kind: tool")
    write_project(tmp_path, agent_yaml=yaml)
    assert "LGWXO011" in finding_ids(tmp_path)


def test_lgwxo012_bad_framework(tmp_path: Path) -> None:
    yaml = GOOD_AGENT_YAML.replace("framework: langgraph", "framework: crewai")
    write_project(tmp_path, agent_yaml=yaml)
    assert "LGWXO012" in finding_ids(tmp_path)


def test_lgwxo013_name_with_whitespace(tmp_path: Path) -> None:
    yaml = GOOD_AGENT_YAML.replace("name: demo_agent", "name: demo agent")
    write_project(tmp_path, agent_yaml=yaml)
    assert "LGWXO013" in finding_ids(tmp_path)


def test_lgwxo013_name_too_long(tmp_path: Path) -> None:
    yaml = GOOD_AGENT_YAML.replace("name: demo_agent", f"name: {'x' * 41}")
    write_project(tmp_path, agent_yaml=yaml)
    assert "LGWXO013" in finding_ids(tmp_path)


def test_lgwxo014_empty_description(tmp_path: Path) -> None:
    yaml = GOOD_AGENT_YAML.replace("description: A demo agent for tests.", 'description: ""')
    write_project(tmp_path, agent_yaml=yaml)
    assert "LGWXO014" in finding_ids(tmp_path)


def test_lgwxo015_bad_entrypoint(tmp_path: Path) -> None:
    yaml = GOOD_AGENT_YAML.replace(
        "entrypoint: agent:create_agent", "entrypoint: agent.create_agent"
    )
    write_project(tmp_path, agent_yaml=yaml)
    assert "LGWXO015" in finding_ids(tmp_path)


def test_lgwxo016_unknown_field(tmp_path: Path) -> None:
    yaml = GOOD_AGENT_YAML + "mystery_field: 1\n"
    write_project(tmp_path, agent_yaml=yaml)
    ids = finding_ids(tmp_path)
    assert "LGWXO016" in ids


def test_placeholder_native_fields_do_not_add_unknown_field_noise(tmp_path: Path) -> None:
    yaml = """\
spec_version: v1
kind: native
name: demo_agent
description: Placeholder.
instructions: Echo messages.
llm: watsonx/ibm/granite-3-8b-instruct
style: default
tools: []
"""
    write_project(tmp_path, agent_yaml=yaml)
    assert "LGWXO016" not in finding_ids(tmp_path)
