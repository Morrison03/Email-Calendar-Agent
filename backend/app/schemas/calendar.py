from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class CalendarBusyBlock(BaseModel):
    start: datetime
    end: datetime
    summary: str | None = None
    is_all_day: bool = False


class CalendarFreeWindow(BaseModel):
    start: datetime
    end: datetime
    duration_minutes: int


class CalendarAvailabilityResult(BaseModel):
    timezone: str
    requested_duration_minutes: int
    window_start: datetime
    window_end: datetime
    busy_blocks: list[CalendarBusyBlock] = Field(default_factory=list)
    free_windows: list[CalendarFreeWindow] = Field(default_factory=list)