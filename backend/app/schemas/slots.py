from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SuggestedMeetingSlot(BaseModel):
    start: datetime
    end: datetime
    duration_minutes: int
    label: str


class SlotSuggestionResult(BaseModel):
    timezone: str
    suggestions: list[SuggestedMeetingSlot] = Field(default_factory=list)
    reason: str | None = None