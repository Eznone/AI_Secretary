"""Core agentic execution loop using Anthropic tool-use."""

from datetime import date

import anthropic
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner

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
        _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def run_session() -> None:
    session_id = create_session()
    conversation: list[dict] = []

    console.print("[bold cyan]Secretary ready.[/bold cyan] Type your request, or [dim]Ctrl+C[/dim] to exit.\n")

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

        conversation.append({"role": "user", "content": user_input})
        save_message(session_id, "user", user_input)

        try:
            _agent_turn(conversation, session_id)
        except anthropic.APIError as exc:
            console.print(f"[red]API error:[/red] {exc}")
        except Exception as exc:
            console.print(f"[red]Unexpected error:[/red] {exc}")


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

            # Feed assistant response + tool results back into the conversation
            conversation.append({"role": "assistant", "content": response.content})
            conversation.append({"role": "user", "content": tool_results})

        else:
            # stop_reason == "end_turn" — final text response
            final_text = next(
                (b.text for b in response.content if hasattr(b, "text")),
                "",
            )
            console.print("\n[bold blue]Secretary:[/bold blue]")
            console.print(Markdown(final_text))
            console.print()
            save_message(session_id, "assistant", final_text)
            break
