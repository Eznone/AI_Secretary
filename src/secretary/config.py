from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

XDG_DATA = Path.home() / ".local" / "share" / "secretary"
XDG_DATA.mkdir(parents=True, exist_ok=True)

_PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
    )

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-opus-4-7"

    gemini_api_key: str | None = None
    groq_api_key: str | None = None

    google_client_secret_path: Path = _PROJECT_ROOT / "credentials" / "google_client_secret.json"
    google_token_keyring_service: str = "secretary_google_oauth"

    db_path: Path = XDG_DATA / "history.db"
    data_dir: Path = XDG_DATA

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
