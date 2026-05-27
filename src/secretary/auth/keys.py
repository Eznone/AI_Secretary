"""Keyring-based storage for AI provider API keys.

Falls back to a restricted local file inside the platform data directory
when no system keyring backend is available (e.g. headless / WSL environments).
The fallback path is platform-correct via platform_dirs.APP_DATA_DIR.
"""

import json
import os
from pathlib import Path

import keyring
import keyring.errors

from secretary.platform_dirs import APP_DATA_DIR

_SERVICE = "secretary_api_keys"
_ACTIVE_PROVIDER_KEY = "__active_provider__"

# Stored alongside the database in the platform-correct data directory.
_FALLBACK_PATH = APP_DATA_DIR / ".keys.json"

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
    # O_CREAT|O_WRONLY|O_TRUNC with mode 0o600 creates the file owner-only in
    # a single syscall, eliminating the write-then-chmod TOCTOU window.
    # On Windows the mode bits are ignored by NTFS, but the call succeeds safely.
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(_FALLBACK_PATH), flags, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(data))


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
