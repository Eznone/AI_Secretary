"""Core agentic execution loop using Anthropic tool-use."""

from datetime import date

import anthropic
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.table import Table

from secretary.agent.registry import dispatch, get_tool_schemas
from secretary.config import settings
from secretary.storage.db import create_session, save_message
from secretary.ui.console import console, print_tool_call

SYSTEM_PROMPT = """\
You are an AI Secretary running locally in the user's terminal. \
You have access to tools for Google Calendar and Gmail. \
Today's date is {today}. \
Be concise, direct, and proactive. \
Always ask for confirmation before creating, modifying, or deleting data.\
"""

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        key = settings.anthropic_api_key
        if not key:
            raise RuntimeError(
                "No Anthropic API key configured. Run /authenticate to set one up."
            )
        _client = anthropic.Anthropic(api_key=key)
    return _client


def run_session() -> None:
    session_id = create_session()
    conversation: list[dict] = []

    if not settings.is_configured:
        console.print(
            "[yellow]No API key configured.[/yellow] "
            "Run [bold cyan]/authenticate[/bold cyan] to get started.\n"
        )
    else:
        console.print(
            "[bold cyan]Secretary ready.[/bold cyan] "
            "Type your request, or [dim]Ctrl+C[/dim] to exit.\n"
        )

    while True:
        try:
            user_input = console.input("[bold green]You:[/bold green] ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "bye"}:
            console.print("[dim]Session ended.[/dim]")
            break

        if user_input.startswith("/"):
            _handle_slash_command(user_input)
            continue

        if not settings.is_configured:
            console.print(
                "[yellow]No API key configured.[/yellow] "
                "Run [bold cyan]/authenticate[/bold cyan] first.\n"
            )
            continue

        conversation.append({"role": "user", "content": user_input})
        save_message(session_id, "user", user_input)

        try:
            _agent_turn(conversation, session_id)
        except anthropic.APIError as exc:
            console.print(f"[red]API error:[/red] {exc}")
        except Exception as exc:
            console.print(f"[red]Unexpected error:[/red] {exc}")


def _handle_slash_command(raw: str) -> None:
    cmd = raw.split()[0].lower()

    if cmd == "/authenticate":
        from secretary.ui.authenticate import run_authenticate

        run_authenticate()
        global _client
        _client = None  # force client rebuild with the new key
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
    table.add_row("/authenticate", "Set up or change your AI provider API key")
    table.add_row("/help", "Show this message")
    table.add_row("exit / quit", "End the session")
    console.print()
    console.print(table)
    console.print()


def _agent_turn(conversation: list[dict], session_id: int) -> None:
    client = _get_client()
    system = SYSTEM_PROMPT.format(today=date.today().isoformat())
    tools = get_tool_schemas()

    while True:
        with Live(
            Spinner("dots", text="[dim]Thinking…[/dim]"),
            console=console,
            transient=True,
        ):
            response = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=4096,
                system=system,
                tools=tools,
                messages=conversation,
            )

        if response.stop_reason == "tool_use":
            tool_results: list[dict] = []

            for block in response.content:
                if block.type == "tool_use":
                    print_tool_call(block.name, block.input)
                    try:
                        result = dispatch(block.name, block.input)
                    except Exception as exc:
                        result = f"Error executing {block.name}: {exc}"
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        }
                    )

            conversation.append({"role": "assistant", "content": response.content})
            conversation.append({"role": "user", "content": tool_results})

        else:
            final_text = next(
                (b.text for b in response.content if hasattr(b, "text")),
                "",
            )
            console.print("\n[bold blue]Secretary:[/bold blue]")
            console.print(Markdown(final_text))
            console.print()
            save_message(session_id, "assistant", final_text)
            break
