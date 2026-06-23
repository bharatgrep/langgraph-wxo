"""Subprocess entrypoint that runs a user's factory the way WxO will.

Reads a JSON spec from stdin, executes the factory in *this* isolated process
(with mock credentials and ``LGWXO_EMULATE=1`` already set by the parent), and
writes a single JSON result line prefixed with :data:`RESULT_PREFIX` to stdout.

Contract violations are reported as structured results mapped to ``LGWXO###`` IDs
rather than raised as raw tracebacks. This module is invoked as
``python -m langgraph_wxo.emulate._child``; never import it in-process.
"""

from __future__ import annotations

import inspect
import json
import sys
import traceback
from pathlib import Path
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_core.runnables.config import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

RESULT_PREFIX = "LGWXO_RESULT:"


def _emit(result: dict[str, Any]) -> None:
    sys.stdout.write("\n" + RESULT_PREFIX + json.dumps(result) + "\n")
    sys.stdout.flush()


def _message_summary(messages: list[Any]) -> list[dict[str, str]]:
    transcript: list[dict[str, str]] = []
    for msg in messages:
        msg_type = getattr(msg, "type", msg.__class__.__name__)
        content = getattr(msg, "content", "")
        transcript.append({"type": str(msg_type), "content": str(content)})
    return transcript


def _run(spec: dict[str, Any]) -> dict[str, Any]:  # noqa: PLR0911 - one return per contract check
    root = spec["root"]
    entrypoint = spec["entrypoint"]
    message = spec["message"]

    sys.path.insert(0, str(Path(root).resolve()))

    module_name, _, factory_name = entrypoint.partition(":")

    # Resolve the factory (LGWXO001 on any import/lookup failure).
    try:
        module = __import__(module_name, fromlist=[factory_name])
    except Exception as exc:  # noqa: BLE001 - report as contract finding
        return {
            "status": "contract",
            "finding_id": "LGWXO001",
            "message": f"Could not import entry module {module_name!r}: {exc}",
        }
    factory = getattr(module, factory_name, None)
    if factory is None:
        return {
            "status": "contract",
            "finding_id": "LGWXO001",
            "message": f"Factory {factory_name!r} not found in {module_name!r}.",
        }

    # Signature must accept a RunnableConfig (LGWXO002).
    if not inspect.signature(factory).parameters:
        return {
            "status": "contract",
            "finding_id": "LGWXO002",
            "message": f"Factory {factory_name!r} does not accept a RunnableConfig.",
        }

    config: RunnableConfig = {"configurable": {"thread_id": "lgwxo-emulator"}}

    try:
        graph = factory(config)
    except TypeError as exc:
        return {
            "status": "contract",
            "finding_id": "LGWXO002",
            "message": f"Factory could not be called with a RunnableConfig: {exc}",
        }

    # Must return an uncompiled StateGraph (LGWXO003 / LGWXO004).
    if isinstance(graph, CompiledStateGraph):
        return {
            "status": "contract",
            "finding_id": "LGWXO003",
            "message": "Factory returned a compiled graph; return the uncompiled StateGraph.",
        }
    if not isinstance(graph, StateGraph):
        return {
            "status": "contract",
            "finding_id": "LGWXO004",
            "message": f"Factory returned {type(graph).__name__}, not a StateGraph.",
        }

    # Compile here (WxO does this) with an in-memory checkpointer and run one turn.
    notices = [
        "Emulator forces an in-memory checkpointer regardless of the declared type.",
        "State will not persist between turns unless a checkpointer is configured in WxO.",
        "Tool/agent isolation and A2A semantics are not emulated.",
    ]
    try:
        app = graph.compile(checkpointer=MemorySaver())
        agent_input: dict[str, Any] = {"messages": [HumanMessage(content=message)]}
        final_state = app.invoke(agent_input, config=config)
    except Exception:  # noqa: BLE001 - genuine agent runtime error
        return {
            "status": "runtime",
            "finding_id": None,
            "message": traceback.format_exc(limit=8),
        }

    messages = final_state.get("messages", []) if isinstance(final_state, dict) else []
    state_keys = sorted(final_state.keys()) if isinstance(final_state, dict) else []
    return {
        "status": "ok",
        "finding_id": None,
        "message": "",
        "transcript": _message_summary(messages),
        "final_state_keys": state_keys,
        "notices": notices,
    }


def main() -> None:
    spec = json.loads(sys.stdin.read())
    try:
        result = _run(spec)
    except Exception:  # noqa: BLE001 - last-resort guard; never leak a raw crash
        result = {"status": "runtime", "finding_id": None, "message": traceback.format_exc(limit=8)}
    _emit(result)


if __name__ == "__main__":
    main()
