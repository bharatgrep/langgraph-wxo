"""Synthesize obviously-fake credential env vars in the WxO key format.

WxO injects each connection's credential under ``{app_id}_{credential_type}``.
The emulator sets the same keys to clearly-fake ``MOCK-<app_id>-<type>`` values so
agent code that reads the right key works locally without any real secret.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..config import ConnectionSpec


def build_mock_creds(connections: list[ConnectionSpec]) -> dict[str, str]:
    """Return ``{runtime_key: MOCK-app-type}`` for each fully-specified connection."""
    creds: dict[str, str] = {}
    for conn in connections:
        key = conn.runtime_key()
        if key:
            creds[key] = f"MOCK-{conn.app_id}-{conn.credential_type}"
    return creds


def load_mock_creds(path: Path) -> dict[str, str]:
    """Load a JSON ``{key: value}`` mock-credential map from ``path``."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object of key/value pairs")
    return {str(k): str(v) for k, v in data.items()}
