from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


def print_banner() -> None:
    title = Text("AI Secretary", style="bold cyan", justify="center")
    console.print(
        Panel(
            title,
            subtitle="[dim]Ctrl+C to exit · sec auth to connect Google[/dim]",
            border_style="cyan",
            padding=(0, 4),
        )
    )
    console.print()


def print_tool_call(name: str, inputs: dict) -> None:
    args = ", ".join(f"{k}={repr(v)}" for k, v in inputs.items())
    console.print(f"  [dim]⚙  {name}({args})[/dim]")


def print_error(msg: str) -> None:
    console.print(f"[bold red]Error:[/bold red] {msg}")
