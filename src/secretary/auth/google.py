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

# Keyring keys for the OAuth application credentials (identify the app, not the user).
# The user's access/refresh token is stored separately under _KEYRING_KEY above.
_CLIENT_ID_KEY     = "google_client_id"
_CLIENT_SECRET_KEY = "google_client_secret"

# Fixed Google OAuth endpoints for installed/desktop apps — these never change.
_INSTALLED_APP_ENDPOINTS: dict = {
    "auth_uri":                    "https://accounts.google.com/o/oauth2/auth",
    "token_uri":                   "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "redirect_uris":               ["http://localhost"],
}


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


# ---------------------------------------------------------------------------
# OAuth application credentials (client_id / client_secret)
# ---------------------------------------------------------------------------

def save_google_client_credentials(client_id: str, client_secret: str) -> None:
    """Persist the OAuth app credentials to the keyring (or secure file fallback)."""
    from secretary.auth.keys import save_key
    save_key(_CLIENT_ID_KEY, client_id)
    save_key(_CLIENT_SECRET_KEY, client_secret)


def load_google_client_config() -> dict | None:
    """Return an InstalledAppFlow config dict built from keyring, or None if not configured."""
    from secretary.auth.keys import load_key
    client_id     = load_key(_CLIENT_ID_KEY)
    client_secret = load_key(_CLIENT_SECRET_KEY)
    if not (client_id and client_secret):
        return None
    return {
        "installed": {
            "client_id":     client_id,
            "client_secret": client_secret,
            **_INSTALLED_APP_ENDPOINTS,
        }
    }


# ---------------------------------------------------------------------------
# User token (access + refresh)
# ---------------------------------------------------------------------------

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
    config = load_google_client_config()
    if config:
        # Preferred path: credentials stored in keyring / secure file fallback.
        flow = InstalledAppFlow.from_client_config(config, SCOPES)
    elif settings.google_client_secret_path.exists():
        # Backward-compatibility: legacy JSON file on disk.
        flow = InstalledAppFlow.from_client_secrets_file(
            str(settings.google_client_secret_path), SCOPES
        )
    else:
        raise RuntimeError(
            "Google OAuth credentials not configured.\n"
            "Run 'sec auth' to enter your client ID and secret."
        )
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
