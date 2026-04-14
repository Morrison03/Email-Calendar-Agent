from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CalendarEventCreationResult(BaseModel):
    event_id: str
    html_link: str | None = None
    summary: str
    start: datetime
    end: datetime