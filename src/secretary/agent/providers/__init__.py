"""
Provider factory.

Call get_provider() to get the adapter for whichever LLM the user has selected.
Adapters are imported lazily so unused provider SDKs are never loaded.

Why construct a new adapter each call instead of caching?
  The user can run /authenticate mid-session to switch providers. Calling
  get_provider() fresh at the start of each _agent_turn() means the change
  takes effect on the very next message without restarting the session.
"""

from __future__ import annotations

from secretary.agent.providers.base import ProviderAdapter
from secretary.config import settings


def get_provider() -> ProviderAdapter:
    """Return the adapter matching the currently active provider.

    Raises RuntimeError if the provider's API key is not configured.
    Raises ValueError if the provider name is unrecognised.
    """
    provider = settings.active_provider

    if provider == "claude":
        from secretary.agent.providers.claude import ClaudeAdapter
        return ClaudeAdapter()

    if provider == "gemini":
        from secretary.agent.providers.gemini import GeminiAdapter
        return GeminiAdapter()

    if provider == "groq":
        from secretary.agent.providers.groq import GroqAdapter
        return GroqAdapter()

    raise ValueError(
        f"Unknown provider {provider!r}. "
        "Expected one of: 'claude', 'gemini', 'groq'. "
        "Run /authenticate to reconfigure."
    )
