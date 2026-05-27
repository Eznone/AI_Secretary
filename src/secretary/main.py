"""Entry point for the `sec` CLI command."""

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="sec",
    help="AI Secretary — your terminal-based personal assistant.",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """Start an interactive AI Secretary session."""
    if ctx.invoked_subcommand is not None:
        return

    # Lazy imports keep startup fast when running subcommands
    from secretary.agent.loop import run_session
    from secretary.storage.db import init_db
    from secretary.ui.console import print_banner

    # Ensure tools are registered before the loop starts
    import secretary.integrations.calendar  # noqa: F401
    import secretary.integrations.gmail     # noqa: F401

    init_db()
    print_banner()
    run_session()


@app.command()
def auth() -> None:
    """Set up Google OAuth credentials and authorize Calendar + Gmail access."""
    from secretary.ui.authenticate import run_google_auth
    run_google_auth()


@app.command()
def history(
    n: int = typer.Option(10, "--last", "-n", help="Number of recent sessions to show"),
) -> None:
    """Show recent session history."""
    from secretary.storage.db import init_db, list_sessions

    init_db()
    sessions = list_sessions(n)

    if not sessions:
        console.print("[dim]No sessions found.[/dim]")
        return

    table = Table(title="Recent Sessions", border_style="cyan")
    table.add_column("ID", style="dim", width=6)
    table.add_column("Created At", style="cyan")
    table.add_column("Summary", style="white")

    for s in sessions:
        table.add_row(
            str(s["id"]),
            s["created_at"],
            s["summary"] or "[dim]—[/dim]",
        )

    console.print(table)


@app.command()
def context() -> None:
    """Show persisted user context (key-value facts the AI remembers)."""
    from secretary.storage.db import get_all_user_context, init_db

    init_db()
    ctx = get_all_user_context()

    if not ctx:
        console.print("[dim]No user context stored yet.[/dim]")
        return

    table = Table(title="User Context", border_style="cyan")
    table.add_column("Key", style="bold cyan")
    table.add_column("Value", style="white")

    for key, value in ctx.items():
        table.add_row(key, value)

    console.print(table)


if __name__ == "__main__":
    app()
