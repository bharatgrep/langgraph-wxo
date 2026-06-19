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
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as pkg_version
from pathlib import Path
from typing import Annotated

import typer
from packaging.version import Version
from rich.console import Console
from rich.table import Table

from .compat import MIN_LANGGRAPH_VERSION, get_spec, known_spec_versions
from .config import LoadError, load_project
from .validate import Report, Severity, run_all
from .validate.rules.limits import ELIGIBILITY_MESSAGE
from .version import __version__

app = typer.Typer(
    help="Build LangGraph agents and deploy them to IBM watsonx Orchestrate.",
    no_args_is_help=True,
    add_completion=False,
)

console = Console()

# Exit codes (kept consistent with TECHNICAL_SPECIFICATION §7).
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
