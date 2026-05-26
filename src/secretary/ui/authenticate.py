"""Interactive /authenticate flow for selecting and storing an AI provider API key."""

import questionary
from rich.panel import Panel
from rich.text import Text

from secretary.auth.keys import PROVIDERS, load_active_provider, load_key, save_active_provider, save_key
from secretary.ui.console import console

_INSTRUCTIONS: dict[str, str] = {
    "claude": "Get your key at [link=https://console.anthropic.com/settings/keys]console.anthropic.com/settings/keys[/link]",
    "gemini": "Get your key at [link=https://aistudio.google.com/app/apikey]aistudio.google.com/app/apikey[/link]",
    "groq":   "Get your key at [link=https://console.groq.com/keys]console.groq.com/keys[/link]",
}

_QUESTIONARY_STYLE = questionary.Style([
    ("selected",    "fg:cyan bold"),
    ("pointer",     "fg:cyan bold"),
    ("highlighted", "fg:cyan"),
    ("question",    "bold"),
    ("answer",      "fg:cyan bold"),
])


def run_authenticate() -> None:
    console.print()
    console.print(
        Panel(
            Text("API Key Setup", style="bold cyan", justify="center"),
            subtitle="[dim]Arrow keys to select · Enter to confirm · Ctrl+C to cancel[/dim]",
            border_style="cyan",
            padding=(0, 4),
        )
    )
    console.print()

    active = load_active_provider()
    choices = [
        questionary.Choice(
            title=f"{'● ' if active == k else '  '}{label}",
            value=k,
        )
        for k, label in PROVIDERS.items()
    ]

    try:
        provider: str | None = questionary.select(
            "Select a provider:",
            choices=choices,
            style=_QUESTIONARY_STYLE,
        ).ask()
    except KeyboardInterrupt:
        provider = None

    if provider is None:
        console.print("[dim]Authentication cancelled.[/dim]\n")
        return

    existing = load_key(provider)
    console.print()
    console.print(f"  {_INSTRUCTIONS[provider]}")
    if existing:
        masked = existing[:10] + "…"
        console.print(f"  [dim]Existing key for {PROVIDERS[provider]}: {masked}  (enter a new one to replace)[/dim]")
    console.print()

    try:
        api_key: str | None = questionary.password(
            f"Paste your {PROVIDERS[provider]} API key:",
            style=_QUESTIONARY_STYLE,
        ).ask()
    except KeyboardInterrupt:
        api_key = None

    if not api_key or not api_key.strip():
        console.print("[yellow]No key entered — nothing saved.[/yellow]\n")
        return

    api_key = api_key.strip()
    save_key(provider, api_key)
    save_active_provider(provider)

    # Patch the live settings object so the current session picks up the new key
    # without requiring a restart.
    from secretary import config as _cfg
    if provider == "claude":
        _cfg.settings.anthropic_api_key = api_key
    elif provider == "gemini":
        _cfg.settings.gemini_api_key = api_key
    elif provider == "groq":
        _cfg.settings.groq_api_key = api_key

    console.print()
    console.print(f"  [bold green]✓[/bold green] Key saved for [bold cyan]{PROVIDERS[provider]}[/bold cyan].")
    console.print(f"  Active provider set to [bold cyan]{PROVIDERS[provider]}[/bold cyan].")
    console.print()


def run_google_setup() -> bool:
    """Prompt for Google OAuth client_id and client_secret and save them to the keyring.

    Returns True if credentials were saved, False if the user cancelled.
    """
    from secretary.auth.google import load_google_client_config, save_google_client_credentials

    console.print()
    console.print(
        Panel(
            Text("Google OAuth Setup", style="bold cyan", justify="center"),
            subtitle="[dim]Find these at console.cloud.google.com → APIs & Services → Credentials[/dim]",
            border_style="cyan",
            padding=(0, 4),
        )
    )
    console.print()
    console.print("  [dim]Create an OAuth 2.0 Client ID (Desktop app type), then paste the two values below.[/dim]")

    existing = load_google_client_config()
    if existing:
        console.print("  [dim]Existing credentials found — enter new values to replace, or press Enter to keep.[/dim]")
    console.print()

    try:
        client_id: str | None = questionary.text(
            "Client ID:",
            style=_QUESTIONARY_STYLE,
        ).ask()
        if not client_id or not client_id.strip():
            console.print("[yellow]No client ID entered — nothing saved.[/yellow]\n")
            return False

        client_secret: str | None = questionary.password(
            "Client Secret:",
            style=_QUESTIONARY_STYLE,
        ).ask()
        if not client_secret or not client_secret.strip():
            console.print("[yellow]No client secret entered — nothing saved.[/yellow]\n")
            return False

    except KeyboardInterrupt:
        console.print("\n[yellow]Setup cancelled.[/yellow]\n")
        return False

    save_google_client_credentials(client_id.strip(), client_secret.strip())
    console.print()
    console.print("  [bold green]✓[/bold green] Google credentials saved.")
    console.print()
    return True
