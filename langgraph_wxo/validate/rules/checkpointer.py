"""Checkpointer / state rules: LGWXO040–041."""

from __future__ import annotations

from ...compat import ImportSpec
from ...config import ProjectConfig
from ..findings import Finding, make_finding


def check(project: ProjectConfig, spec: ImportSpec) -> list[Finding]:
    findings: list[Finding] = []
    name = project.agent_yaml_path.name
    cp = project.agent.checkpointer
    line = project.line_map.get("checkpointer")

    # LGWXO040 — no checkpointer configured: state will not persist between turns.
    if cp is None or not cp.type:
        findings.append(
            make_finding(
                "LGWXO040",
                name,
                "No checkpointer configured; agent state is lost between turns in WxO.",
                "Add a 'checkpointer' (memory | sqlite | postgres) to agent.yaml.",
                line=line,
            )
        )
        return findings

    # LGWXO041 — postgres requires a connection_string_key
    if cp.type == "postgres" and not cp.connection_string_key:
        findings.append(
            make_finding(
                "LGWXO041",
                name,
                "postgres checkpointer is missing 'connection_string_key'.",
                "Add 'checkpointer.connection_string_key: <key>' naming the injected "
                "connection string.",
                line=line,
            )
        )

    return findings
