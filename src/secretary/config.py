from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

XDG_DATA = Path.home() / ".local" / "share" / "secretary"
XDG_DATA.mkdir(parents=True, exist_ok=True)

_PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
    )

    anthropic_api_key: str
    anthropic_model: str = "claude-opus-4-7"

    @field_validator("anthropic_api_key")
    @classmethod
    def _require_api_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "ANTHROPIC_API_KEY is not set. "
                "Add it to your .env file or set it as an environment variable."
            )
        return v

    google_client_secret_path: Path = _PROJECT_ROOT / "credentials" / "google_client_secret.json"
    google_token_keyring_service: str = "secretary_google_oauth"

    db_path: Path = XDG_DATA / "history.db"
    data_dir: Path = XDG_DATA


settings = Settings()
