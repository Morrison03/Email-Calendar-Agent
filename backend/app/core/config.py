"""Application settings loaded from environment variables.

This centralizes secrets, database settings, and app preferences so the rest
of the code can import a single settings object.
"""

from __future__ import annotations

from datetime import time
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[3]
ENV_FILE = BASE_DIR / ".env"

WEEKDAY_NAME_TO_INDEX = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "tues": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}


class Settings(BaseSettings):
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str

    openai_api_key: str = ""

    oauthlib_relax_token_scope: str = "0"

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

    calendar_lookahead_days: int = 14
    max_slot_suggestions: int = 5
    minimum_notice_minutes: int = 60
    allowed_meeting_days: str = "mon,tue,wed,thu,fri"

    notification_poll_seconds: int = 60
    notification_repeat_minutes: int = 10

    secret_key: str = "change-this-in-env"

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
    )

    @field_validator("workday_start", "workday_end")
    @classmethod
    def validate_time_string(cls, value: str) -> str:
        try:
            hour_text, minute_text = value.split(":")
            hour = int(hour_text)
            minute = int(minute_text)
        except ValueError as exc:
            raise ValueError("Time values must be in HH:MM format.") from exc

        if hour < 0 or hour > 23:
            raise ValueError("Hour must be between 00 and 23.")

        if minute < 0 or minute > 59:
            raise ValueError("Minute must be between 00 and 59.")

        return f"{hour:02d}:{minute:02d}"

    @field_validator("default_meeting_lengths")
    @classmethod
    def validate_default_meeting_lengths(cls, value: str) -> str:
        lengths = cls._parse_positive_int_csv(value)
        if not lengths:
            raise ValueError("default_meeting_lengths must contain at least one value.")
        return ",".join(str(length) for length in lengths)

    @field_validator("allowed_meeting_days")
    @classmethod
    def validate_allowed_meeting_days(cls, value: str) -> str:
        normalized_days = cls._parse_allowed_meeting_days(value)
        if not normalized_days:
            raise ValueError("allowed_meeting_days must contain at least one weekday.")
        return ",".join(normalized_days)

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:"
            f"{self.postgres_password}@{self.postgres_host}:"
            f"{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def workday_start_time(self) -> time:
        return self._parse_time(self.workday_start)

    @property
    def workday_end_time(self) -> time:
        return self._parse_time(self.workday_end)

    @property
    def default_meeting_lengths_minutes(self) -> list[int]:
        return self._parse_positive_int_csv(self.default_meeting_lengths)

    @property
    def default_meeting_duration_minutes(self) -> int:
        return self.default_meeting_lengths_minutes[0]

    @property
    def allowed_meeting_day_indexes(self) -> set[int]:
        day_names = self._parse_allowed_meeting_days(self.allowed_meeting_days)
        return {WEEKDAY_NAME_TO_INDEX[day_name] for day_name in day_names}

    @staticmethod
    def _parse_time(value: str) -> time:
        hour_text, minute_text = value.split(":")
        return time(hour=int(hour_text), minute=int(minute_text))

    @staticmethod
    def _parse_positive_int_csv(value: str) -> list[int]:
        parsed_values: list[int] = []
        seen: set[int] = set()

        for raw_item in value.split(","):
            cleaned = raw_item.strip()
            if not cleaned:
                continue

            number = int(cleaned)
            if number <= 0:
                raise ValueError("Values must be positive integers.")

            if number in seen:
                continue

            seen.add(number)
            parsed_values.append(number)

        parsed_values.sort()
        return parsed_values

    @staticmethod
    def _parse_allowed_meeting_days(value: str) -> list[str]:
        parsed_days: list[str] = []
        seen: set[str] = set()

        for raw_item in value.split(","):
            cleaned = raw_item.strip().casefold()
            if not cleaned:
                continue

            if cleaned not in WEEKDAY_NAME_TO_INDEX:
                raise ValueError(f"Unsupported weekday: {raw_item}")

            canonical_name = next(
                name
                for name, index in WEEKDAY_NAME_TO_INDEX.items()
                if index == WEEKDAY_NAME_TO_INDEX[cleaned] and len(name) == 3
            )

            if canonical_name in seen:
                continue

            seen.add(canonical_name)
            parsed_days.append(canonical_name)

        return parsed_days


settings = Settings()