"""Application settings loaded from environment variables.

This centralizes secrets, database settings, and app preferences so the rest
of the code can import a single settings object.
"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    openai_api_key: str = ""

    postgres_db: str
    postgres_user: str
    postgres_password: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    app_timezone: str = "America/Denver"
    workday_start: str = "09:00"
    workday_end: str = "17:00"
    default_meeting_lengths: str = "15,30,45,60"
    meeting_buffer_minutes: int = 15

    secret_key: str = "change-this-in-env"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()