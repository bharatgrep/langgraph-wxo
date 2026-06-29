"""Finding model, severities, and the registry of every ``LGWXO###`` rule.

The registry is the single source of truth for rule IDs, their human title, and
their *base* severity. Rules construct findings via :func:`make_finding`, which
fills in title/severity from the registry (a rule may override severity for the
``error/warn`` dual-severity rules).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    """Finding severity. ``--strict`` promotes WARNING to ERROR for CI gating."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

    @property
    def rank(self) -> int:
        return {"error": 0, "warning": 1, "info": 2}[self.value]


@dataclass(frozen=True)
class RuleMeta:
    """Static metadata for one rule ID."""

    id: str
    severity: Severity
    title: str


@dataclass
class Finding:
    """A single validation result tied to a rule ID and (optionally) a location."""

    id: str
    severity: Severity
    path: str
    message: str
    fix: str
    line: int | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "path": self.path,
            "line": self.line,
            "message": self.message,
            "fix": self.fix,
        }


E, W, INF = Severity.ERROR, Severity.WARNING, Severity.INFO

#: Every rule the validator can emit. Keep IDs/severities stable (the contract).
RULES: dict[str, RuleMeta] = {
    m.id: m
    for m in [
        # Factory / code
        RuleMeta("LGWXO001", E, "Factory not found"),
        RuleMeta("LGWXO002", E, "Factory missing RunnableConfig parameter"),
        RuleMeta("LGWXO003", E, "Factory returns a compiled graph"),
        RuleMeta("LGWXO004", W, "Factory return type is not a StateGraph"),
        RuleMeta("LGWXO005", W, "Module-level side effects at import time"),
        # agent.yaml schema
        RuleMeta("LGWXO010", E, "Missing or invalid spec_version"),
        RuleMeta("LGWXO011", E, "kind is not 'agent'"),
        RuleMeta("LGWXO012", E, "framework is not 'langgraph'"),
        RuleMeta("LGWXO013", E, "Invalid name"),
        RuleMeta("LGWXO014", E, "Empty description"),
        RuleMeta("LGWXO015", E, "entrypoint is not module:function"),
        RuleMeta("LGWXO016", W, "Unknown field for target spec"),
        # Dependencies
        RuleMeta("LGWXO020", E, "langgraph missing or < 0.6.0"),
        RuleMeta("LGWXO021", E, "requirements.txt missing"),
        RuleMeta("LGWXO022", W, "Unpinned critical dependency"),
        # Connections / credentials
        RuleMeta("LGWXO030", W, "Code reads an undeclared credential"),
        RuleMeta("LGWXO031", E, "Credential key mismatch"),
        RuleMeta("LGWXO032", INF, "Declared connection unused"),
        RuleMeta("LGWXO033", W, "Local .env credential loading"),
        # Checkpointer / state
        RuleMeta("LGWXO040", W, "Custom state without a checkpointer"),
        RuleMeta("LGWXO041", E, "postgres checkpointer without connection_string_key"),
        # Limitations / eligibility (informational)
        RuleMeta("LGWXO050", INF, "In-package tools are read-only in WxO"),
        RuleMeta("LGWXO051", INF, "Cannot use native WxO agents as collaborators"),
        RuleMeta("LGWXO052", INF, "Python-only / commercial-cloud-only / experimental"),
        RuleMeta("LGWXO053", W, "Code attempts WxO platform access"),
    ]
}


def make_finding(  # noqa: PLR0913
    rule_id: str,
    path: str,
    message: str,
    fix: str,
    *,
    line: int | None = None,
    severity: Severity | None = None,
) -> Finding:
    """Build a :class:`Finding`, defaulting severity/title from :data:`RULES`."""
    meta = RULES[rule_id]
    return Finding(
        id=rule_id,
        severity=severity or meta.severity,
        path=path,
        message=message,
        fix=fix,
        line=line,
    )


@dataclass
class Report:
    """Aggregated validation result with convenience counters."""

    findings: list[Finding] = field(default_factory=list)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.WARNING]

    @property
    def infos(self) -> list[Finding]:
        return [f for f in self.findings if f.severity is Severity.INFO]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.ok,
            "counts": {
                "error": len(self.errors),
                "warning": len(self.warnings),
                "info": len(self.infos),
            },
            "findings": [f.to_dict() for f in self.findings],
        }
