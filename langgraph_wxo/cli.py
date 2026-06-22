"""``lgwxo`` command-line interface (Typer + Rich).

Commands wired here delegate to the library packages (config/validate/analyze/
emulate/templates). Output is human-readable Rich by default and machine-readable
JSON where ``--json`` is offered.
"""

from __future__ import annotations

import json as jsonlib
import platform
import shutil
import subprocess
from enum import StrEnum
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Annotated

import typer
from packaging.version import Version
from rich.console import Console
from rich.table import Table

from .compat import DEFAULT_MODEL_ALIAS, MIN_LANGGRAPH_VERSION, get_spec, known_spec_versions
from .config import LoadError, load_project
from .emulate import RunResult, load_mock_creds, run_agent
from .templates import TemplateError, UnknownTemplateError, render_template
from .validate import RULES, Report, Severity, run_all
from .validate.rules.limits import ELIGIBILITY_MESSAGE
from .version import __version__

app = typer.Typer(
    help="Build LangGraph agents and deploy them to IBM watsonx Orchestrate.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()

# Exit codes (stable contract; scripts and CI branch on these).
EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_DIR_EXISTS = 2
EXIT_UNKNOWN_TEMPLATE = 3
EXIT_RUNTIME = 4

_SEVERITY_STYLE = {
    Severity.ERROR: "bold red",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
}


class TemplateChoice(StrEnum):
    react_tools = "react-tools"
    minimal = "minimal"


class CheckpointerChoice(StrEnum):
    memory = "memory"
    sqlite = "sqlite"
    postgres = "postgres"


def _version_callback(value: bool) -> None:
    if value:
        console.print(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version."),
    ] = False,
    verbose: Annotated[bool, typer.Option("-v", "--verbose", help="Verbose output.")] = False,
    no_color: Annotated[bool, typer.Option("--no-color", help="Disable colored output.")] = False,
) -> None:
    """langgraph-wxo: scaffold, validate, and locally run LangGraph agents for WxO."""
    if no_color:
        console.no_color = True


@app.command()
def version() -> None:
    """Print the langgraph-wxo version."""
    console.print(__version__)


# --- new ---------------------------------------------------------------------


def _git_init(target: Path) -> bool:
    if shutil.which("git") is None:
        return False
    try:
        subprocess.run(
            ["git", "init", "-q"],
            cwd=target,
            capture_output=True,
            timeout=30,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return True


@app.command()
def new(  # noqa: PLR0913 - CLI options map 1:1 to user-facing flags
    name: Annotated[str, typer.Argument(help="Project name (also the agent name).")],
    template: Annotated[
        TemplateChoice, typer.Option("--template", help="Template to scaffold.")
    ] = TemplateChoice.react_tools,
    checkpointer: Annotated[
        CheckpointerChoice, typer.Option("--checkpointer", help="Checkpointer type.")
    ] = CheckpointerChoice.memory,
    model: Annotated[
        str, typer.Option("--model", help="Model id/alias for templates.")
    ] = DEFAULT_MODEL_ALIAS,
    directory: Annotated[
        Path | None, typer.Option("--dir", help="Target directory (default: ./<name>).")
    ] = None,
    no_git: Annotated[bool, typer.Option("--no-git", help="Do not initialize a git repo.")] = False,
) -> None:
    """Scaffold a new WxO-importable LangGraph project."""
    target = (directory or Path(name)).resolve()
    if target.exists() and any(target.iterdir()):
        console.print(f"[bold red]error:[/bold red] target directory is not empty: {target}")
        raise typer.Exit(EXIT_DIR_EXISTS)

    variables: dict[str, object] = {
        "name": name,
        "checkpointer": checkpointer.value,
        "model": model,
    }
    try:
        result = render_template(template.value, target, variables)
    except UnknownTemplateError as exc:
        console.print(f"[bold red]error:[/bold red] {exc}")
        raise typer.Exit(EXIT_UNKNOWN_TEMPLATE) from exc
    except TemplateError as exc:
        console.print(f"[bold red]error:[/bold red] {exc}")
        raise typer.Exit(EXIT_DIR_EXISTS) from exc

    git_ok = False if no_git else _git_init(target)

    table = Table(title=f"Created {name}", show_header=True, header_style="bold")
    table.add_column("File")
    for path in result.files:
        table.add_row(str(path.relative_to(target)))
    console.print(table)

    console.print(f"\n[green]✓[/green] scaffolded [bold]{template.value}[/bold] in {target}")
    if not no_git:
        console.print(
            f"[dim]git: {'initialized' if git_ok else 'skipped (git not available)'}[/dim]"
        )
    console.print("\n[bold]Next steps:[/bold]")
    console.print(f"  cd {target}")
    console.print("  lgwxo validate")
    console.print('  lgwxo run --message "hi"')
    if result.manifest.post_render:
        console.print(f"\n[dim]{result.manifest.post_render}[/dim]")


# --- validate / doctor -------------------------------------------------------


def _render_report(report: Report, *, strict: bool) -> None:
    groups = [
        ("Errors", report.errors),
        ("Warnings", report.warnings),
        ("Info", report.infos),
    ]
    for title, findings in groups:
        if not findings:
            continue
        console.print(f"\n[bold]{title}[/bold]")
        for f in findings:
            location = f.path
            if f.line is not None:
                location += f":{f.line}"
            style = _SEVERITY_STYLE[f.severity]
            console.print(f"  [{style}]{f.id}[/{style}] {location} — {f.message}")
            console.print(f"      [dim]fix:[/dim] {f.fix}")

    counts = (
        f"{len(report.errors)} error(s), "
        f"{len(report.warnings)} warning(s), {len(report.infos)} info"
    )
    if report.ok:
        console.print(f"\n[bold green]✓ valid[/bold green] — {counts}")
    else:
        suffix = " (strict)" if strict else ""
        console.print(f"\n[bold red]✗ invalid[/bold red]{suffix} — {counts}")


def _validate_impl(path: Path, target_spec: str | None, strict: bool, json_out: bool) -> None:
    try:
        project = load_project(path)
    except LoadError as exc:
        if json_out:
            console.print_json(jsonlib.dumps({"error": str(exc)}))
        else:
            console.print(f"[bold red]error:[/bold red] {exc}")
        raise typer.Exit(EXIT_FINDINGS) from exc

    try:
        spec = get_spec(target_spec)
    except KeyError as exc:
        console.print(f"[bold red]error:[/bold red] {exc}")
        raise typer.Exit(EXIT_FINDINGS) from exc

    report = run_all(project, spec, strict=strict)

    if json_out:
        console.print_json(jsonlib.dumps(report.to_dict()))
    else:
        _render_report(report, strict=strict)

    raise typer.Exit(EXIT_OK if report.ok else EXIT_FINDINGS)


_PathOpt = Annotated[Path, typer.Option("--path", help="Project directory.")]
_SpecOpt = Annotated[str | None, typer.Option("--target-spec", help="Import spec version.")]
_StrictOpt = Annotated[bool, typer.Option("--strict", help="Treat warnings as errors.")]
_JsonOpt = Annotated[bool, typer.Option("--json", help="Machine-readable JSON output.")]


@app.command()
def validate(
    path: _PathOpt = Path("."),
    target_spec: _SpecOpt = None,
    strict: _StrictOpt = False,
    json_out: _JsonOpt = False,
) -> None:
    """Validate a project against the WxO native-import contract."""
    _validate_impl(path, target_spec, strict, json_out)


@app.command()
def doctor(
    path: _PathOpt = Path("."),
    target_spec: _SpecOpt = None,
    strict: _StrictOpt = False,
    json_out: _JsonOpt = False,
) -> None:
    """Alias for ``validate``."""
    _validate_impl(path, target_spec, strict, json_out)


# --- run ---------------------------------------------------------------------


def _resolve_message(message: str | None, input_file: Path | None) -> str:
    if input_file is not None:
        data = jsonlib.loads(input_file.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "message" in data:
            return str(data["message"])
        if isinstance(data, dict) and isinstance(data.get("messages"), list) and data["messages"]:
            last = data["messages"][-1]
            return str(last.get("content", last) if isinstance(last, dict) else last)
        return str(data)
    return message or "hi"


def _render_run(result: RunResult) -> None:
    for msg in result.transcript:
        role = msg.get("type", "?")
        console.print(f"[bold]{role}[/bold]: {msg.get('content', '')}")
    if result.final_state_keys:
        console.print(f"\n[dim]final state keys: {', '.join(result.final_state_keys)}[/dim]")
    for notice in result.notices:
        console.print(f"[yellow]notice:[/yellow] {notice}")


@app.command()
def run(
    path: _PathOpt = Path("."),
    message: Annotated[str | None, typer.Option("--message", "-m", help="User message.")] = None,
    input_file: Annotated[
        Path | None, typer.Option("--input", help="JSON input file ({'message': ...}).")
    ] = None,
    mock_creds: Annotated[
        Path | None, typer.Option("--mock-creds", help="JSON map of extra mock credentials.")
    ] = None,
    stream: Annotated[bool, typer.Option("--stream/--no-stream", help="Stream output.")] = False,
) -> None:
    """Run the agent locally the way WxO will (compile + inject mock creds + 1 turn)."""
    try:
        project = load_project(path)
    except LoadError as exc:
        console.print(f"[bold red]error:[/bold red] {exc}")
        raise typer.Exit(EXIT_FINDINGS) from exc

    extra = load_mock_creds(mock_creds) if mock_creds is not None else None
    text = _resolve_message(message, input_file)

    result = run_agent(project, text, extra_creds=extra)

    if result.status == "ok":
        _render_run(result)
        raise typer.Exit(EXIT_OK)

    if result.status == "contract":
        rule_id = result.finding_id or "LGWXO000"
        title = RULES[rule_id].title if rule_id in RULES else "contract violation"
        console.print(f"[bold red]{rule_id}[/bold red] {title} — {result.message}")
        raise typer.Exit(EXIT_FINDINGS)

    # runtime / error
    console.print("[bold red]agent runtime error[/bold red]")
    if result.message:
        console.print(result.message)
    if result.stderr:
        console.print(f"[dim]{result.stderr}[/dim]")
    raise typer.Exit(EXIT_RUNTIME)


# --- check-env ---------------------------------------------------------------


def _resolved_langgraph_version() -> str | None:
    try:
        return pkg_version("langgraph")
    except PackageNotFoundError:
        return None


def _orchestrate_version() -> str | None:
    if shutil.which("orchestrate") is None:
        return None
    try:
        out = subprocess.run(
            ["orchestrate", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "installed (version unknown)"
    return (out.stdout or out.stderr).strip() or "installed (version unknown)"


@app.command(name="check-env")
def check_env(json_out: _JsonOpt = False) -> None:
    """Report Python/langgraph versions and WxO eligibility reminders."""
    py = platform.python_version()
    py_ok = Version(py) >= Version("3.11")
    lg = _resolved_langgraph_version()
    lg_ok = lg is not None and Version(lg) >= Version(MIN_LANGGRAPH_VERSION)
    orchestrate = _orchestrate_version()
    spec = get_spec()

    if json_out:
        payload = {
            "python": {"version": py, "ok": py_ok, "required": ">=3.11"},
            "langgraph": {
                "version": lg,
                "ok": lg_ok,
                "required": f">={MIN_LANGGRAPH_VERSION}",
            },
            "orchestrate_cli": orchestrate,
            "target_spec": spec.version,
            "eligibility": ELIGIBILITY_MESSAGE,
        }
        console.print_json(jsonlib.dumps(payload))
        raise typer.Exit(EXIT_OK if py_ok and lg_ok else EXIT_FINDINGS)

    table = Table(title="lgwxo check-env", show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Value")
    table.add_column("Status")

    def mark(ok: bool) -> str:
        return "[green]ok[/green]" if ok else "[red]fail[/red]"

    table.add_row("Python", py, mark(py_ok) + " [dim](>=3.11)[/dim]")
    table.add_row(
        "langgraph",
        lg or "[red]not installed[/red]",
        mark(lg_ok) + f" [dim](>={MIN_LANGGRAPH_VERSION})[/dim]",
    )
    table.add_row("orchestrate CLI", orchestrate or "[dim]not found[/dim]", "-")
    table.add_row("target spec", f"{spec.version} (ADK {spec.adk_version})", "-")
    console.print(table)
    console.print(f"\n[bold]Eligibility:[/bold] {ELIGIBILITY_MESSAGE}")
    console.print(f"[dim]Known import specs: {', '.join(known_spec_versions())}[/dim]")

    raise typer.Exit(EXIT_OK if py_ok and lg_ok else EXIT_FINDINGS)


if __name__ == "__main__":
    app()
