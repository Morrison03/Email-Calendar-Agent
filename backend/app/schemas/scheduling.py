from __future__ import annotations

from pydantic import BaseModel, Field


class SchedulingIntentResult(BaseModel):
    has_scheduling_intent: bool = False
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requested_duration_minutes: int | None = None
    mentioned_dates: list[str] = Field(default_factory=list)
    mentioned_times: list[str] = Field(default_factory=list)
    mentioned_time_ranges: list[str] = Field(default_factory=list)
    timezone_clues: list[str] = Field(default_factory=list)
    notes: str | None = None