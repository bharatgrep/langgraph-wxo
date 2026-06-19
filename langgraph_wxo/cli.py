import typer

from .version import __version__

app = typer.Typer(help="Build LangGraph agents and deploy them to IBM watsonx Orchestrate.")


@app.callback()
def main() -> None:
    """Build LangGraph agents and deploy them to IBM watsonx Orchestrate."""


@app.command()
def version() -> None:
    """Print the langgraph-wxo version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
