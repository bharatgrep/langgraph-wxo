# langgraph-wxo

> The fastest, safest way to get a LangGraph agent running inside IBM watsonx
> Orchestrate (WxO) via WxO's native LangGraph package import.

![status: pre-release](https://img.shields.io/badge/status-pre--release-orange)

`langgraph-wxo` is a thin developer-experience CLI (`lgwxo`) that does two things,
which are also its two demo angles:

- **Velocity** — scaffold a correct, importable LangGraph-on-WxO project in one
  command.
- **Safety** — statically validate a project against the import contract, and run
  it locally the way WxO will, *before* you upload.

It tracks (never forks) LangGraph and the WxO import spec.

## Disclaimer

This product is an independent, community-maintained project. It is not
affiliated with, endorsed by, or sponsored by IBM. "watsonx",
"watsonx Orchestrate", and "wxO" are trademarks of IBM Corporation.
"LangGraph" is a trademark of LangChain, Inc.

## Install

```bash
uvx langgraph-wxo --version      # run without installing
# or
pipx install langgraph-wxo
```

## Quickstart (5 minutes, both angles)

### 1. Velocity — scaffold a working agent

```bash
lgwxo new demo --template react-tools
cd demo
lgwxo validate                   # 0 errors
lgwxo run --message "hi"         # runs one turn locally, offline
```

`lgwxo new` produces a complete, **already-valid** package: an `agent.py` factory
that returns an *uncompiled* `StateGraph`, a pinned `requirements.txt`, an
`agent.yaml` with the entrypoint/checkpointer/connection, and a governed watsonx
model helper.

### 2. Safety — break it three ways, catch each locally

The import contract has sharp edges. `validate` and `run` catch them with a precise
`LGWXO###` finding and a fix hint — no failed uploads:

| Break | Caught as |
|---|---|
| Call `.compile()` in the factory | **LGWXO003** — return the uncompiled `StateGraph` |
| Pin `langgraph<0.6` in `requirements.txt` | **LGWXO020** — pin `langgraph>=0.6.0` |
| Read `OPENAI_API_KEY` instead of the injected `openai_api_api_key` | **LGWXO030/031** — match `{app_id}_{credential_type}` |

```bash
lgwxo validate --strict          # CI gate: warnings become errors
lgwxo run --message "hi"         # contract violations fail with the matching ID
```

## Commands

| Command | Purpose |
|---|---|
| `lgwxo new <name>` | Scaffold a project (`--template react-tools\|minimal`). |
| `lgwxo validate` / `doctor` | Validate against the import contract (`--strict`, `--json`). |
| `lgwxo run` | Run one turn locally (compile + inject mock creds + invoke). |
| `lgwxo check-env` | Report Python/langgraph versions and eligibility reminders. |

The connections sub-app, `package`, `import`, and the `governed-rag` template are
planned for a future release.

## The WxO native-import contract (what the tool enforces)

- The factory **accepts a `RunnableConfig`** and **returns an uncompiled
  `StateGraph`** — never call `.compile()`; WxO compiles it.
- `requirements.txt` pins **`langgraph>=0.6.0`**.
- Credentials are **injected by WxO at runtime** under
  `{connection_app_id}_{credential_type}` (e.g. connection `openai_api` +
  credential type `api_key` → `openai_api_api_key`), not read from a local `.env`.
- Without a configured checkpointer, **state is lost between turns**.
- Limitations (surfaced, not worked around): in-package tools are read-only inside
  WxO; the agent can't use native WxO agents as collaborators; Python-only;
  commercial AWS / IBM Cloud regions only; experimental.

## Compatibility matrix

| langgraph-wxo | Tested LangGraph | Target ADK | Import spec |
|---|---|---|---|
| 0.1.0 | `>=0.6.0` (dev: 1.x) | 2.7.x | `v1` |

Anything version-sensitive about WxO lives in
[`langgraph_wxo/compat/spec.py`](langgraph_wxo/compat/spec.py); use
`validate --target-spec <ver>` to validate against a specific spec.

## Development

```bash
uv sync --extra agent
uv run ruff check . && uv run ruff format --check .
uv run mypy langgraph_wxo
uv run pytest
```

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
