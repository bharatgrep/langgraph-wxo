"""Validation engine: run the ruleset against a project and collect findings."""

from __future__ import annotations

from ..analyze import FactoryAnalysis, analyze_factory
from ..compat import ImportSpec, get_spec
from ..config import ProjectConfig
from .findings import Finding, Report, Severity
from .rules import agent_yaml, checkpointer, connections, deps, factory, limits


def _promote(findings: list[Finding]) -> list[Finding]:
    """Promote WARNING findings to ERROR for ``--strict`` runs."""
    for f in findings:
        if f.severity is Severity.WARNING:
            f.severity = Severity.ERROR
    return findings


def _sort_key(f: Finding) -> tuple[int, str, int]:
    return (f.severity.rank, f.id, f.line or 0)


def run_all(
    project: ProjectConfig,
    spec: ImportSpec | None = None,
    *,
    strict: bool = False,
) -> Report:
    """Run every rule family and return an aggregated :class:`Report`.

    Static only — no user code is executed. The factory and connection rules use
    AST analysis (:func:`analyze_factory`) of the entry module.
    """
    spec = spec or get_spec()
    analysis: FactoryAnalysis = analyze_factory(project)

    findings: list[Finding] = []
    findings += agent_yaml.check(project, spec)
    findings += deps.check(project, spec)
    findings += checkpointer.check(project, spec, analysis)
    findings += factory.check(project, spec, analysis)
    findings += connections.check(project, spec, analysis)
    findings += limits.check(project, spec)

    if strict:
        findings = _promote(findings)

    findings.sort(key=_sort_key)
    return Report(findings=findings)
