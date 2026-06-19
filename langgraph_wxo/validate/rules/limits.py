"""Limitation / eligibility reminders: LGWXO050–052 (informational).

These are not defects to fix — they are sharp edges of the WxO native-import
runtime that the tool surfaces so developers are not surprised in production.
"""

from __future__ import annotations

from ...compat import ImportSpec
from ...config import ProjectConfig
from ..findings import Finding, make_finding

ELIGIBILITY_MESSAGE = (
    "WxO native LangGraph import is experimental, Python-only, and available only "
    "in commercial AWS and IBM Cloud regions (not on-prem/GovCloud)."
)


def check(project: ProjectConfig, spec: ImportSpec) -> list[Finding]:
    name = project.agent_yaml_path.name
    return [
        make_finding(
            "LGWXO050",
            name,
            "Tools defined in this package are read-only inside WxO.",
            "They cannot be reused/exposed as standalone WxO tools.",
        ),
        make_finding(
            "LGWXO051",
            name,
            "An imported LangGraph agent cannot use native WxO agents as collaborators.",
            "It cannot reach other WxO tools/agents/knowledge bases.",
        ),
        make_finding(
            "LGWXO052",
            name,
            ELIGIBILITY_MESSAGE,
            "Confirm your target region and runtime eligibility before deploying.",
        ),
    ]
