"""``agent.yaml`` schema rules: LGWXO010–016."""

from __future__ import annotations

from ...compat import ImportSpec
from ...config import ProjectConfig, split_entrypoint
from ..findings import Finding, make_finding

_NATIVE_PLACEHOLDER_KEYS = frozenset({"instructions", "llm", "style", "tools"})


def check(project: ProjectConfig, spec: ImportSpec) -> list[Finding]:
    findings: list[Finding] = []
    agent = project.agent
    name = project.agent_yaml_path.name
    lines = project.line_map

    def line(key: str) -> int | None:
        return lines.get(key)

    # LGWXO010 — spec_version
    if agent.spec_version != spec.spec_version_value:
        findings.append(
            make_finding(
                "LGWXO010",
                name,
                f"spec_version is {agent.spec_version!r}; expected {spec.spec_version_value!r}.",
                f"Set 'spec_version: {spec.spec_version_value}'.",
                line=line("spec_version"),
            )
        )

    # LGWXO011 — kind
    if agent.kind != spec.kind_value:
        findings.append(
            make_finding(
                "LGWXO011",
                name,
                f"kind is {agent.kind!r}; native LangGraph import requires {spec.kind_value!r}.",
                f"Set 'kind: {spec.kind_value}'.",
                line=line("kind"),
            )
        )

    # LGWXO012 — framework
    if agent.framework != spec.framework_value:
        findings.append(
            make_finding(
                "LGWXO012",
                name,
                f"framework is {agent.framework!r}; expected {spec.framework_value!r}.",
                f"Set 'framework: {spec.framework_value}'.",
                line=line("framework"),
            )
        )

    # LGWXO013 — name
    name_value = agent.name
    if name_value is None or not name_value.strip():
        findings.append(
            make_finding(
                "LGWXO013",
                name,
                "name is empty or whitespace.",
                f"Set a non-empty 'name' with no spaces, <= {spec.name_max_len} characters.",
                line=line("name"),
            )
        )
    elif any(c.isspace() for c in name_value) or len(name_value) > spec.name_max_len:
        findings.append(
            make_finding(
                "LGWXO013",
                name,
                f"name {name_value!r} must contain no whitespace and be "
                f"<= {spec.name_max_len} characters.",
                "Use a short identifier-style name, e.g. 'my_agent'.",
                line=line("name"),
            )
        )

    # LGWXO014 — description
    if agent.description is None or not agent.description.strip():
        findings.append(
            make_finding(
                "LGWXO014",
                name,
                "description is empty.",
                "Add a non-empty 'description' explaining what the agent does.",
                line=line("description"),
            )
        )

    # LGWXO015 — entrypoint module:function
    entrypoint = agent.entrypoint()
    if entrypoint is None:
        findings.append(
            make_finding(
                "LGWXO015",
                name,
                "deployment.code_bundle.entrypoint is missing.",
                "Add 'deployment.code_bundle.entrypoint: agent:create_agent'.",
                line=line("deployment"),
            )
        )
    elif split_entrypoint(entrypoint) is None:
        findings.append(
            make_finding(
                "LGWXO015",
                name,
                f"entrypoint {entrypoint!r} is not in 'module:function' form.",
                "Use 'module:function', e.g. 'agent:create_agent'.",
                line=line("deployment"),
            )
        )

    # LGWXO016 — unknown top-level fields for the target spec (drift guard)
    for key in project.raw:
        key_name = str(key)
        if agent.kind != spec.kind_value and key_name in _NATIVE_PLACEHOLDER_KEYS:
            continue
        if key_name not in spec.known_agent_keys:
            findings.append(
                make_finding(
                    "LGWXO016",
                    name,
                    f"Unknown field {key_name!r} for spec {spec.version}.",
                    "Remove the field or target a spec version that supports it.",
                    line=line(key_name),
                )
            )

    return findings
