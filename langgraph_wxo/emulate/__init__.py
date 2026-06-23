"""Lightweight local emulator: run the factory the way WxO will, in a subprocess."""

from .mockcreds import build_mock_creds, load_mock_creds
from .runner import RunResult, run_agent

__all__ = ["RunResult", "build_mock_creds", "load_mock_creds", "run_agent"]
