"""Checkpointer / state rules: LGWXO040–041."""

from __future__ import annotations

from ...analyze import FactoryAnalysis
from ...compat import ImportSpec
from ...config import ProjectConfig
from ..findings import Finding, make_finding


def check(project: ProjectConfig, spec: ImportSpec, analysis: FactoryAnalysis) -> list[Finding]:
    findings: list[Finding] = []
    name = project.agent_yaml_path.name
    cp = project.agent.checkpointer
    line = project.line_map.get("checkpointer")

    # LGWXO040 — custom state without a checkpointer: state will not persist between turns.
    if cp is None or not cp.type:
        if analysis.custom_state_fields:
            fields = ", ".join(repr(field) for field in analysis.custom_state_fields)
            findings.append(
                make_finding(
                    "LGWXO040",
                    analysis.module_path.name if analysis.module_path else name,
                    f"State schema defines custom field(s) {fields} without a checkpointer; "
                    "WxO will not persist them between turns.",
                    "Add a checkpointer or redesign the state to rely only on messages.",
                    line=analysis.custom_state_line,
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
