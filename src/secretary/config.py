from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from secretary.platform_dirs import ensure_data_dir

# Platform-correct data directory (created on first import).
# Windows: %LOCALAPPDATA%\secretary  |  macOS: ~/Library/Application Support/secretary
# Linux:   ~/.local/share/secretary
APP_DATA_DIR = ensure_data_dir()

_PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
    )

    # Set DEBUG=true in .env or as an environment variable to enable verbose
    # error output (full tracebacks with file paths and line numbers).
    debug: bool = False

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4.6"
    gemini_model: str = "gemini-2.0-flash"
    groq_model: str = "llama-3.3-70b-versatile"

    gemini_api_key: str | None = None
    groq_api_key: str | None = None

    google_client_secret_path: Path = _PROJECT_ROOT / "credentials" / "google_client_secret.json"
    google_token_keyring_service: str = "secretary_google_oauth"

    db_path: Path = APP_DATA_DIR / "history.db"
    data_dir: Path = APP_DATA_DIR

    @model_validator(mode="after")
    def _load_from_keyring(self) -> "Settings":
        from secretary.auth.keys import load_key
        if self.anthropic_api_key is None:
            self.anthropic_api_key = load_key("claude")
        if self.gemini_api_key is None:
            self.gemini_api_key = load_key("gemini")
        if self.groq_api_key is None:
            self.groq_api_key = load_key("groq")
        return self

    @property
    def active_provider(self) -> str:
        from secretary.auth.keys import load_active_provider
        return load_active_provider() or "claude"

    @property
    def active_api_key(self) -> str | None:
        provider = self.active_provider
        if provider == "claude":
            return self.anthropic_api_key
        if provider == "gemini":
            return self.gemini_api_key
        if provider == "groq":
            return self.groq_api_key
        return None

    @property
    def is_configured(self) -> bool:
        return bool(self.active_api_key)


settings = Settings()
