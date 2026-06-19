"""Reference implementation of the governed watsonx model helper.

This is the canonical source for ``make_watsonx_chat``. The ``react-tools``
template ships a self-contained copy (``watsonx_model.py``) so generated projects
do not depend on ``langgraph-wxo`` at runtime; keep the two in sync.

The watsonx.ai **Model Gateway** is provider-agnostic (Granite, OpenAI,
Anthropic, NVIDIA, ... via an OpenAI-compatible interface) and governed by
watsonx Orchestrate. Credentials are read from WxO-injected connection keys, with
documented env-var fallbacks for local development. When ``LGWXO_EMULATE=1`` is
set (by ``lgwxo run``) a deterministic offline stub is returned instead.
"""

from __future__ import annotations

import itertools
import os
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain_core.runnables.config import RunnableConfig
from pydantic import SecretStr

# TODO(spec): confirm gateway endpoint/field names and a region-stable model alias
# for the targeted ADK version.
_GATEWAY_URL_KEYS = ("watsonx_gateway_url", "WATSONX_GATEWAY_URL", "WATSONX_URL")
_GATEWAY_KEY_KEYS = ("watsonx_gateway_api_key", "WATSONX_GATEWAY_API_KEY", "WATSONX_APIKEY")

_DEFAULT_MODEL = "watsonx/ibm/granite-3-8b-instruct"


def _first_env(keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = os.environ.get(key)
        if value:
            return value
    return None


def _emulator_model() -> BaseChatModel:
    canned = AIMessage(content="[emulated] Hello! (no model is called during lgwxo run)")
    return GenericFakeChatModel(messages=itertools.cycle([canned]))


def make_watsonx_chat(
    model: str | None = None,
    *,
    api_key: str | None = None,
    config: RunnableConfig | None = None,
) -> BaseChatModel:
    """Return a chat model configured for the watsonx Model Gateway.

    In emulation mode (``LGWXO_EMULATE=1``) returns a deterministic offline stub so
    a turn can run without network access or real credentials.
    """
    if os.environ.get("LGWXO_EMULATE") == "1":
        return _emulator_model()

    # Lazy import: avoid pulling in langchain_ibm unless a real model is needed.
    from langchain_ibm import ChatWatsonx  # noqa: PLC0415

    url = _first_env(_GATEWAY_URL_KEYS)
    apikey = api_key or _first_env(_GATEWAY_KEY_KEYS)
    kwargs: dict[str, Any] = {"model_id": model or _DEFAULT_MODEL}
    if url:
        kwargs["url"] = SecretStr(url)
    if apikey:
        kwargs["apikey"] = SecretStr(apikey)
    return ChatWatsonx(**kwargs)
