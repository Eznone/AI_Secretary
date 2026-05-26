"""
Core agentic execution loop — provider-agnostic.

All provider-specific logic lives in agent/providers/. This module only knows
about the neutral Conversation format defined in agent/providers/base.py.
"""

from datetime import date

from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner
from rich.table import Table

from secretary.agent.providers import get_provider
from secretary.agent.providers.base import (
    make_assistant_turn,
    make_tool_results_turn,
    make_user_turn,
)
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


def run_session() -> None:
    """Outer REPL: read user input and dispatch each message to _agent_turn()."""
    session_id = create_session()
    conversation: list[dict] = []  # neutral Conversation — see providers/base.py

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

        conversation.append(make_user_turn(user_input))
        save_message(session_id, "user", user_input)

        try:
            _agent_turn(conversation, session_id)
        except Exception as exc:
            # Catching broad Exception so provider SDK errors (anthropic.APIError,
            # groq.APIError, google.api_core errors, etc.) all surface uniformly
            # without importing any provider SDK here.
            console.print(f"[red]Error:[/red] {exc}")


def _handle_slash_command(raw: str) -> None:
    cmd = raw.split()[0].lower()

    if cmd == "/authenticate":
        from secretary.ui.authenticate import run_authenticate
        run_authenticate()
        # get_provider() is called fresh each _agent_turn(), so no cache to
        # invalidate here — the new key is picked up automatically next turn.

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
    table.add_row("/help",         "Show this message")
    table.add_row("exit / quit",   "End the session")
    console.print()
    console.print(table)
    console.print()


def _agent_turn(conversation: list[dict], session_id: int) -> None:
    """Run the multi-turn tool-use loop for one user request.

    Calls get_provider() fresh each time so that a /authenticate run mid-session
    is picked up on the very next message. The loop continues until the provider
    returns TurnResult(done=True), meaning it produced a final text answer.
    """
    provider = get_provider()
    system = SYSTEM_PROMPT.format(today=date.today().isoformat())
    tools = get_tool_schemas()

    while True:
        with Live(
            Spinner("dots", text="[dim]Thinking…[/dim]"),
            console=console,
            transient=True,
        ):
            result = provider.complete(system, conversation, tools)

        if not result.done:
            # The provider wants to call tools. Execute each one, collect results,
            # then append both the tool-calling turn and the results to the
            # conversation before looping for the provider's next response.
            tool_results = []
            for tc in result.tool_calls:
                print_tool_call(tc.name, tc.inputs)
                try:
                    output = dispatch(tc.name, tc.inputs)
                except Exception as exc:
                    output = f"Error executing {tc.name}: {exc}"
                tool_results.append({
                    "id": tc.id,
                    "name": tc.name,    # required by Gemini; ignored by Claude/Groq
                    "content": str(output),
                })

            conversation.append(make_assistant_turn(tool_calls=result.tool_calls))
            conversation.append(make_tool_results_turn(tool_results))

        else:
            # Final answer — render, save, and break the tool-use loop.
            final_text = result.text or ""
            console.print("\n[bold blue]Secretary:[/bold blue]")
            console.print(Markdown(final_text))
            console.print()
            conversation.append(make_assistant_turn(text=final_text))
            save_message(session_id, "assistant", final_text)
            break
