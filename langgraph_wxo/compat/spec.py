"""Known WxO native-import spec versions and their field maps.

This module is the **single place** where version-sensitive WxO/ADK facts live.
Where a detail is not independently verifiable from IBM's published docs at the
time of writing, it is encoded here with a ``# TODO(spec)`` marker rather than
guessed silently elsewhere in the codebase.

Default target: **ADK 2.7.x / import spec ``v1``**.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: The import-spec version validated against unless ``--target-spec`` overrides it.
DEFAULT_SPEC_VERSION = "v1"

#: Minimum LangGraph version WxO native import requires (native async streaming).
MIN_LANGGRAPH_VERSION = "0.6.0"

#: Critical runtime deps we recommend pinning (LGWXO022).
CRITICAL_DEPS = ("langgraph", "langchain-core", "langchain-ibm")

#: Default model alias used by templates. The watsonx.ai Model Gateway exposes
#: provider-agnostic aliases; the exact stable id varies by region.
# TODO(spec): confirm a region-stable Granite gateway alias for ADK 2.7.x (OQ-4).
DEFAULT_MODEL_ALIAS = "watsonx/ibm/granite-3-8b-instruct"


@dataclass(frozen=True)
class ImportSpec:
    """A pinned snapshot of the WxO native-import contract for one spec version."""

    version: str
    adk_version: str
    spec_version_value: str
    kind_value: str
    framework_value: str
    name_max_len: int
    checkpointer_types: frozenset[str]
    min_langgraph_version: str
    default_model_alias: str
    # Recognised top-level ``agent.yaml`` keys for this spec (drift guard, LGWXO016).
    known_agent_keys: frozenset[str] = field(default_factory=frozenset)
    known_deployment_keys: frozenset[str] = field(default_factory=frozenset)
    known_code_bundle_keys: frozenset[str] = field(default_factory=frozenset)
    known_checkpointer_keys: frozenset[str] = field(default_factory=frozenset)

    def credential_key(self, app_id: str, credential_type: str) -> str:
        """Runtime env key WxO injects for a connection: ``{app_id}_{type}``."""
        return f"{app_id}_{credential_type}"


# --- Spec registry -----------------------------------------------------------

_SPEC_V1 = ImportSpec(
    version="v1",
    adk_version="2.7.x",
    spec_version_value="v1",
    kind_value="agent",
    framework_value="langgraph",
    name_max_len=40,
    checkpointer_types=frozenset({"memory", "sqlite", "postgres"}),
    min_langgraph_version=MIN_LANGGRAPH_VERSION,
    default_model_alias=DEFAULT_MODEL_ALIAS,
    # TODO(spec): verify the exact accepted agent.yaml field set against ADK 2.7.x.
    known_agent_keys=frozenset(
        {
            "spec_version",
            "kind",
            "name",
            "title",
            "description",
            "framework",
            "deployment",
            "checkpointer",
            "connections",
        }
    ),
    known_deployment_keys=frozenset({"code_bundle"}),
    known_code_bundle_keys=frozenset({"entrypoint"}),
    known_checkpointer_keys=frozenset({"type", "connection_string_key"}),
)

_SPECS: dict[str, ImportSpec] = {
    _SPEC_V1.version: _SPEC_V1,
}


def known_spec_versions() -> list[str]:
    """Return the spec versions this build knows how to validate against."""
    return sorted(_SPECS)


def get_spec(version: str | None = None) -> ImportSpec:
    """Return the :class:`ImportSpec` for ``version`` (default: latest known).

    Raises ``KeyError`` with a helpful message for an unknown version.
    """
    if version is None:
        version = DEFAULT_SPEC_VERSION
    try:
        return _SPECS[version]
    except KeyError as exc:
        known = ", ".join(known_spec_versions())
        raise KeyError(f"unknown target spec {version!r}; known versions: {known}") from exc
