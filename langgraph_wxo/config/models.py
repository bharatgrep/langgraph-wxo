"""Pydantic v2 models mirroring ``agent.yaml`` and connection declarations.

The models are intentionally **permissive** — almost every field is optional and
unknown keys are preserved. Schema *correctness* is reported by the validation
ruleset (``LGWXO0xx``) with precise IDs and fix hints, not by pydantic raising on
load. This lets ``lgwxo validate`` produce friendly findings for a malformed
project instead of an opaque parse error.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


def split_entrypoint(entrypoint: str) -> tuple[str, str] | None:
    """Split a ``module:function`` entrypoint. Return ``None`` if malformed."""
    if entrypoint.count(":") != 1:
        return None
    module, _, function = entrypoint.partition(":")
    module, function = module.strip(), function.strip()
    if not module or not function:
        return None
    return module, function


class ConnectionSpec(BaseModel):
    """A connection the agent expects WxO to inject credentials for.

    The runtime env key WxO injects follows ``{app_id}_{credential_type}``.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    app_id: str | None = None
    # ``type`` is the credential type (e.g. ``api_key``); aliased for readability.
    credential_type: str | None = Field(default=None, alias="type")

    def runtime_key(self) -> str | None:
        """Return ``{app_id}_{credential_type}`` or ``None`` if underspecified."""
        if not self.app_id or not self.credential_type:
            return None
        return f"{self.app_id}_{self.credential_type}"


class CodeBundle(BaseModel):
    model_config = ConfigDict(extra="allow")
    entrypoint: str | None = None


class Deployment(BaseModel):
    model_config = ConfigDict(extra="allow")
    code_bundle: CodeBundle | None = None


class Checkpointer(BaseModel):
    model_config = ConfigDict(extra="allow")
    type: str | None = None
    connection_string_key: str | None = None


class AgentYaml(BaseModel):
    """Permissive model of ``agent.yaml``; unknown keys are kept for drift checks."""

    model_config = ConfigDict(extra="allow")

    spec_version: str | None = None
    kind: str | None = None
    name: str | None = None
    title: str | None = None
    description: str | None = None
    framework: str | None = None
    deployment: Deployment | None = None
    checkpointer: Checkpointer | None = None
    connections: list[ConnectionSpec] = Field(default_factory=list)

    def entrypoint(self) -> str | None:
        """Return the declared ``module:function`` entrypoint, if present."""
        if self.deployment and self.deployment.code_bundle:
            return self.deployment.code_bundle.entrypoint
        return None


class Requirement(BaseModel):
    """One parsed line from ``requirements.txt``."""

    raw: str
    name: str | None = None
    specifier: str | None = None
    pinned: bool = False


class ProjectConfig(BaseModel):
    """Everything the validator and emulator need about a project on disk."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    root: Path
    agent_yaml_path: Path
    agent: AgentYaml
    raw: dict[str, object] = Field(default_factory=dict)
    # Top-level ``agent.yaml`` key -> 1-based source line, for finding locations.
    line_map: dict[str, int] = Field(default_factory=dict)
    requirements_path: Path | None = None
    requirements: list[Requirement] = Field(default_factory=list)

    def entry_module_path(self) -> Path | None:
        """Resolve the entry module file from the declared entrypoint, if any."""
        entrypoint = self.agent.entrypoint()
        if not entrypoint:
            return None
        parts = split_entrypoint(entrypoint)
        if not parts:
            return None
        module, _ = parts
        return self.root / (module.replace(".", "/") + ".py")
