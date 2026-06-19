"""Load and normalise a project on disk into a :class:`ProjectConfig`.

Uses ``ruamel.yaml`` in round-trip mode so we can recover source line numbers for
``agent.yaml`` keys (surfaced in findings). Loading never executes user code.
"""

from __future__ import annotations

from pathlib import Path

from packaging.requirements import InvalidRequirement
from packaging.requirements import Requirement as PkgRequirement
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap
from ruamel.yaml.error import YAMLError

from .models import AgentYaml, ProjectConfig, Requirement

AGENT_YAML_NAMES = ("agent.yaml", "agent.yml")
REQUIREMENTS_NAME = "requirements.txt"


class LoadError(Exception):
    """Raised when a project cannot be loaded at all (missing/invalid YAML)."""


def _find_agent_yaml(root: Path) -> Path | None:
    for name in AGENT_YAML_NAMES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def _line_map(data: object) -> dict[str, int]:
    """Map top-level mapping keys to 1-based source line numbers, if available."""
    if not isinstance(data, CommentedMap):
        return {}
    lines: dict[str, int] = {}
    for key in data:
        try:
            pos = data.lc.data[key]  # [key_line, key_col, value_line, value_col]
        except (AttributeError, KeyError, TypeError):
            continue
        lines[str(key)] = int(pos[0]) + 1
    return lines


def _parse_requirements(path: Path) -> list[Requirement]:
    reqs: list[Requirement] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        try:
            parsed = PkgRequirement(stripped)
        except InvalidRequirement:
            reqs.append(Requirement(raw=stripped))
            continue
        spec = str(parsed.specifier) if parsed.specifier else None
        reqs.append(
            Requirement(
                raw=stripped,
                name=parsed.name,
                specifier=spec,
                pinned=bool(spec),
            )
        )
    return reqs


def load_project(path: str | Path) -> ProjectConfig:
    """Load the project rooted at ``path`` into a :class:`ProjectConfig`.

    Raises :class:`LoadError` if no readable ``agent.yaml`` exists.
    """
    root = Path(path).resolve()
    if not root.is_dir():
        raise LoadError(f"not a directory: {root}")

    agent_yaml_path = _find_agent_yaml(root)
    if agent_yaml_path is None:
        raise LoadError(f"no agent.yaml found in {root}")

    yaml = YAML(typ="rt")
    try:
        raw_obj = yaml.load(agent_yaml_path.read_text(encoding="utf-8"))
    except YAMLError as exc:
        raise LoadError(f"could not parse {agent_yaml_path.name}: {exc}") from exc

    if raw_obj is None:
        raw_obj = CommentedMap()
    if not isinstance(raw_obj, CommentedMap):
        raise LoadError(f"{agent_yaml_path.name} must be a mapping at the top level")

    # Convert the round-trip object into plain Python for pydantic.
    plain: dict[str, object] = dict(raw_obj)
    agent = AgentYaml.model_validate(plain)

    candidate_req = root / REQUIREMENTS_NAME
    requirements_path: Path | None = None
    requirements: list[Requirement] = []
    if candidate_req.is_file():
        requirements_path = candidate_req
        requirements = _parse_requirements(candidate_req)

    return ProjectConfig(
        root=root,
        agent_yaml_path=agent_yaml_path,
        agent=agent,
        raw=plain,
        line_map=_line_map(raw_obj),
        requirements_path=requirements_path,
        requirements=requirements,
    )
