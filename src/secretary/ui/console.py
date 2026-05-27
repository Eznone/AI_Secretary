from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()

_PROMPT_STYLE = Style.from_dict({
    "prompt": "bold ansibrightgreen",
    "completion-menu.completion.current": "bg:ansicyan ansiblack",
    "completion-menu.completion": "bg:ansiblue ansiwhite",
    "completion-menu.meta.completion": "bg:ansiblue ansigray",
    "completion-menu.meta.completion.current": "bg:ansicyan ansiblack",
})


class SlashCommandCompleter(Completer):
    def __init__(self, commands: dict[str, str]) -> None:
        self._commands = commands

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if not text.startswith("/") or " " in text:
            return
        for cmd, desc in self._commands.items():
            if cmd.startswith(text):
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=HTML(f"<b>{cmd}</b>"),
                    display_meta=desc,
                )


def get_user_input(commands: dict[str, str]) -> str:
    """Prompt for user input with / command autocomplete."""
    return prompt(
        HTML("<prompt>You:</prompt> "),
        completer=SlashCommandCompleter(commands),
        complete_while_typing=True,
        style=_PROMPT_STYLE,
    ).strip()


def print_banner() -> None:
    title = Text("AI Secretary", style="bold cyan", justify="center")
    console.print(
        Panel(
            title,
            subtitle="[dim]/auth-llm for AI key · /auth-google for Google · Ctrl+C to exit[/dim]",
            border_style="cyan",
            padding=(0, 4),
        )
    )
    console.print()


def print_tool_call(name: str, inputs: dict) -> None:
    args = ", ".join(f"{k}={repr(v)}" for k, v in inputs.items())
    console.print(f"  [dim]⚙  {name}({args})[/dim]")


