"""Jinja2-based project templates (vendored; no cookiecutter runtime dep)."""

from ._engine import (
    TemplateError,
    UnknownTemplateError,
    available_templates,
    render_template,
)

__all__ = [
    "TemplateError",
    "UnknownTemplateError",
    "available_templates",
    "render_template",
]
