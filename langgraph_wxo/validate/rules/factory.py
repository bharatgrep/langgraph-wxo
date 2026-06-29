"""Factory / code rules: LGWXO001–005 (driven by AST analysis)."""

from __future__ import annotations

from ...analyze import FactoryAnalysis
from ...compat import ImportSpec
from ...config import ProjectConfig
from ..findings import Finding, make_finding


def check(
    project: ProjectConfig,
    spec: ImportSpec,
    analysis: FactoryAnalysis,
) -> list[Finding]:
    findings: list[Finding] = []

    # No resolvable entrypoint: LGWXO015 (agent_yaml) already reports it.
    if analysis.factory_name is None:
        return findings

    module_name = analysis.module_path.name if analysis.module_path is not None else "entry module"

    # LGWXO001 — factory not found / module unreadable
    if not analysis.factory_found:
        if not analysis.module_exists:
            msg = f"Entry module for {analysis.entrypoint!r} not found."
        elif analysis.parse_error:
            msg = f"Entry module could not be parsed: {analysis.parse_error}"
        else:
            msg = f"Function {analysis.factory_name!r} not found in {module_name}."
        findings.append(
            make_finding(
                "LGWXO001",
                module_name,
                msg,
                "Correct deployment.code_bundle.entrypoint to a real 'module:function'.",
                line=analysis.factory_line,
            )
        )
        return findings  # remaining factory rules need the function

    # LGWXO002 — missing RunnableConfig parameter
    if not analysis.has_runnable_config_param:
        findings.append(
            make_finding(
                "LGWXO002",
                module_name,
                f"Factory {analysis.factory_name!r} does not accept a RunnableConfig.",
                "Use 'def create_agent(config: RunnableConfig) -> StateGraph:'.",
                line=analysis.factory_line,
            )
        )

    # LGWXO003 — returns a compiled graph
    if analysis.returns_compiled:
        findings.append(
            make_finding(
                "LGWXO003",
                module_name,
                "Factory returns a compiled graph; WxO compiles it for you.",
                "Return the uncompiled StateGraph (do not call .compile()).",
                line=analysis.compiled_line or analysis.factory_line,
            )
        )
    # LGWXO004 — return type is annotated as something other than a StateGraph
    elif analysis.return_annotation and "StateGraph" not in analysis.return_annotation:
        findings.append(
            make_finding(
                "LGWXO004",
                module_name,
                f"Factory return type is annotated {analysis.return_annotation!r}, "
                "not a StateGraph.",
                "Return (and annotate) an uncompiled StateGraph.",
                line=analysis.factory_line,
            )
        )

    # LGWXO005 — compile / network side effects at import time
    if analysis.module_level_compile or analysis.module_level_network:
        what = "compiles a graph" if analysis.module_level_compile else "makes a network call"
        findings.append(
            make_finding(
                "LGWXO005",
                module_name,
                f"Module {what} at import time.",
                "Move compile/network work inside the factory; keep import side-effect free.",
                line=analysis.module_level_line,
            )
        )

    # LGWXO053 — concrete attempt to use WxO platform APIs from inside LangGraph
    if analysis.wxo_platform_access:
        findings.append(
            make_finding(
                "LGWXO053",
                module_name,
                "Code imports WxO runtime platform APIs from inside the LangGraph package.",
                "Keep imported LangGraph agents as leaf collaborators; route WxO tools, "
                "agents, and knowledge bases from a native WxO parent.",
                line=analysis.wxo_platform_line,
            )
        )

    return findings
