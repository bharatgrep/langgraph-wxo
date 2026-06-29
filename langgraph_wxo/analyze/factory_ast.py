"""AST-based inspection of the factory function declared in ``agent.yaml``.

This module **never imports or executes** user code. It parses the entry module
with :mod:`ast` and answers the questions the factory/connection rules need:

* Does the factory exist at ``module:function``?
* Does it accept a ``RunnableConfig`` parameter?
* Does it return a *compiled* graph (``.compile()`` / ``CompiledStateGraph``)?
* Does it return a ``StateGraph`` (annotation/return-value heuristic)?
* Are there compile calls or obvious network calls at import time?
* Which credentials does it read from the environment or RunnableConfig?
* Does it rely on local ``.env`` loading?
* Does its state schema include custom fields that need persistence?
* Does it try to reach WxO platform APIs from inside the graph?
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from ..config import ProjectConfig, split_entrypoint

# Modules whose top-level use strongly implies a network call at import time.
_NETWORK_HINTS = {"requests", "httpx", "urllib", "urlopen", "socket", "aiohttp"}


@dataclass
class CredentialRead:
    """A literal credential key read by the entry module."""

    key: str
    line: int
    source: str = "env"


@dataclass
class FactoryAnalysis:
    """Everything the rules learn from statically analysing the entry module."""

    entrypoint: str | None
    factory_name: str | None
    module_path: Path | None
    inferred_entrypoint: bool = False
    module_exists: bool = False
    parse_error: str | None = None

    factory_found: bool = False
    factory_line: int | None = None
    has_runnable_config_param: bool = False

    returns_compiled: bool = False
    compiled_line: int | None = None
    return_annotation: str | None = None
    returns_state_graph: bool | None = None

    module_level_compile: bool = False
    module_level_network: bool = False
    module_level_line: int | None = None

    credential_reads: list[CredentialRead] = field(default_factory=list)
    dotenv_loads: list[int] = field(default_factory=list)
    custom_state_fields: list[str] = field(default_factory=list)
    custom_state_line: int | None = None
    wxo_platform_access: bool = False
    wxo_platform_line: int | None = None


def _annotation_str(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    try:
        return ast.unparse(node)
    except Exception:  # noqa: BLE001 - defensive; unparse should not fail
        return None


def _literal_str(node: ast.AST, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                part = _literal_str(value.value, constants)
                if part is None:
                    return None
                parts.append(part)
            else:
                return None
        return "".join(parts)
    return None


def _is_env_read(call: ast.Call, constants: dict[str, str]) -> str | None:
    """Return the env key for ``os.getenv(X)`` / ``os.environ.get(X)``."""
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr not in {"getenv", "get"}:
        return None
    if func.attr == "getenv":
        if not (isinstance(func.value, ast.Name) and func.value.id == "os"):
            return None
    elif not (
        isinstance(func.value, ast.Attribute)
        and func.value.attr == "environ"
        and isinstance(func.value.value, ast.Name)
        and func.value.value.id == "os"
    ):
        return None
    if call.args:
        return _literal_str(call.args[0], constants)
    return None


class _Visitor(ast.NodeVisitor):
    def __init__(self, factory_name: str, constants: dict[str, str]) -> None:
        self.factory_name = factory_name
        self.constants = constants
        self.result_factory: ast.FunctionDef | ast.AsyncFunctionDef | None = None
        self.module_level_compile = False
        self.module_level_network = False
        self.module_level_line: int | None = None
        self.credential_reads: list[CredentialRead] = []
        self.credential_vars: set[str] = set()
        self.dotenv_loads: list[int] = []
        self.custom_state_fields: list[str] = []
        self.custom_state_line: int | None = None
        self.wxo_platform_access = False
        self.wxo_platform_line: int | None = None
        self._depth = 0  # 0 == module level

    # -- credential reads (anywhere) -------------------------------------
    def visit_Subscript(self, node: ast.Subscript) -> None:
        # os.environ["KEY"]
        value = node.value
        if isinstance(value, ast.Attribute) and value.attr == "environ":
            key = _literal_str(node.slice, self.constants)
            if key is not None:
                self.credential_reads.append(CredentialRead(key, node.lineno))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        key = _is_env_read(node, self.constants)
        if key is not None:
            self.credential_reads.append(CredentialRead(key, node.lineno))
        config_key = _config_credential_key(node, self.constants, self.credential_vars)
        if config_key is not None:
            self.credential_reads.append(CredentialRead(config_key, node.lineno, "config"))
        if _call_root_names(node) & {"load_dotenv"}:
            self.dotenv_loads.append(node.lineno)

        # Module-level compile / network detection
        if self._depth == 0:
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "compile":
                self.module_level_compile = True
                self.module_level_line = node.lineno
            names = _call_root_names(node)
            if names & _NETWORK_HINTS:
                self.module_level_network = True
                self.module_level_line = self.module_level_line or node.lineno
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call) and _call_mentions_credentials(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.credential_vars.add(target.id)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module and node.module.startswith("ibm_watsonx_orchestrate.run"):
            self.wxo_platform_access = True
            self.wxo_platform_line = self.wxo_platform_line or node.lineno
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.startswith("ibm_watsonx_orchestrate.run"):
                self.wxo_platform_access = True
                self.wxo_platform_line = self.wxo_platform_line or node.lineno
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if _is_typeddict_class(node):
            fields = [
                stmt.target.id
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name)
            ]
            custom = [field for field in fields if field != "messages"]
            if custom:
                self.custom_state_fields.extend(custom)
                self.custom_state_line = self.custom_state_line or node.lineno
        self.generic_visit(node)

    def _visit_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        if self._depth == 0 and node.name == self.factory_name and self.result_factory is None:
            self.result_factory = node
        self._depth += 1
        self.generic_visit(node)
        self._depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_func(node)


def _call_root_names(node: ast.Call) -> set[str]:
    """Collect identifier names referenced in a call's func chain."""
    names: set[str] = set()
    cur: ast.expr = node.func
    while isinstance(cur, ast.Attribute):
        names.add(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        names.add(cur.id)
    return names


def _constant_strings(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for stmt in tree.body:
        if not isinstance(stmt, ast.Assign):
            continue
        value = _literal_str(stmt.value, constants)
        if value is None:
            continue
        for target in stmt.targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value
    return constants


def _is_typeddict_class(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Name) and base.id == "TypedDict":
            return True
        if isinstance(base, ast.Attribute) and base.attr == "TypedDict":
            return True
    return False


def _call_mentions_credentials(call: ast.Call) -> bool:
    return any(
        isinstance(node, ast.Constant) and node.value == "credentials" for node in ast.walk(call)
    )


def _config_credential_key(
    call: ast.Call,
    constants: dict[str, str],
    credential_vars: set[str],
) -> str | None:
    if not call.args:
        return None
    key = _literal_str(call.args[0], constants)
    if key is None:
        return None
    if key in {"configurable", "credentials"}:
        return None
    saw_credentials = _call_mentions_credentials(call)
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
        saw_credentials = saw_credentials or call.func.value.id in credential_vars
    return key if saw_credentials else None


def _fallback_entrypoint(project: ProjectConfig) -> tuple[str, Path, str] | None:
    candidate = project.root / "agent.py"
    if candidate.is_file():
        return "agent:create_agent", candidate, "create_agent"
    return None


def _track_assignments(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[dict[str, int], set[str]]:
    """Map var names to ``.compile()`` call lines, and names bound to a StateGraph."""
    compiled_vars: dict[str, int] = {}
    state_graph_vars: set[str] = set()
    for stmt in ast.walk(func):
        if not (isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call)):
            continue
        call = stmt.value
        targets = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
        if isinstance(call.func, ast.Attribute) and call.func.attr == "compile":
            compiled_vars.update({name: call.lineno for name in targets})
        elif isinstance(call.func, ast.Name) and call.func.id == "StateGraph":
            state_graph_vars.update(targets)
    return compiled_vars, state_graph_vars


def _analyze_factory_body(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
) -> tuple[bool, int | None, bool | None]:
    """Inspect factory returns for compiled-graph / StateGraph results.

    Returns ``(returns_compiled, compiled_line, returns_state_graph)``.
    """
    compiled_vars, state_graph_vars = _track_assignments(func)
    returns_compiled = False
    compiled_line: int | None = None
    returns_state_graph: bool | None = None

    for stmt in ast.walk(func):
        if not isinstance(stmt, ast.Return) or stmt.value is None:
            continue
        value = stmt.value
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
            if value.func.attr == "compile":
                returns_compiled, compiled_line = True, value.lineno
        elif isinstance(value, ast.Name) and value.id in compiled_vars:
            returns_compiled, compiled_line = True, compiled_vars[value.id]
        elif isinstance(value, ast.Name) and value.id in state_graph_vars:
            returns_state_graph = True

    return returns_compiled, compiled_line, returns_state_graph


def _has_runnable_config(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    args = func.args
    all_args = [*args.posonlyargs, *args.args, *args.kwonlyargs]
    if args.vararg:
        all_args.append(args.vararg)
    if args.kwarg:
        all_args.append(args.kwarg)
    for arg in all_args:
        ann = _annotation_str(arg.annotation)
        if ann and "RunnableConfig" in ann:
            return True
        if arg.arg == "config":
            return True
    return False


def analyze_factory(project: ProjectConfig) -> FactoryAnalysis:
    """Statically analyse the entry module declared in ``agent.yaml``."""
    entrypoint = project.agent.entrypoint()
    factory_name: str | None = None
    if entrypoint:
        parts = split_entrypoint(entrypoint)
        if parts:
            factory_name = parts[1]

    module_path = project.entry_module_path()
    inferred_entrypoint = False
    if module_path is None or factory_name is None:
        fallback = _fallback_entrypoint(project)
        if fallback is not None:
            entrypoint, module_path, factory_name = fallback
            inferred_entrypoint = True
    analysis = FactoryAnalysis(
        entrypoint=entrypoint,
        factory_name=factory_name,
        module_path=module_path,
        inferred_entrypoint=inferred_entrypoint,
    )

    if module_path is None or not module_path.is_file() or factory_name is None:
        return analysis
    analysis.module_exists = True

    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        analysis.parse_error = str(exc)
        return analysis

    constants = _constant_strings(tree)
    visitor = _Visitor(factory_name, constants)
    visitor.visit(tree)

    analysis.module_level_compile = visitor.module_level_compile
    analysis.module_level_network = visitor.module_level_network
    analysis.module_level_line = visitor.module_level_line
    analysis.credential_reads = visitor.credential_reads
    analysis.dotenv_loads = visitor.dotenv_loads
    analysis.custom_state_fields = sorted(set(visitor.custom_state_fields))
    analysis.custom_state_line = visitor.custom_state_line
    analysis.wxo_platform_access = visitor.wxo_platform_access
    analysis.wxo_platform_line = visitor.wxo_platform_line

    func = visitor.result_factory
    if func is None:
        return analysis

    analysis.factory_found = True
    analysis.factory_line = func.lineno
    analysis.has_runnable_config_param = _has_runnable_config(func)
    analysis.return_annotation = _annotation_str(func.returns)

    returns_compiled, compiled_line, returns_state_graph = _analyze_factory_body(func)
    annotation = analysis.return_annotation or ""
    if "CompiledStateGraph" in annotation:
        returns_compiled = True
        compiled_line = compiled_line or func.lineno
        returns_state_graph = False
    elif "StateGraph" in annotation:
        returns_state_graph = True

    analysis.returns_compiled = returns_compiled
    analysis.compiled_line = compiled_line
    analysis.returns_state_graph = returns_state_graph
    return analysis
