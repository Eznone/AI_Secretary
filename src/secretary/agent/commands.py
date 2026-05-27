"""Slash command registry and dispatch for the interactive session."""

from rich.table import Table

from secretary.ui.console import console

SLASH_COMMANDS: dict[str, str] = {
    "/auth-llm":    "Set up or change your AI provider API key (Claude / Gemini / Groq)",
    "/auth-google": "Connect your Google account (Calendar + Gmail)",
    "/help":        "Show available commands",
}


def handle(raw: str) -> None:
    """Dispatch a raw /command string to the appropriate handler."""
    cmd = raw.split()[0].lower()

    if cmd == "/auth-llm":
        from secretary.ui.authenticate import run_authenticate
        run_authenticate()
        # get_provider() is called fresh each _agent_turn(), so no cache to
        # invalidate here — the new key is picked up automatically next turn.

    elif cmd == "/auth-google":
        from secretary.ui.authenticate import run_google_auth
        run_google_auth()

    elif cmd == "/help":
        _print_help()

    else:
        console.print(
            f"[yellow]Unknown command:[/yellow] {cmd}  "
            "— type [bold cyan]/help[/bold cyan] for available commands.\n"
        )


def _print_help() -> None:
    table = Table(border_style="dim", show_header=False, padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column(style="white")
    for cmd, desc in SLASH_COMMANDS.items():
        table.add_row(cmd, desc)
    table.add_row("exit / quit", "End the session")
    console.print()
    console.print(table)
    console.print()
