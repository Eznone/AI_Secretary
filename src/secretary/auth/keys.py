"""Keyring-based storage for AI provider API keys.

Falls back to a restricted local file (~/.local/share/secretary/.keys.json)
when no system keyring backend is available (e.g. headless / WSL environments).
"""

import json
import os
import stat
from pathlib import Path

import keyring
import keyring.errors

_SERVICE = "secretary_api_keys"
_ACTIVE_PROVIDER_KEY = "__active_provider__"

_FALLBACK_PATH = Path.home() / ".local" / "share" / "secretary" / ".keys.json"

PROVIDERS: dict[str, str] = {
    "claude": "Claude (Anthropic)",
    "gemini": "Gemini (Google)",
    "groq":   "Groq",
}


# ---------------------------------------------------------------------------
# Fallback file store (mode 600, owner-only)
# ---------------------------------------------------------------------------

def _read_fallback() -> dict:
    if not _FALLBACK_PATH.exists():
        return {}
    try:
        return json.loads(_FALLBACK_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_fallback(data: dict) -> None:
    _FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    _FALLBACK_PATH.write_text(json.dumps(data))
    _FALLBACK_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def save_key(provider: str, key: str) -> None:
    try:
        keyring.set_password(_SERVICE, provider, key)
    except keyring.errors.NoKeyringError:
        data = _read_fallback()
        data[provider] = key
        _write_fallback(data)


def load_key(provider: str) -> str | None:
    try:
        return keyring.get_password(_SERVICE, provider)
    except keyring.errors.NoKeyringError:
        return _read_fallback().get(provider)


def delete_key(provider: str) -> None:
    try:
        keyring.delete_password(_SERVICE, provider)
    except (keyring.errors.PasswordDeleteError, keyring.errors.NoKeyringError):
        data = _read_fallback()
        data.pop(provider, None)
        _write_fallback(data)


def save_active_provider(provider: str) -> None:
    try:
        keyring.set_password(_SERVICE, _ACTIVE_PROVIDER_KEY, provider)
    except keyring.errors.NoKeyringError:
        data = _read_fallback()
        data[_ACTIVE_PROVIDER_KEY] = provider
        _write_fallback(data)


def load_active_provider() -> str | None:
    try:
        return keyring.get_password(_SERVICE, _ACTIVE_PROVIDER_KEY)
    except keyring.errors.NoKeyringError:
        return _read_fallback().get(_ACTIVE_PROVIDER_KEY)
