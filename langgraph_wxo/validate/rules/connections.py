"""Connection / credential rules: LGWXO030–032.

Cross-checks credential keys the code reads from the environment (found by AST)
against the connections declared in ``agent.yaml``. WxO injects credentials as
``{app_id}_{credential_type}`` — local ``.env`` names like ``OPENAI_API_KEY`` will
be ``None`` in production.
"""

from __future__ import annotations

from ...analyze import FactoryAnalysis
from ...compat import ImportSpec
from ...config import ProjectConfig
from ..findings import Finding, make_finding

# Substrings that mark an env var as credential-like (so we ignore PORT, DEBUG…).
_CREDENTIAL_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "APIKEY")


def _looks_like_credential(key: str) -> bool:
    upper = key.upper()
    return any(marker in upper for marker in _CREDENTIAL_MARKERS)


def _normalize(value: str) -> str:
    return value.lower().replace("_", "").replace("-", "")


def check(
    project: ProjectConfig,
    spec: ImportSpec,
    analysis: FactoryAnalysis,
) -> list[Finding]:
    findings: list[Finding] = []
    module_name = analysis.module_path.name if analysis.module_path is not None else "entry module"

    declared = project.agent.connections
    runtime_keys = {c.runtime_key() for c in declared if c.runtime_key()}
    used_keys: set[str] = set()

    for read in analysis.credential_reads:
        key = read.key
        if key in runtime_keys:
            used_keys.add(key)
            continue
        if not _looks_like_credential(key):
            continue

        # Does this read look like a mangled reference to a declared connection?
        related = None
        for conn in declared:
            if not conn.app_id:
                continue
            app = conn.app_id.lower()
            if app in key.lower() or _normalize(conn.runtime_key() or "") in _normalize(key):
                related = conn
                break

        if related is not None:
            expected = related.runtime_key()
            findings.append(
                make_finding(
                    "LGWXO031",
                    module_name,
                    f"Code reads {key!r}, but WxO injects connection "
                    f"'{related.app_id}' as {expected!r}.",
                    f"Read {expected!r} from RunnableConfig configurable credentials.",
                    line=read.line,
                )
            )
        elif read.source == "config":
            continue
        else:
            findings.append(
                make_finding(
                    "LGWXO030",
                    module_name,
                    f"Code reads credential {key!r} but no connection declares it; "
                    "it will be None in WxO.",
                    "Declare a connection so WxO injects it as '{app_id}_{credential_type}'.",
                    line=read.line,
                )
            )

    if analysis.dotenv_loads and any(
        read.source == "env" and _looks_like_credential(read.key)
        for read in analysis.credential_reads
    ):
        findings.append(
            make_finding(
                "LGWXO033",
                module_name,
                "Code loads local .env files for credentials; WxO runtime does not ship "
                "developer .env files.",
                "Use WxO connections and read injected credentials from RunnableConfig.",
                line=analysis.dotenv_loads[0],
            )
        )

    # LGWXO032 — declared but never read
    for conn in declared:
        rk = conn.runtime_key()
        if rk and rk not in used_keys:
            findings.append(
                make_finding(
                    "LGWXO032",
                    project.agent_yaml_path.name,
                    f"Declared connection '{conn.app_id}' (key {rk!r}) is never read in code.",
                    "Remove the unused connection or read its injected key.",
                    line=project.line_map.get("connections"),
                )
            )

    return findings
