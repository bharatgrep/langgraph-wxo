"""Dependency (020–022) and checkpointer (040–041) rules."""

from __future__ import annotations

from pathlib import Path

from conftest import GOOD_AGENT_YAML, finding_ids, write_project


def test_lgwxo020_old_langgraph(tmp_path: Path) -> None:
    write_project(tmp_path, requirements="langgraph>=0.5\n")
    assert "LGWXO020" in finding_ids(tmp_path)


def test_lgwxo020_missing_langgraph(tmp_path: Path) -> None:
    write_project(tmp_path, requirements="langchain-core>=0.3\n")
    assert "LGWXO020" in finding_ids(tmp_path)


def test_lgwxo020_floor_passes(tmp_path: Path) -> None:
    write_project(tmp_path, requirements="langgraph>=0.6.0\n")
    assert "LGWXO020" not in finding_ids(tmp_path)


def test_lgwxo021_missing_requirements(tmp_path: Path) -> None:
    write_project(tmp_path, requirements=None)
    assert "LGWXO021" in finding_ids(tmp_path)


def test_lgwxo022_unpinned_dep(tmp_path: Path) -> None:
    write_project(tmp_path, requirements="langgraph>=0.6.0\nlangchain-ibm\n")
    assert "LGWXO022" in finding_ids(tmp_path)


def test_lgwxo040_no_checkpointer(tmp_path: Path) -> None:
    yaml = "\n".join(
        ln for ln in GOOD_AGENT_YAML.splitlines() if ln not in {"checkpointer:", "  type: memory"}
    )
    write_project(tmp_path, agent_yaml=yaml)
    assert "LGWXO040" in finding_ids(tmp_path)


def test_lgwxo041_postgres_without_key(tmp_path: Path) -> None:
    yaml = GOOD_AGENT_YAML.replace("  type: memory", "  type: postgres")
    write_project(tmp_path, agent_yaml=yaml)
    assert "LGWXO041" in finding_ids(tmp_path)


def test_postgres_with_key_passes(tmp_path: Path) -> None:
    yaml = GOOD_AGENT_YAML.replace(
        "  type: memory", "  type: postgres\n  connection_string_key: db_conn"
    )
    write_project(tmp_path, agent_yaml=yaml)
    assert "LGWXO041" not in finding_ids(tmp_path)
