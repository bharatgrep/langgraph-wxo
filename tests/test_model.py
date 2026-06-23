"""Model helper: returns an offline stub in emulation mode."""

from __future__ import annotations

import pytest

from langgraph_wxo.model import make_watsonx_chat


def test_emulate_mode_returns_offline_stub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LGWXO_EMULATE", "1")
    model = make_watsonx_chat("any-model")
    response = model.invoke("hello")
    assert "emulated" in response.content


def test_emulate_stub_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LGWXO_EMULATE", "1")
    model = make_watsonx_chat()
    first = model.invoke("a").content
    second = model.invoke("b").content
    assert first == second
