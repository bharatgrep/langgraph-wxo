"""Dependency rules: LGWXO020–022."""

from __future__ import annotations

from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import Version

from ...compat import CRITICAL_DEPS, ImportSpec
from ...config import ProjectConfig
from ..findings import Finding, make_finding

_FLOOR_OPERATORS = {">=", ">", "==", "~="}


def _allows_below_minimum(specifier: str, minimum: str) -> bool:
    """True unless ``specifier`` guarantees a floor at or above ``minimum``.

    ``langgraph>=0.6.0`` passes; ``>=0.5`` / ``==0.4`` / ``<1.0`` (no floor) fail.
    A specifier is safe iff at least one clause establishes a lower bound whose
    version is ``>= minimum``.
    """
    try:
        spec_set = SpecifierSet(specifier)
    except InvalidSpecifier:
        return True
    min_version = Version(minimum)
    for clause in spec_set:
        if clause.operator in _FLOOR_OPERATORS:
            try:
                clause_version = Version(clause.version.rstrip(".*"))
            except Exception:  # noqa: BLE001 - malformed clause version
                continue
            if clause_version >= min_version:
                return False
    return True


def check(project: ProjectConfig, spec: ImportSpec) -> list[Finding]:
    findings: list[Finding] = []
    req_name = "requirements.txt"

    # LGWXO021 — requirements.txt missing
    if project.requirements_path is None:
        findings.append(
            make_finding(
                "LGWXO021",
                req_name,
                "requirements.txt is missing.",
                f"Create requirements.txt and pin 'langgraph>={spec.min_langgraph_version}'.",
            )
        )
        return findings

    reqs_by_name = {r.name.lower(): r for r in project.requirements if r.name}

    # LGWXO020 — langgraph missing or below the required floor
    langgraph_req = reqs_by_name.get("langgraph")
    if langgraph_req is None:
        findings.append(
            make_finding(
                "LGWXO020",
                req_name,
                "langgraph is not listed in requirements.txt.",
                f"Pin 'langgraph>={spec.min_langgraph_version}'.",
            )
        )
    elif not langgraph_req.specifier:
        findings.append(
            make_finding(
                "LGWXO020",
                req_name,
                f"langgraph is unpinned; WxO requires >= {spec.min_langgraph_version}.",
                f"Pin 'langgraph>={spec.min_langgraph_version}'.",
            )
        )
    elif _allows_below_minimum(langgraph_req.specifier, spec.min_langgraph_version):
        findings.append(
            make_finding(
                "LGWXO020",
                req_name,
                f"langgraph specifier '{langgraph_req.specifier}' allows versions "
                f"below {spec.min_langgraph_version}.",
                f"Pin 'langgraph>={spec.min_langgraph_version}'.",
            )
        )

    # LGWXO022 — unpinned critical deps (warn)
    for dep in CRITICAL_DEPS:
        req = reqs_by_name.get(dep)
        if req is not None and not req.pinned:
            findings.append(
                make_finding(
                    "LGWXO022",
                    req_name,
                    f"{dep} is unpinned.",
                    f"Pin a version, e.g. '{dep}>=...'.",
                )
            )

    return findings
