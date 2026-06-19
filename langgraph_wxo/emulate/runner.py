"""Drive the emulator subprocess and parse its structured result."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field

from ..config import ProjectConfig
from ._child import RESULT_PREFIX
from .mockcreds import build_mock_creds

_TIMEOUT_SECONDS = 120


@dataclass
class RunResult:
    """Outcome of an emulated run."""

    status: str  # "ok" | "contract" | "runtime" | "error"
    finding_id: str | None = None
    message: str = ""
    transcript: list[dict[str, str]] = field(default_factory=list)
    final_state_keys: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    stderr: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def run_agent(
    project: ProjectConfig,
    message: str,
    *,
    extra_creds: dict[str, str] | None = None,
) -> RunResult:
    """Run one turn of the project's agent in an isolated subprocess.

    Mock credentials are derived from declared connections (and any ``extra_creds``)
    and exposed under the WxO ``{app_id}_{credential_type}`` key format.
    """
    entrypoint = project.agent.entrypoint()
    if not entrypoint or ":" not in entrypoint:
        return RunResult(
            status="contract",
            finding_id="LGWXO015",
            message="agent.yaml entrypoint is missing or not in 'module:function' form.",
        )

    creds = build_mock_creds(project.agent.connections)
    if extra_creds:
        creds.update(extra_creds)

    env = dict(os.environ)
    env.update(creds)
    env["LGWXO_EMULATE"] = "1"

    spec = {"root": str(project.root), "entrypoint": entrypoint, "message": message}

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "langgraph_wxo.emulate._child"],
            input=json.dumps(spec),
            capture_output=True,
            text=True,
            env=env,
            timeout=_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return RunResult(
            status="runtime", message=f"Agent run timed out after {_TIMEOUT_SECONDS}s."
        )

    result = _parse_result(proc.stdout)
    if result is None:
        return RunResult(
            status="error",
            message="Emulator subprocess produced no result.",
            stderr=proc.stderr.strip(),
        )
    result.stderr = proc.stderr.strip()
    return result


def _parse_result(stdout: str) -> RunResult | None:
    for line in reversed(stdout.splitlines()):
        if line.startswith(RESULT_PREFIX):
            payload = json.loads(line[len(RESULT_PREFIX) :])
            return RunResult(
                status=str(payload.get("status", "error")),
                finding_id=payload.get("finding_id"),
                message=str(payload.get("message", "")),
                transcript=list(payload.get("transcript", [])),
                final_state_keys=list(payload.get("final_state_keys", [])),
                notices=list(payload.get("notices", [])),
            )
    return None
