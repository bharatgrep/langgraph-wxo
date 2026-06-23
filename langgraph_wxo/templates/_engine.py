"""Render a template directory + ``template.toml`` manifest into a project tree.

A template is a directory under ``langgraph_wxo/templates/`` containing:

* ``template.toml`` — manifest (name, description, default variables, post-render
  notes). The manifest itself is never written to the rendered project.
* source files; any file whose name ends in ``.jinja`` is rendered with Jinja2
  and written with the ``.jinja`` suffix stripped. Other files are copied as-is.

The rendered output is guaranteed (by the shipped templates + tests) to pass
``lgwxo validate`` with zero errors.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, StrictUndefined

_TEMPLATES_DIR = Path(__file__).resolve().parent
_MANIFEST_NAME = "template.toml"
_JINJA_SUFFIX = ".jinja"


class TemplateError(Exception):
    """Base error for template rendering."""


class UnknownTemplateError(TemplateError):
    """Raised when a requested template does not exist."""


@dataclass
class TemplateManifest:
    name: str
    description: str
    post_render: str = ""
    variables: dict[str, object] = field(default_factory=dict)


@dataclass
class RenderResult:
    target: Path
    files: list[Path]
    manifest: TemplateManifest


def available_templates() -> list[str]:
    """Return the names of templates that ship with this build."""
    return sorted(
        p.name for p in _TEMPLATES_DIR.iterdir() if p.is_dir() and (p / _MANIFEST_NAME).is_file()
    )


def _load_manifest(template_dir: Path) -> TemplateManifest:
    data = tomllib.loads((template_dir / _MANIFEST_NAME).read_text(encoding="utf-8"))
    return TemplateManifest(
        name=str(data.get("name", template_dir.name)),
        description=str(data.get("description", "")),
        post_render=str(data.get("post_render", "")),
        variables=dict(data.get("variables", {})),
    )


def render_template(
    template: str,
    target: Path,
    variables: dict[str, object],
) -> RenderResult:
    """Render ``template`` into ``target`` with ``variables``.

    Raises :class:`UnknownTemplateError` if the template is missing, or
    :class:`TemplateError` if ``target`` already exists and is non-empty.
    """
    template_dir = _TEMPLATES_DIR / template
    if not (template_dir.is_dir() and (template_dir / _MANIFEST_NAME).is_file()):
        raise UnknownTemplateError(
            f"unknown template {template!r}; available: {', '.join(available_templates())}"
        )

    if target.exists() and any(target.iterdir()):
        raise TemplateError(f"target directory is not empty: {target}")

    manifest = _load_manifest(template_dir)
    merged = {**manifest.variables, **variables}

    env = Environment(undefined=StrictUndefined, keep_trailing_newline=True, autoescape=False)

    written: list[Path] = []
    for src in sorted(template_dir.rglob("*")):
        if src.is_dir() or src.name == _MANIFEST_NAME:
            continue
        rel = src.relative_to(template_dir)
        out_rel = rel.with_suffix("") if src.suffix == _JINJA_SUFFIX else rel
        dest = target / out_rel
        dest.parent.mkdir(parents=True, exist_ok=True)

        raw = src.read_text(encoding="utf-8")
        content = env.from_string(raw).render(**merged) if src.suffix == _JINJA_SUFFIX else raw
        dest.write_text(content, encoding="utf-8")
        written.append(dest)

    return RenderResult(target=target, files=written, manifest=manifest)
