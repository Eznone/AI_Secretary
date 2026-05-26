"""Google OAuth2 flow with token persistence.

Tokens are stored in the OS keyring when available. On headless environments
(WSL, CI, servers) where no keyring backend exists, falls back to a restricted
JSON file inside the platform data directory (mode 600, owner-only).
"""

import json

import keyring
import keyring.errors
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from secretary.config import settings
from secretary.platform_dirs import APP_DATA_DIR, secure_file

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]

_KEYRING_KEY = "google_oauth_token"

# Used when no system keyring is available (e.g. headless Linux / WSL).
_FALLBACK_PATH = APP_DATA_DIR / ".google_token.json"


# ---------------------------------------------------------------------------
# Fallback file store (mode 600, owner-only)
# ---------------------------------------------------------------------------

def _read_token_fallback() -> str | None:
    if not _FALLBACK_PATH.exists():
        return None
    try:
        return _FALLBACK_PATH.read_text()
    except OSError:
        return None


def _write_token_fallback(raw: str) -> None:
    _FALLBACK_PATH.parent.mkdir(parents=True, exist_ok=True)
    _FALLBACK_PATH.write_text(raw)
    secure_file(_FALLBACK_PATH)  # owner-only on Unix; no-op on Windows


# ---------------------------------------------------------------------------
# Token load / save (keyring with file fallback)
# ---------------------------------------------------------------------------

def _load_token() -> Credentials | None:
    try:
        raw = keyring.get_password(settings.google_token_keyring_service, _KEYRING_KEY)
    except keyring.errors.NoKeyringError:
        raw = _read_token_fallback()
    if not raw:
        return None
    try:
        return Credentials.from_authorized_user_info(json.loads(raw), SCOPES)
    except Exception:
        return None


def _save_token(creds: Credentials) -> None:
    raw = creds.to_json()
    try:
        keyring.set_password(settings.google_token_keyring_service, _KEYRING_KEY, raw)
    except keyring.errors.NoKeyringError:
        _write_token_fallback(raw)


def get_credentials() -> Credentials | None:
    creds = _load_token()
    if creds is None:
        return None
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)
        return creds
    return None


def run_oauth_flow() -> Credentials:
    client_secret = settings.google_client_secret_path
    if not client_secret.exists():
        raise FileNotFoundError(
            f"Google client secret not found at {client_secret}.\n"
            "Download it from https://console.cloud.google.com/ and place it there."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    # port=0 → OS picks a random ephemeral port (no predictable attack surface)
    creds = flow.run_local_server(port=0)
    _save_token(creds)
    return creds


def _authenticated_service(api: str, version: str):
    creds = get_credentials()
    if creds is None:
        creds = run_oauth_flow()
    return build(api, version, credentials=creds)


def get_calendar_service():
    return _authenticated_service("calendar", "v3")


def get_gmail_service():
    return _authenticated_service("gmail", "v1")
