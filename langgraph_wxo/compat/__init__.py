"""WxO import-spec compatibility layer.

Everything in this package that is version-sensitive or not independently
verifiable against IBM's published docs is isolated here and tagged with a
``# TODO(spec)`` comment, so spec drift is a one-file change.
"""

from .spec import DEFAULT_SPEC_VERSION, ImportSpec, get_spec, known_spec_versions

__all__ = ["DEFAULT_SPEC_VERSION", "ImportSpec", "get_spec", "known_spec_versions"]
